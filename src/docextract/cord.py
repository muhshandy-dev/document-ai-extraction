"""CORD-v2 loader (naver-clova-ix/cord-v2, CC BY 4.0).

Turns one parquet row into: the page image, the ground-truth words with
boxes and word labels, and the ground-truth document (from `gt_parse`).
"""

from __future__ import annotations

import io
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .layout import Word
from .schema import ExtractedDocument, LineItem, ScalarValue
from .text import norm_space, parse_amount, parse_count

SPLITS = ("train", "validation", "test")

# CORD category -> our word label. Anything else becomes "O".
CATEGORY_TO_LABEL = {
    "menu.nm": "menu.nm",
    "menu.cnt": "menu.cnt",
    "menu.unitprice": "menu.unitprice",
    "menu.price": "menu.price",
    "menu.sub_nm": "menu.sub",
    "menu.sub_cnt": "menu.sub",
    "menu.sub_price": "menu.sub",
    "menu.sub_unitprice": "menu.sub",
    "sub_total.subtotal_price": "subtotal",
    "sub_total.tax_price": "tax",
    "sub_total.service_price": "service",
    "sub_total.discount_price": "discount",
    "total.total_price": "total",
    "total.cashprice": "cash",
    "total.changeprice": "change",
}

LABELS = (
    "O",
    "menu.nm",
    "menu.cnt",
    "menu.unitprice",
    "menu.price",
    "menu.sub",
    "subtotal",
    "tax",
    "service",
    "discount",
    "total",
    "cash",
    "change",
)

GT_SCALAR_KEYS = {
    "subtotal": ("sub_total", "subtotal_price"),
    "tax": ("sub_total", "tax_price"),
    "service": ("sub_total", "service_price"),
    "discount": ("sub_total", "discount_price"),
    "total": ("total", "total_price"),
    "cash": ("total", "cashprice"),
    "change": ("total", "changeprice"),
}


@dataclass
class CordSample:
    doc_id: str
    split: str
    image_bytes: bytes
    width: int
    height: int
    gt_words: list[Word]
    gt_doc: ExtractedDocument
    gt_alternatives: dict[str, list[int]]


def _as_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return " ".join(_as_text(x) for x in v)
    if isinstance(v, dict):
        return ""
    return norm_space(str(v))


def _first_amount_list(v) -> list[int]:
    vals = v if isinstance(v, list) else [v]
    out = [parse_amount(_as_text(x)) for x in vals]
    return [x for x in out if x is not None]


def gt_document(gt_parse: dict) -> tuple[ExtractedDocument, dict[str, list[int]]]:
    """Ground-truth document. A field with several values keeps all of them
    as acceptable alternatives (the first one is the canonical value)."""
    menu = gt_parse.get("menu") or []
    if isinstance(menu, dict):
        menu = [menu]
    items = []
    for m in menu:
        if not isinstance(m, dict):
            continue
        name = _as_text(m.get("nm"))
        price = _first_amount_list(m.get("price"))
        unit = _first_amount_list(m.get("unitprice"))
        if not name and not price:
            continue
        items.append(
            LineItem(
                name=name,
                qty=parse_count(_as_text(m.get("cnt"))),
                unit_price=unit[0] if unit else None,
                price=price[0] if price else None,
            )
        )
    doc = ExtractedDocument(items=items)
    alts: dict[str, list[int]] = {}
    for field, (group, key) in GT_SCALAR_KEYS.items():
        g = gt_parse.get(group)
        if isinstance(g, list):  # rare: several sub_total blocks
            g = g[0] if g and isinstance(g[0], dict) else {}
        if not isinstance(g, dict) or key not in g:
            continue
        vals = _first_amount_list(g[key])
        if vals:
            setattr(doc, field, ScalarValue(value=vals[0], text=_as_text(g[key])))
            alts[field] = vals
    return doc, alts


def gt_words(gt: dict, sx: float, sy: float) -> list[Word]:
    words: list[Word] = []
    for line in gt.get("valid_line", []):
        label = CATEGORY_TO_LABEL.get(line.get("category", ""), "O")
        for w in line.get("words", []):
            q = w["quad"]
            xs = [q["x1"], q["x2"], q["x3"], q["x4"]]
            ys = [q["y1"], q["y2"], q["y3"], q["y4"]]
            text = norm_space(w.get("text", ""))
            if not text:
                continue
            lab = "O" if w.get("is_key", 0) else label
            words.append(Word(text, min(xs) * sx, min(ys) * sy, max(xs) * sx, max(ys) * sy, 100.0, lab))
    return words


def iter_split(data_dir: Path, split: str) -> Iterator[CordSample]:
    import pyarrow.parquet as pq
    from PIL import Image

    if split == "test" and os.environ.get("DOCEXTRACT_NO_TEST"):
        raise PermissionError("development mode (DOCEXTRACT_NO_TEST): the test split may not be read")
    files = sorted(data_dir.glob(f"{split}-*.parquet"))
    if not files:
        raise FileNotFoundError(f"no {split}-*.parquet in {data_dir}; run `docextract download`")
    idx = 0
    for f in files:
        table = pq.read_table(f)
        for row in table.to_pylist():
            gt = json.loads(row["ground_truth"])
            img_bytes = row["image"]["bytes"]
            with Image.open(io.BytesIO(img_bytes)) as im:
                width, height = im.size
            meta = gt.get("meta", {}).get("image_size", {})
            mw, mh = meta.get("width", width), meta.get("height", height)
            sx, sy = width / mw if mw else 1.0, height / mh if mh else 1.0
            doc, alts = gt_document(gt.get("gt_parse", {}))
            yield CordSample(
                doc_id=f"{split}-{idx:04d}",  # row order in the parquet files, stable across runs
                split=split,
                image_bytes=img_bytes,
                width=width,
                height=height,
                gt_words=gt_words(gt, sx, sy),
                gt_doc=doc,
                gt_alternatives=alts,
            )
            idx += 1
