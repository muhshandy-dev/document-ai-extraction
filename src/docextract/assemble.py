"""Labelled words -> ExtractedDocument. Twin: web/src/core/assemble.ts."""

from __future__ import annotations

from .layout import Page
from .schema import SCALAR_FIELDS, ExtractedDocument, LineItem, ScalarValue
from .text import parse_amount, parse_count


class _Item:
    def __init__(self) -> None:
        self.name: list[str] = []
        self.cnt: list[str] = []
        self.unit: list[str] = []
        self.price: list[str] = []
        self.probs: list[float] = []
        self.last = ""
        self.last_line = -1

    def to_model(self) -> LineItem:
        price = parse_amount("".join(self.price))
        unit = parse_amount("".join(self.unit))
        conf = sum(self.probs) / len(self.probs) if self.probs else 0.0
        return LineItem(
            name=" ".join(self.name),
            qty=parse_count(" ".join(self.cnt)),
            unit_price=unit,
            price=price,
            confidence=min(max(conf, 0.0), 1.0),
        )


def assemble(page: Page, labels: list[str], probs: list[float]) -> ExtractedDocument:
    words = page.words
    assert len(words) == len(labels) == len(probs)

    # scalar fields: best line-group per field
    groups: dict[str, list[tuple[float, int, list[str], list[float]]]] = {f: [] for f in SCALAR_FIELDS}
    k = 0
    for li, line in enumerate(page.lines):
        per_line: dict[str, tuple[list[str], list[float]]] = {}
        for w in line.words:
            lab = labels[k]
            if lab in groups:
                texts, ps = per_line.setdefault(lab, ([], []))
                texts.append(w.text)
                ps.append(probs[k])
            k += 1
        for lab, (texts, ps) in per_line.items():
            groups[lab].append((sum(ps), li, texts, ps))

    doc = ExtractedDocument()
    for f in SCALAR_FIELDS:
        cands = sorted(groups[f], key=lambda c: (-c[0], c[1]))
        for _, _, texts, ps in cands:
            value = parse_amount("".join(texts))
            if value is not None:
                conf = sum(ps) / len(ps)
                setattr(doc, f, ScalarValue(value=value, confidence=min(max(conf, 0.0), 1.0), text=" ".join(texts)))
                break

    # line items: walk words in reading order
    line_of = [li for li, line in enumerate(page.lines) for _ in line.words]
    items: list[_Item] = []
    cur: _Item | None = None
    for w, lab, p, li in zip(words, labels, probs, line_of, strict=True):
        if not lab.startswith("menu.") or lab == "menu.sub":
            continue
        if lab == "menu.nm":
            if cur is None or cur.price or (cur.name and cur.last != "menu.nm"):
                cur = _Item()
                items.append(cur)
            cur.name.append(w.text)
        elif lab == "menu.cnt":
            if cur is None or cur.price or cur.cnt:
                cur = _Item()
                items.append(cur)
            cur.cnt.append(w.text)
        elif lab == "menu.unitprice":
            if cur is None or cur.price:
                cur = _Item()
                items.append(cur)
            if cur.unit and cur.last != "menu.unitprice":
                continue
            cur.unit.append(w.text)
        elif lab == "menu.price":
            if cur is None or (cur.price and (cur.last != "menu.price" or cur.last_line != li)):
                cur = _Item()
                items.append(cur)
            cur.price.append(w.text)
        cur.probs.append(p)
        cur.last = lab
        cur.last_line = li
    doc.items = [it.to_model() for it in items if it.name or it.price]
    return doc
