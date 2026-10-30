"""Write tests/fixtures/parity.json: Python outputs that the TypeScript core must reproduce.

Uses cached synthetic dev invoices (OCR and PDF text words) plus a few
hand-made receipt pages with OCR-style digit errors and competing totals,
and a small CRF trained on heuristic labels of the synthetic dev set. The
fixture model is only for parity checks; it is never evaluated or shipped.
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
from docextract.model import CrfModel, train  # noqa: E402
from docextract.ocr import OcrConfig  # noqa: E402
from docextract.schema import validate_document  # noqa: E402
from docextract.synth_eval import build_cache  # noqa: E402
from docextract.text import (  # noqa: E402
    fix_ocr_token,
    is_money,
    norm_name,
    parse_amount,
    parse_count,
    similarity,
    word_shape,
)

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
    "1O.0O0",
    "45,5OO",
    "I00.000",
    "1O00",
    "B12",
    "10O",
    "SOS",
    "E6013",
    "OO.OO",
    "B1.2",
]

LAM = 1.0
TAU = 0.6


def hand_pages() -> list[tuple[str, list[Word], float, float]]:
    """Receipts with misread digits and a second, inconsistent total line."""
    rows = [
        [
            ["2", "NASI", "GORENG", "4O.000"],
            ["1", "ES", "TEH", "8.0O0"],
            ["SUBTOTAL", "48.000"],
            ["PB1", "4.800"],
            ["TOTAL", "62.800"],
            ["TOTAL", "52.800"],
            ["CASH", "1OO.000"],
            ["CHANGE", "47.200"],
        ],
        [
            ["KOPI", "SUSU", "18.000"],
            ["ROTI", "BAKAR", "15.0OO"],
            ["TOTAL", "33.000"],
            ["TUNAI", "50.000"],
            ["KEMBALI", "17.000"],
        ],
    ]
    out = []
    for k, page_rows in enumerate(rows):
        words = []
        for r, row in enumerate(page_rows):
            x = 20.0
            for tok in row:
                w = 11.0 * len(tok)
                words.append(Word(tok, x, 30.0 * r + 10, x + w, 30.0 * r + 28, 60.0 + 7 * r))
                x += w + 12.0
        out.append((f"hand-{k}", words, 500.0, 30.0 * len(page_rows) + 20))
    return out


def main() -> None:
    recs = build_cache(P.CACHE / "synth-dev", range(0, 60), P.ensure_tessdata(), OcrConfig("eng", 4))
    pages = []
    for rec in recs[:40]:
        for src in ("ocr", "pdf"):
            words = [Word.from_dict(d) for d in rec[f"{src}_words"]]
            w, h = (rec["width"], rec["height"]) if src == "ocr" else rec["pdf_size"]
            pages.append((f"{rec['doc_id']}-{src}", words, w, h))
    train_pages = [group_lines(ws, w, h) for _, ws, w, h in pages[:60]]
    model = train(train_pages, [label_page(p) for p in train_pages], c1=0.05, c2=0.1)
    model = CrfModel.from_json(json.loads(json.dumps(model.to_json())))

    cases = []
    for name, words, w, h in pages[60:] + hand_pages():
        page = group_lines(words, w, h)
        h_labels = label_page(page)
        n_labels, n_probs = model.predict_page(page)
        doc_h = assemble(page, h_labels, [1.0] * len(h_labels), lam=LAM)
        doc_n = assemble(page, n_labels, n_probs, lam=LAM)
        doc_n0 = assemble(page, n_labels, n_probs, lam=0.0)
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
                "doc_n0": doc_n0.model_dump(mode="json"),
                "issues_h": [i.code for i in validate_document(doc_h)],
                "issues_n": [i.code for i in validate_document(doc_n, min_conf=TAU)],
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
            "fixed": fix_ocr_token(t),
        }
        for t in TEXT_CASES
    ]
    out = ROOT / "tests" / "fixtures" / "parity.json"
    out.write_text(json.dumps({"model": model.to_json(), "lam": LAM, "tau": TAU, "text": text, "cases": cases}))
    print(out, len(cases), "pages", out.stat().st_size // 1024, "KiB")


if __name__ == "__main__":
    main()
