"""Pydantic schema for an extracted receipt/invoice and its validation rules.

The browser twin is web/src/core/schema.ts. Review routing uses the
issues returned by `validate_document`: any issue sends the document to
a human reviewer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCALAR_FIELDS = ("subtotal", "tax", "service", "discount", "total", "cash", "change")

FieldName = Literal["subtotal", "tax", "service", "discount", "total", "cash", "change"]


class LineItem(BaseModel):
    name: str = ""
    qty: int | None = Field(default=None, ge=0, le=10_000)
    unit_price: int | None = Field(default=None, ge=0)
    price: int | None = Field(default=None, ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())


class ScalarValue(BaseModel):
    value: int = Field(ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    text: str = ""


class ExtractedDocument(BaseModel):
    items: list[LineItem] = Field(default_factory=list)
    subtotal: ScalarValue | None = None
    tax: ScalarValue | None = None
    service: ScalarValue | None = None
    discount: ScalarValue | None = None
    total: ScalarValue | None = None
    cash: ScalarValue | None = None
    change: ScalarValue | None = None

    def value(self, name: str) -> int | None:
        v = getattr(self, name)
        return None if v is None else v.value

    def scalar_values(self) -> dict[str, int | None]:
        return {f: self.value(f) for f in SCALAR_FIELDS}


class Issue(BaseModel):
    code: str
    message: str
    field: str | None = None


def verified_fields(doc: ExtractedDocument) -> set[str]:
    """Scalar fields whose value is confirmed by an arithmetic check that holds.

    - items sum == subtotal confirms subtotal;
    - total == one of the accepted sums confirms total and the parts used in that sum;
    - cash - change == total confirms cash, change and total.
    Item names are never confirmed this way.
    """
    v = doc.scalar_values()
    out: set[str] = set()
    item_sum = sum(it.price or 0 for it in doc.items)
    sub, total = v["subtotal"], v["total"]
    if doc.items and sub is not None and item_sum == sub:
        out.add("subtotal")
    if total is not None:
        base = sub if sub is not None else (item_sum if doc.items else None)
        if base is not None:
            tax, svc, disc = v["tax"] or 0, v["service"] or 0, v["discount"] or 0
            parts = (
                ("tax", "service", "discount"),
                ("tax", "service"),
                ("discount",),
                (),
            )
            sums = (base + tax + svc - disc, base + tax + svc, base - disc, base)
            for used, value in zip(parts, sums, strict=True):
                if total == value:
                    out.add("total")
                    if sub is not None:
                        out.add("subtotal")
                    out.update(f for f in used if v[f] is not None)
                    break
        cash, change = v["cash"], v["change"]
        if cash is not None and change is not None and cash - change == total:
            out.update(("cash", "change", "total"))
    return out


def validate_document(doc: ExtractedDocument, min_conf: float | None = None) -> list[Issue]:
    """Business-rule checks. `min_conf` is only used for the trained extractor.

    v2: a field below `min_conf` is not flagged when an arithmetic check
    confirms its value (see verified_fields). Items are flagged when their
    name confidence is below `min_conf`.
    """
    issues: list[Issue] = []
    v = doc.scalar_values()
    total = v["total"]
    if total is None:
        issues.append(Issue(code="TOTAL_MISSING", message="Total belum ditemukan", field="total"))
    if not doc.items:
        issues.append(Issue(code="NO_ITEMS", message="Belum ada baris item"))

    for i, it in enumerate(doc.items):
        if it.price is None:
            issues.append(Issue(code="ITEM_NO_PRICE", message=f"Item {i + 1} belum punya harga", field=f"items.{i}"))
        elif it.qty and it.unit_price and it.qty * it.unit_price != it.price:
            issues.append(
                Issue(
                    code="ITEM_QTY_PRICE",
                    message=f"Item {i + 1}: jumlah kali harga satuan tidak sama dengan harga",
                    field=f"items.{i}",
                )
            )

    item_sum = sum(it.price or 0 for it in doc.items)
    sub = v["subtotal"]
    if sub is not None and doc.items and item_sum != sub:
        issues.append(Issue(code="ITEMS_SUM", message="Jumlah harga item berbeda dengan subtotal", field="subtotal"))

    if total is not None:
        base = sub if sub is not None else (item_sum if doc.items else None)
        if base is not None:
            tax = v["tax"] or 0
            svc = v["service"] or 0
            disc = v["discount"] or 0
            # Indonesian receipts print totals either tax-exclusive or inclusive.
            allowed = {
                base + tax + svc - disc,
                base + tax + svc,
                base - disc,
                base,
            }
            if total not in allowed:
                issues.append(
                    Issue(
                        code="TOTAL_MISMATCH",
                        message="Total tidak cocok dengan subtotal, pajak, servis, dan diskon",
                        field="total",
                    )
                )
        cash, change = v["cash"], v["change"]
        if cash is not None and change is not None and cash - change != total:
            issues.append(
                Issue(code="CASH_CHANGE", message="Tunai dikurangi kembalian tidak sama dengan total", field="cash")
            )
        if cash is not None and change is None and cash < total:
            issues.append(Issue(code="CASH_SHORT", message="Uang tunai lebih kecil dari total", field="cash"))

    if min_conf is not None:
        proven = verified_fields(doc)
        for f in SCALAR_FIELDS:
            sv = getattr(doc, f)
            if sv is not None and sv.confidence < min_conf and f not in proven:
                issues.append(Issue(code="LOW_CONF", message=f"Keyakinan rendah: {f}", field=f))
        for i, it in enumerate(doc.items):
            if it.confidence < min_conf:
                issues.append(Issue(code="LOW_CONF", message=f"Keyakinan rendah: item {i + 1}", field=f"items.{i}"))
    return issues
