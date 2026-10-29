"""Write tests/fixtures/parity.json: Python outputs that the TypeScript core must reproduce.

Uses cached synthetic dev invoices (OCR and PDF text words) plus a few
hand-made receipt pages, and a small model trained on heuristic labels of
the synthetic dev set. The fixture model is only for parity checks; it is
never evaluated or shipped.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docextract import pipeline as P  # noqa: E402
from docextract.assemble import assemble  # noqa: E402
from docextract.features import page_features  # noqa: E402
from docextract.heuristic import label_page  # noqa: E402
from docextract.layout import Word, group_lines  # noqa: E402
from docextract.model import LinearModel, train  # noqa: E402
from docextract.schema import validate_document  # noqa: E402
from docextract.synth_eval import build_cache  # noqa: E402
from docextract.text import is_money, norm_name, parse_amount, parse_count, similarity, word_shape  # noqa: E402

TEXT_CASES = [
    "Rp 45.500",
    "45,500",
    "12,500.00",
    "45.50",
    "2x",
    "x 3",
    "(5,000)",
    "1.234.567",
    "abc",
    "100",
    "Rp45.000",
    "IDR 1,000",
    "081234567890123",
    "TOTAL",
    "goréng",
    "Śląsk",
    "  a  b ",
    "12:30",
    "-5.000",
    "99999",
]


def main() -> None:
    recs = build_cache(P.CACHE / "synth-dev", range(0, 60), P.ensure_tessdata(), "eng", 4)
    pages = []
    for rec in recs[:40]:
        for src in ("ocr", "pdf"):
            words = [Word.from_dict(d) for d in rec[f"{src}_words"]]
            w, h = (rec["width"], rec["height"]) if src == "ocr" else rec["pdf_size"]
            pages.append((f"{rec['doc_id']}-{src}", words, w, h))
    train_pages = [group_lines(ws, w, h) for _, ws, w, h in pages[:60]]
    model = train(train_pages, [label_page(p) for p in train_pages], c=1.0)
    model = LinearModel(**model.to_json())

    cases = []
    for name, words, w, h in pages[60:]:
        page = group_lines(words, w, h)
        h_labels = label_page(page)
        n_labels, n_probs = model.predict_page(page)
        doc_h = assemble(page, h_labels, [1.0] * len(h_labels))
        doc_n = assemble(page, n_labels, n_probs)
        cases.append(
            {
                "name": name,
                "width": w,
                "height": h,
                "words": [x.to_dict() for x in words],
                "lines": [[x.text for x in ln.words] for ln in page.lines],
                "features": page_features(page),
                "h_labels": h_labels,
                "n_labels": n_labels,
                "n_probs": n_probs,
                "doc_h": doc_h.model_dump(mode="json"),
                "doc_n": doc_n.model_dump(mode="json"),
                "issues_h": [i.code for i in validate_document(doc_h)],
                "issues_n": [i.code for i in validate_document(doc_n, min_conf=0.6)],
            }
        )
    text = [
        {
            "text": t,
            "amount": parse_amount(t),
            "count": parse_count(t),
            "money": is_money(t),
            "shape": word_shape(t),
            "norm": norm_name(t),
            "sim_total": round(similarity(t, "TOTAL"), 9),
        }
        for t in TEXT_CASES
    ]
    out = ROOT / "tests" / "fixtures" / "parity.json"
    out.write_text(json.dumps({"model": model.to_json(), "text": text, "cases": cases}))
    print(out, len(cases), "pages", out.stat().st_size // 1024, "KiB")


if __name__ == "__main__":
    main()
