"""Command line: `docextract <step>` or `docextract all`.

Protocol (docs/EVALUASI.md): OCR settings, C and the review threshold are
chosen on the validation split only; the test split is scored once with
the frozen choices.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

from . import pipeline as P
from .evaluate import aggregate, bootstrap
from .model import LinearModel, train

# DOCEXTRACT_OUT redirects outputs (evaluation/, web/public/model, web/public/samples).
OUT = Path(os.environ.get("DOCEXTRACT_OUT", P.ROOT))
EVAL = OUT / "evaluation"
MODEL_PATH = OUT / "web" / "public" / "model" / "model-n.json"
CONFIG_PATH = EVAL / "config.json"

OCR_GRID = [("eng", 4), ("eng", 6), ("ind", 4), ("ind", 6), ("eng+ind", 4), ("eng+ind", 6)]
C_GRID = [0.1, 0.3, 1.0, 3.0]
TAU_GRID = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]


def _write(path: Path, obj, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:  # the browser downloads the model; indentation alone adds about 2 MB
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(obj, indent=1, ensure_ascii=False)
    path.write_text(text + "\n")


def _config() -> dict:
    return json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}


def _save_config(**kw) -> dict:
    cfg = _config()
    cfg.update(kw)
    _write(CONFIG_PATH, cfg)
    return cfg


def cmd_download(_: argparse.Namespace) -> None:
    P.CORD_DIR.mkdir(parents=True, exist_ok=True)
    for name in P.CORD_FILES:
        target = P.CORD_DIR / name
        if target.exists():
            continue
        print("download", name)
        urllib.request.urlretrieve(P.HF_BASE + name, target)
    for split in ("train", "validation", "test"):
        P.cache_ground_truth(split)
    print("ground truth cached in", P.CACHE / "gt")


def cmd_select_ocr(args: argparse.Namespace) -> None:
    rows = []
    for lang, psm in OCR_GRID:
        t = time.time()
        P.cache_ocr("validation", lang, psm, workers=args.workers)
        rec = P.ocr_word_recall("validation", lang, psm)
        rows.append({"lang": lang, "psm": psm, "word_recall": round(rec, 4), "seconds": round(time.time() - t, 1)})
        print(rows[-1])
    best = max(rows, key=lambda r: r["word_recall"])
    _write(EVAL / "ocr-selection.json", {"split": "validation", "grid": rows, "chosen": best})
    _save_config(ocr_lang=best["lang"], ocr_psm=best["psm"])


def cmd_ocr(args: argparse.Namespace) -> None:
    cfg = _config()
    for split in args.splits:
        t = time.time()
        P.cache_ocr(split, cfg["ocr_lang"], cfg["ocr_psm"], workers=args.workers)
        print(split, f"{time.time() - t:.0f}s")


def _train_pages(cfg: dict):
    pages, gold = [], []
    for rec in P.load_gt("train"):
        for page in (P.ocr_page(rec, cfg["ocr_lang"], cfg["ocr_psm"], labelled=True), P.gt_page(rec)):
            pages.append(page)
            gold.append([w.label for w in page.words])
    return pages, gold


def cmd_train(_: argparse.Namespace) -> None:
    cfg = _config()
    pages, gold = _train_pages(cfg)
    rows = []
    best = None
    for c in C_GRID:
        model = train(pages, gold, c=c)
        model = LinearModel(**{k: v for k, v in model.to_json().items()})  # exported, rounded weights
        scores, _ = P.run_split("validation", "N", "ocr", cfg["ocr_lang"], cfg["ocr_psm"], model)
        agg = aggregate(scores)
        sel = (agg["field_micro_f1"] + agg["row_f1"]) / 2
        rows.append({"C": c, "field_micro_f1": agg["field_micro_f1"], "row_f1": agg["row_f1"], "selection_score": sel})
        print(rows[-1])
        if best is None or sel > best[0]:
            best = (sel, c, model)
    assert best is not None
    _, c, model = best
    tau_rows = []
    for tau in TAU_GRID:
        scores, _ = P.run_split("validation", "N", "ocr", cfg["ocr_lang"], cfg["ocr_psm"], model, min_conf=tau)
        auto = [s for s in scores if not s.routed]
        right = sum(s.doc_correct for s in auto)
        wrong = len(auto) - right
        tau_rows.append(
            {"tau": tau, "auto": len(auto), "auto_right": right, "auto_wrong": wrong, "utility": right - 2 * wrong}
        )
    tau = max(tau_rows, key=lambda r: (r["utility"], -r["tau"]))["tau"]
    model.meta["review_min_conf"] = tau
    model.meta["ocr"] = {"lang": cfg["ocr_lang"], "psm": cfg["ocr_psm"]}
    _write(MODEL_PATH, model.to_json(), compact=True)
    _write(
        EVAL / "model-selection.json",
        {"split": "validation", "C_grid": rows, "chosen_C": c, "tau_grid": tau_rows, "chosen_tau": tau},
    )
    _save_config(C=c, tau=tau)
    print("model ->", MODEL_PATH, "C", c, "tau", tau)


def cmd_evaluate(args: argparse.Namespace) -> None:
    cfg = _config()
    model = LinearModel.load(MODEL_PATH)
    tau = model.meta["review_min_conf"]
    runs, preds = {}, {}
    for name, approach, source in (
        ("H-ocr", "H", "ocr"),
        ("N-ocr", "N", "ocr"),
        ("H-gt", "H", "gt"),
        ("N-gt", "N", "gt"),
    ):
        scores, pr = P.run_split(
            args.split,
            approach,
            source,
            cfg["ocr_lang"],
            cfg["ocr_psm"],
            model,
            min_conf=tau if approach == "N" else None,
            keep_predictions=True,
        )
        runs[name], preds[name] = scores, pr
    summary = {name: aggregate(s) for name, s in runs.items()}
    boot = bootstrap(runs, n_boot=args.n_boot)
    out = {
        "split": args.split,
        "dataset": "naver-clova-ix/cord-v2 (CC BY 4.0)",
        "ocr": {"engine": "tesseract (native)", "lang": cfg["ocr_lang"], "psm": cfg["ocr_psm"]},
        "model": {"C": model.meta["C"], "review_min_conf": tau, "n_features": model.meta["n_features"]},
        "summary": summary,
        "bootstrap": boot,
    }
    _write(EVAL / f"results-{args.split}.json", out)
    _write(EVAL / f"per-doc-{args.split}.json", {k: [s.to_dict() for s in v] for k, v in runs.items()})
    _write(EVAL / f"predictions-{args.split}.json", preds)
    for name, agg in summary.items():
        print(
            name,
            f"fieldF1={agg['field_micro_f1']:.3f}",
            f"rowF1={agg['row_f1']:.3f}",
            f"tabel={agg['table_doc_accuracy']:.2f}",
            f"review={agg['review_rate']:.2f}",
            f"auto_acc={agg['auto_accept_accuracy']}",
        )


def cmd_synth(args: argparse.Namespace) -> None:
    from .assemble import assemble
    from .evaluate import score_document
    from .heuristic import label_page
    from .layout import Word, group_lines
    from .schema import validate_document
    from .synth_eval import build_cache, gt_of

    cfg = _config()
    model = LinearModel.load(MODEL_PATH)
    tau = model.meta["review_min_conf"]
    recs = build_cache(
        P.CACHE / "synth", range(args.start, args.start + args.n), P.ensure_tessdata(), cfg["ocr_lang"], cfg["ocr_psm"]
    )
    runs = {}
    for source in ("ocr", "pdf"):
        for approach in ("H", "N"):
            scores = []
            for rec in recs:
                words = [Word.from_dict(d) for d in rec[f"{source}_words"]]
                w, h = (rec["width"], rec["height"]) if source == "ocr" else rec["pdf_size"]
                page = group_lines(words, w, h)
                if approach == "H":
                    labels = label_page(page)
                    probs = [1.0] * len(labels)
                    doc = assemble(page, labels, probs)
                    issues = validate_document(doc)
                else:
                    labels, probs = model.predict_page(page)
                    doc = assemble(page, labels, probs)
                    issues = validate_document(doc, min_conf=tau)
                scores.append(score_document(rec["doc_id"], doc, gt_of(rec), rec["alts"], [i.code for i in issues]))
            runs[f"{approach}-{source}"] = scores
    summary = {k: aggregate(v) for k, v in runs.items()}
    out = {
        "split": f"synthetic seeds {args.start}-{args.start + args.n - 1}",
        "note": "out-of-domain: model trained on CORD receipts only",
        "summary": summary,
        "bootstrap": bootstrap(runs, n_boot=args.n_boot),
    }
    _write(EVAL / "results-synth.json", out)
    for k, agg in summary.items():
        print(
            k, f"fieldF1={agg['field_micro_f1']:.3f}", f"rowF1={agg['row_f1']:.3f}", f"review={agg['review_rate']:.2f}"
        )


def cmd_export_web(args: argparse.Namespace) -> None:
    """Demo samples + evaluation JSON for the static site (web/public)."""
    import shutil

    from .synth import make_invoice, render_pdf
    from .synth_eval import scan_image

    pub = OUT / "web" / "public"
    sdir = pub / "samples"
    sdir.mkdir(parents=True, exist_ok=True)
    samples = []
    for k, seed in enumerate(range(5000, 5000 + args.n_synth)):
        spec, doc = make_invoice(seed)
        pdf = sdir / f"faktur-{seed}.pdf"
        render_pdf(spec, doc, pdf)
        samples.append(
            {
                "id": f"faktur-{seed}",
                "title": f"Faktur {spec['number']}",
                "origin": "Faktur sintetis",
                "kind": "pdf",
                "src": f"samples/{pdf.name}",
            }
        )
        if k == 0:  # one scanned copy to show OCR on an image
            tmp = P.CACHE / "scan-tmp.pdf"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(pdf, tmp)
            (sdir / f"faktur-{seed}-pindai.jpg").write_bytes(scan_image(tmp, seed))
            tmp.unlink()
            samples.append(
                {
                    "id": f"faktur-{seed}-pindai",
                    "title": f"Faktur {spec['number']} (pindaian)",
                    "origin": "Faktur sintetis",
                    "kind": "image",
                    "src": f"samples/faktur-{seed}-pindai.jpg",
                }
            )
    if args.cord and any(P.CORD_DIR.glob("test-*.parquet")):
        from .cord import iter_split

        for i, s in enumerate(iter_split(P.CORD_DIR, "test")):
            if i >= args.n_cord:
                break
            name = f"cord-{s.doc_id}.jpg"
            (sdir / name).write_bytes(s.image_bytes)
            samples.append(
                {
                    "id": f"cord-{s.doc_id}",
                    "title": f"Struk {s.doc_id}",
                    "origin": "CORD-v2 (CC BY 4.0)",
                    "kind": "image",
                    "src": f"samples/{name}",
                }
            )
    _write(sdir / "index.json", samples)
    ddir = pub / "data"
    ddir.mkdir(parents=True, exist_ok=True)
    for name in ("results-test.json", "results-synth.json", "model-selection.json", "ocr-selection.json"):
        src = EVAL / name
        if src.exists():
            shutil.copy(src, ddir / name)
    print("samples:", len(samples), "->", sdir)


def cmd_all(args: argparse.Namespace) -> None:
    """Full protocol in order. The test split is scored once, after every choice is frozen."""
    ns = argparse.Namespace
    if not args.skip_download:
        cmd_download(ns())
    cmd_select_ocr(ns(workers=args.workers))
    cmd_ocr(ns(splits=["train", "validation", "test"], workers=args.workers))
    cmd_train(ns())
    cmd_evaluate(ns(split="validation", n_boot=args.n_boot))
    cmd_evaluate(ns(split="test", n_boot=args.n_boot))
    cmd_synth(ns(start=1000, n=args.n_synth, n_boot=args.n_boot))
    cmd_export_web(ns(n_synth=3, n_cord=4, cord=True))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="docextract")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("download").set_defaults(fn=cmd_download)
    p = sub.add_parser("select-ocr")
    p.add_argument("--workers", type=int, default=4)
    p.set_defaults(fn=cmd_select_ocr)
    p = sub.add_parser("ocr")
    p.add_argument("--splits", nargs="+", default=["train", "validation", "test"])
    p.add_argument("--workers", type=int, default=4)
    p.set_defaults(fn=cmd_ocr)
    sub.add_parser("train").set_defaults(fn=cmd_train)
    p = sub.add_parser("evaluate")
    p.add_argument("--split", default="validation", choices=["validation", "test"])
    p.add_argument("--n-boot", type=int, default=2000)
    p.set_defaults(fn=cmd_evaluate)
    p = sub.add_parser("synth")
    p.add_argument("--start", type=int, default=1000)
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--n-boot", type=int, default=1000)
    p.set_defaults(fn=cmd_synth)
    p = sub.add_parser("export-web")
    p.add_argument("--n-synth", type=int, default=3)
    p.add_argument("--n-cord", type=int, default=4)
    p.add_argument("--no-cord", dest="cord", action="store_false")
    p.set_defaults(fn=cmd_export_web)
    p = sub.add_parser("all")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--n-boot", type=int, default=2000)
    p.add_argument("--n-synth", type=int, default=200)
    p.add_argument("--skip-download", action="store_true")
    p.set_defaults(fn=cmd_all)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
