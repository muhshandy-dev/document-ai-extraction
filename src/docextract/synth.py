"""Synthetic Indonesian invoices (PDF + ground truth) for the demo and an
out-of-domain test. All names are invented; amounts are generated so the
arithmetic is consistent (qty x unit = amount, subtotal - discount + PPN = total).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .schema import ExtractedDocument, LineItem, ScalarValue

SELLERS = [
    "CV Sinar Teknik Mandiri",
    "PT Arunika Suplai Industri",
    "UD Bumi Baut Sejahtera",
    "PT Delta Kalibrasi Nusantara",
    "CV Mahakam Hidrolik",
    "PT Lintas Pelumas Prima",
]
BUYERS = ["PT Contoh Fabrikasi Batam", "PT Sampel Tambang Kaltim", "CV Uji Coba Manufaktur", "PT Demo Energi Samarinda"]
PRODUCTS = [
    ("Baut hex M12 x 50 galvanis", 2_500, 9_000),
    ("Mur M12 stainless", 1_500, 6_000),
    ("Sarung tangan las kulit", 35_000, 95_000),
    ("Kacamata safety bening", 18_000, 60_000),
    ("Oli hidrolik ISO VG 46 (20 L)", 650_000, 1_450_000),
    ("Filter oli mesin", 85_000, 240_000),
    ("Bearing 6205 2RS", 45_000, 120_000),
    ("Kabel NYY 4x10 mm (meter)", 55_000, 110_000),
    ("Jasa kalibrasi pressure gauge", 250_000, 600_000),
    ("Helm safety putih", 45_000, 130_000),
    ("Selang hidrolik 1/2 inch (meter)", 75_000, 180_000),
    ("Gasket spiral wound 4 inch", 95_000, 260_000),
    ("Elektroda las E6013 (kg)", 32_000, 70_000),
    ("Cat epoxy abu-abu (galon)", 210_000, 480_000),
    ("V-belt B-52", 38_000, 95_000),
    ("Sensor proximity induktif", 180_000, 520_000),
]
FONTS = [("Helvetica", "Helvetica-Bold"), ("Times-Roman", "Times-Bold"), ("Courier", "Courier-Bold")]


def fmt(v: int, style: int) -> str:
    s = f"{v:,}"
    if style == 0:
        return "Rp " + s.replace(",", ".")
    if style == 1:
        return s.replace(",", ".")
    return s + ".00"


def make_invoice(seed: int) -> tuple[dict, ExtractedDocument]:
    rnd = random.Random(seed)
    n_items = rnd.randint(2, 8)
    items = []
    for prod, lo, hi in rnd.sample(PRODUCTS, n_items):
        unit = rnd.randrange(lo, hi, 500)
        qty = rnd.choice([1, 1, 2, 3, 4, 5, 10, 12, 20, 25])
        items.append(LineItem(name=prod, qty=qty, unit_price=unit, price=unit * qty))
    subtotal = sum(i.price for i in items)
    discount = rnd.choice([0, 0, 0, round(subtotal * rnd.choice([0.02, 0.05, 0.1]) / 100) * 100])
    tax = round((subtotal - discount) * 0.11)
    total = subtotal - discount + tax
    doc = ExtractedDocument(
        items=items,
        subtotal=ScalarValue(value=subtotal),
        tax=ScalarValue(value=tax),
        total=ScalarValue(value=total),
        discount=ScalarValue(value=discount) if discount else None,
    )
    spec = {
        "seed": seed,
        "seller": rnd.choice(SELLERS),
        "buyer": rnd.choice(BUYERS),
        "number": f"INV/{rnd.randint(2025, 2026)}/{rnd.randint(1, 12):02d}/{rnd.randint(1, 999):04d}",
        "date": f"{rnd.randint(1, 28):02d}/{rnd.randint(1, 12):02d}/2026",
        "money_style": rnd.randint(0, 2),
        "font": rnd.randint(0, 2),
        "qty_first": rnd.random() < 0.3,
        "x_shift": rnd.randint(-15, 15),
    }
    return spec, doc


def render_pdf(spec: dict, doc: ExtractedDocument, path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    reg, bold = FONTS[spec["font"]]
    st = spec["money_style"]
    W, H = A4
    xs = spec["x_shift"]
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    c.setTitle(f"Faktur sintetis {spec['number']}")
    c.setFont(bold, 16)
    c.drawString(50 + xs, H - 60, spec["seller"])
    c.setFont(reg, 9)
    c.drawString(50 + xs, H - 76, "Dokumen sintetis untuk demo, bukan transaksi nyata")
    c.setFont(bold, 20)
    c.drawRightString(W - 50, H - 60, "FAKTUR")
    c.setFont(reg, 10)
    c.drawRightString(W - 50, H - 80, f"Nomor: {spec['number']}")
    c.drawRightString(W - 50, H - 94, f"Tanggal: {spec['date']}")
    c.drawString(50 + xs, H - 120, "Kepada:")
    c.setFont(bold, 10)
    c.drawString(50 + xs, H - 134, spec["buyer"])

    y = H - 175
    cols = (
        [("Qty", 50 + xs), ("Deskripsi", 90 + xs), ("Harga Satuan", 360), ("Jumlah", W - 50)]
        if spec["qty_first"]
        else [("Deskripsi", 50 + xs), ("Qty", 290), ("Harga Satuan", 360), ("Jumlah", W - 50)]
    )
    c.setFont(bold, 10)
    for name, x in cols:
        if name in ("Harga Satuan", "Jumlah"):
            c.drawRightString(x if name == "Jumlah" else x + 80, y, name)
        else:
            c.drawString(x, y, name)
    c.line(50 + xs, y - 6, W - 50, y - 6)
    c.setFont(reg, 10)
    y -= 24
    for it in doc.items:
        for name, x in cols:
            if name == "Qty":
                c.drawString(x, y, str(it.qty))
            elif name == "Deskripsi":
                c.drawString(x, y, it.name)
            elif name == "Harga Satuan":
                c.drawRightString(x + 80, y, fmt(it.unit_price or 0, st))
            else:
                c.drawRightString(x, y, fmt(it.price or 0, st))
        y -= 20
    c.line(300, y + 8, W - 50, y + 8)
    y -= 12
    rows = [("Subtotal", doc.value("subtotal"))]
    if doc.discount:
        rows.append(("Diskon", doc.value("discount")))
    rows += [("PPN 11%", doc.value("tax")), ("TOTAL", doc.value("total"))]
    for label, v in rows:
        c.setFont(bold if label == "TOTAL" else reg, 11 if label == "TOTAL" else 10)
        c.drawString(320, y, label)
        c.drawRightString(W - 50, y, fmt(v or 0, st))
        y -= 18
    c.setFont(reg, 8)
    c.drawString(50 + xs, 60, "Pembayaran via transfer bank. Terima kasih.")
    c.showPage()
    c.save()


def build(out_dir: Path, seeds: range) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for seed in seeds:
        spec, doc = make_invoice(seed)
        name = f"faktur-{seed:04d}"
        render_pdf(spec, doc, out_dir / f"{name}.pdf")
        (out_dir / f"{name}.json").write_text(json.dumps(doc.model_dump(mode="json"), indent=1))
        index.append({"id": name, "seed": seed, "pdf": f"{name}.pdf", "truth": f"{name}.json"})
    return index
