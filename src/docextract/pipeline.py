"""End-to-end steps: cache OCR, train N, evaluate H vs N on a split."""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .assemble import assemble
from .cord import iter_split
from .evaluate import DocScore, aggregate, score_document
from .heuristic import label_page
from .layout import Page, Word, group_lines
from .model import LinearModel
from .ocr import align_labels, ocr_image, word_recall
from .schema import ExtractedDocument, validate_document

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CORD_DIR = DATA / "cord"
CACHE = DATA / "cache"
TESSDATA_GZ = ROOT / "web" / "public" / "tessdata"
TESSDATA = DATA / "tessdata"

HF_BASE = "https://huggingface.co/datasets/naver-clova-ix/cord-v2/resolve/main/data/"
CORD_FILES = {
    "test-00000-of-00001-9c204eb3f4e11791.parquet": None,
    "validation-00000-of-00001-cc3c5779fe22e8ca.parquet": None,
    "train-00000-of-00004-b4aaeceff1d90ecb.parquet": None,
    "train-00001-of-00004-7dbbe248962764c5.parquet": None,
    "train-00002-of-00004-688fe1305a55e5cc.parquet": None,
    "train-00003-of-00004-2d0cd200555ed7fd.parquet": None,
}


def ensure_tessdata() -> Path:
    """Unpack the browser's gzipped traineddata for native Tesseract."""
    import gzip

    TESSDATA.mkdir(parents=True, exist_ok=True)
    for gz in TESSDATA_GZ.glob("*.traineddata.gz"):
        target = TESSDATA / gz.name[:-3]
        if not target.exists():
            target.write_bytes(gzip.decompress(gz.read_bytes()))
    return TESSDATA


def ocr_key(lang: str, psm: int) -> str:
    return f"{lang.replace('+', '_')}-psm{psm}"


# ---------------------------------------------------------------- caching


def cache_ground_truth(split: str) -> Path:
    """Write GT words + documents (no images) to data/cache/gt/<split>.jsonl."""
    out = CACHE / "gt" / f"{split}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for s in iter_split(CORD_DIR, split):
            fh.write(
                json.dumps(
                    {
                        "doc_id": s.doc_id,
                        "width": s.width,
                        "height": s.height,
                        "words": [w.to_dict() for w in s.gt_words],
                        "doc": s.gt_doc.model_dump(mode="json"),
                        "alts": s.gt_alternatives,
                    }
                )
                + "\n"
            )
    return out


def load_gt(split: str) -> list[dict]:
    path = CACHE / "gt" / f"{split}.jsonl"
    if not path.exists():
        cache_ground_truth(split)
    return [json.loads(line) for line in path.read_text().splitlines()]


def _ocr_job(args: tuple[str, bytes, str, int, str]) -> tuple[str, list[dict]]:
    doc_id, img, lang, psm, tessdata = args
    words = ocr_image(img, lang=lang, psm=psm, tessdata_dir=Path(tessdata))
    return doc_id, [w.to_dict() for w in words]


def cache_ocr(split: str, lang: str, psm: int, workers: int = 4, limit: int | None = None) -> Path:
    """OCR every page of a split once; results are reused by all experiments."""
    out_dir = CACHE / "ocr" / ocr_key(lang, psm)
    out_dir.mkdir(parents=True, exist_ok=True)
    ensure_tessdata()
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    jobs = []
    for i, s in enumerate(iter_split(CORD_DIR, split)):
        if limit is not None and i >= limit:
            break
        if not (out_dir / f"{s.doc_id}.json").exists():
            jobs.append((s.doc_id, s.image_bytes, lang, psm, str(TESSDATA)))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for doc_id, words in ex.map(_ocr_job, jobs, chunksize=2):
            (out_dir / f"{doc_id}.json").write_text(json.dumps(words))
    return out_dir


def load_ocr(doc_id: str, lang: str, psm: int) -> list[Word]:
    path = CACHE / "ocr" / ocr_key(lang, psm) / f"{doc_id}.json"
    return [Word.from_dict(d) for d in json.loads(path.read_text())]


# ---------------------------------------------------------------- pages


def gt_page(rec: dict) -> Page:
    return group_lines([Word.from_dict(d) for d in rec["words"]], rec["width"], rec["height"])


def ocr_page(rec: dict, lang: str, psm: int, labelled: bool = False) -> Page:
    words = load_ocr(rec["doc_id"], lang, psm)
    if labelled:
        words = align_labels(words, [Word.from_dict(d) for d in rec["words"]])
    return group_lines(words, rec["width"], rec["height"])


def ocr_word_recall(split: str, lang: str, psm: int) -> float:
    hit = tot = 0
    for rec in load_gt(split):
        h, t = word_recall(load_ocr(rec["doc_id"], lang, psm), [Word.from_dict(d) for d in rec["words"]])
        hit, tot = hit + h, tot + t
    return hit / tot if tot else 0.0


# ---------------------------------------------------------------- extraction


def extract(page: Page, approach: str, model: LinearModel | None, min_conf: float | None):
    if approach == "H":
        labels = label_page(page)
        probs = [1.0] * len(labels)
        doc = assemble(page, labels, probs)
        issues = validate_document(doc)
    else:
        assert model is not None
        labels, probs = model.predict_page(page)
        doc = assemble(page, labels, probs)
        issues = validate_document(doc, min_conf=min_conf)
    return doc, issues, labels, probs


def run_split(
    split: str,
    approach: str,
    source: str,
    lang: str,
    psm: int,
    model: LinearModel | None = None,
    min_conf: float | None = None,
    keep_predictions: bool = False,
) -> tuple[list[DocScore], list[dict]]:
    scores: list[DocScore] = []
    preds: list[dict] = []
    for rec in load_gt(split):
        page = gt_page(rec) if source == "gt" else ocr_page(rec, lang, psm)
        doc, issues, labels, probs = extract(page, approach, model, min_conf)
        gt = ExtractedDocument.model_validate(rec["doc"])
        scores.append(score_document(rec["doc_id"], doc, gt, rec["alts"], [i.code for i in issues]))
        if keep_predictions:
            preds.append(
                {"doc_id": rec["doc_id"], "doc": doc.model_dump(mode="json"), "issues": [i.code for i in issues]}
            )
    return scores, preds


def summary(scores: list[DocScore]) -> dict:
    return aggregate(scores)
