"""Labelled words -> ExtractedDocument. Twin: web/src/core/assemble.ts.

Scalar fields (v2): each field keeps up to MAX_CANDIDATES values from the
line groups labelled with it. The chosen combination maximises

    sum(log confidence) + lam * (number of arithmetic checks that hold)

so a slightly less confident reading wins when it makes subtotal, tax,
total, cash and change add up. With lam = 0 this is the v1 choice (the
most confident group per field).

When the word labeller gives a label distribution (N and T), words that
were not labelled with a field but still have probability >= ALT_MIN for
it form extra candidates for that field, ranked after the labelled ones,
with confidence = mean probability of the field. These alternatives are
only considered when lam > 0, so they can win only through the
arithmetic checks.
"""

from __future__ import annotations

import math
from itertools import product

from .layout import Page
from .schema import SCALAR_FIELDS, ExtractedDocument, LineItem, ScalarValue
from .text import parse_amount, parse_count

MAX_CANDIDATES = 3
MIN_LOG_CONF = 1e-6
ALT_MIN = 0.1


class _Item:
    def __init__(self) -> None:
        self.name: list[str] = []
        self.cnt: list[str] = []
        self.unit: list[str] = []
        self.price: list[str] = []
        self.probs: list[float] = []
        self.name_probs: list[float] = []
        self.last = ""
        self.last_line = -1

    def to_model(self) -> LineItem:
        price = parse_amount("".join(self.price))
        unit = parse_amount("".join(self.unit))
        ps = self.name_probs or self.probs  # v2: an item is as sure as its name
        conf = sum(ps) / len(ps) if ps else 0.0
        return LineItem(
            name=" ".join(self.name),
            qty=parse_count(" ".join(self.cnt)),
            unit_price=unit,
            price=price,
            confidence=min(max(conf, 0.0), 1.0),
        )


def total_options(base: int, tax: int, svc: int, disc: int) -> list[int]:
    """Totals accepted for a base amount (receipts print totals with or without tax)."""
    return [base + tax + svc - disc, base + tax + svc, base - disc, base]


def arithmetic_checks(values: dict[str, int | None], item_sum: int, has_items: bool) -> int:
    """How many of the three independent checks hold (0-3)."""
    n = 0
    sub, total = values["subtotal"], values["total"]
    if has_items and sub is not None and item_sum == sub:
        n += 1
    if total is not None:
        base = sub if sub is not None else (item_sum if has_items else None)
        if base is not None and total in total_options(
            base, values["tax"] or 0, values["service"] or 0, values["discount"] or 0
        ):
            n += 1
        cash, change = values["cash"], values["change"]
        if cash is not None and change is not None and cash - change == total:
            n += 1
    return n


def assemble(
    page: Page,
    labels: list[str],
    probs: list[float],
    lam: float = 0.0,
    field_probs: list[dict[str, float]] | None = None,
) -> ExtractedDocument:
    """field_probs[k][f]: probability that word k carries scalar field f (optional)."""
    words = page.words
    assert len(words) == len(labels) == len(probs)
    assert field_probs is None or len(field_probs) == len(words)

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
            cur.name_probs.append(p)
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
    doc = ExtractedDocument(items=[it.to_model() for it in items if it.name or it.price])
    item_sum = sum(it.price or 0 for it in doc.items)

    # scalar fields: line groups per field -> candidate values
    groups: dict[str, list[tuple[float, int, list[str], list[float]]]] = {f: [] for f in SCALAR_FIELDS}
    alts: dict[str, list[tuple[float, int, list[str], list[float]]]] = {f: [] for f in SCALAR_FIELDS}
    use_alts = field_probs is not None and lam != 0.0
    k = 0
    for li, line in enumerate(page.lines):
        per_line: dict[str, tuple[list[str], list[float]]] = {}
        alt_line: dict[str, tuple[list[str], list[float]]] = {}
        for w in line.words:
            lab = labels[k]
            if lab in groups:
                texts, ps = per_line.setdefault(lab, ([], []))
                texts.append(w.text)
                ps.append(probs[k])
            if use_alts:
                assert field_probs is not None
                for f in SCALAR_FIELDS:
                    p = field_probs[k].get(f, 0.0)
                    if f != lab and p >= ALT_MIN:
                        texts, ps = alt_line.setdefault(f, ([], []))
                        texts.append(w.text)
                        ps.append(p)
            k += 1
        for lab, (texts, ps) in per_line.items():
            groups[lab].append((sum(ps), li, texts, ps))
        for f in SCALAR_FIELDS:
            if f in alt_line:
                texts, ps = alt_line[f]
                alts[f].append((sum(ps), li, texts, ps))

    options: list[list[ScalarValue | None]] = []
    for f in SCALAR_FIELDS:
        cands: list[ScalarValue] = []
        seen: set[int] = set()
        ranked = sorted(groups[f], key=lambda c: (-c[0], c[1])) + sorted(alts[f], key=lambda c: (-c[0], c[1]))
        for _, _, texts, ps in ranked:
            value = parse_amount("".join(texts))
            if value is None or value in seen:
                continue
            seen.add(value)
            conf = min(max(sum(ps) / len(ps), 0.0), 1.0)
            cands.append(ScalarValue(value=value, confidence=conf, text=" ".join(texts)))
            if len(cands) == MAX_CANDIDATES or lam == 0.0:
                break
        options.append(cands if cands else [None])

    best: tuple[ScalarValue | None, ...] | None = None
    best_score = -math.inf
    for combo in product(*options):
        score = 0.0
        for sv in combo:
            if sv is not None:
                score += math.log(max(sv.confidence, MIN_LOG_CONF))
        if lam != 0.0:
            values = {f: (sv.value if sv is not None else None) for f, sv in zip(SCALAR_FIELDS, combo, strict=True)}
            score += lam * arithmetic_checks(values, item_sum, bool(doc.items))
        if score > best_score:
            best, best_score = combo, score
    assert best is not None
    for f, sv in zip(SCALAR_FIELDS, best, strict=True):
        setattr(doc, f, sv)
    return doc
