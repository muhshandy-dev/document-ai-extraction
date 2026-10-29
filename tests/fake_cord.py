"""Tiny receipts in the exact CORD-v2 parquet format, for offline end-to-end tests.

Each row has `image` {bytes, path} and `ground_truth` (JSON string with
gt_parse, meta and valid_line word quads), like naver-clova-ix/cord-v2.
"""

from __future__ import annotations

import io
import json
import random
from pathlib import Path

MENU = ["NASI GORENG", "ES TEH", "AYAM BAKAR", "KOPI SUSU", "MIE AYAM", "TEH TARIK", "ROTI BAKAR", "JUS JERUK"]


def _fmt(v: int) -> str:
    return f"{v:,}"


def make_receipt(seed: int) -> tuple[bytes, dict]:
    from PIL import Image, ImageDraw, ImageFont

    rnd = random.Random(seed)
    font = ImageFont.load_default(size=26)
    width, height = 640, 900
    im = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(im)
    lines: list[dict] = []
    y = 40

    def put(tokens: list[tuple[str, float, str, int]]) -> None:
        """tokens: (text, x, category, is_key); one valid_line per category run."""
        nonlocal y
        groups: dict[str, list[dict]] = {}
        for text, x, cat, key in tokens:
            draw.text((x, y), text, fill=0, font=font)
            x0, y0, x1, y1 = draw.textbbox((x, y), text, font=font)
            quad = {"x1": x0, "y1": y0, "x2": x1, "y2": y0, "x3": x1, "y3": y1, "x4": x0, "y4": y1}
            groups.setdefault(cat, []).append({"quad": quad, "is_key": key, "row_id": len(lines), "text": text})
        for cat, words in groups.items():
            lines.append({"words": words, "category": cat, "group_id": len(lines), "sub_group_id": 0})
        y += 44

    put([("WARUNG", 40, "store", 0), ("CONTOH", 170, "store", 0)])
    menu = []
    for name in rnd.sample(MENU, rnd.randint(2, 4)):
        qty = rnd.randint(1, 3)
        price = rnd.choice([8, 12, 15, 18, 25, 30]) * 1000 * qty
        toks = [(str(qty), 40, "menu.cnt", 0)]
        x = 90
        for part in name.split():
            toks.append((part, x, "menu.nm", 0))
            x += 24 * len(part) // 1.6 + 20
        toks.append((_fmt(price), 480, "menu.price", 0))
        put(toks)
        menu.append({"nm": name, "cnt": str(qty), "price": _fmt(price)})
    sub = sum(int(m["price"].replace(",", "")) for m in menu)
    tax = sub // 10
    total = sub + tax
    cash = (total // 50000 + 1) * 50000
    put([("SUBTOTAL", 40, "sub_total.subtotal_price", 1), (_fmt(sub), 480, "sub_total.subtotal_price", 0)])
    put([("PB1", 40, "sub_total.tax_price", 1), (_fmt(tax), 480, "sub_total.tax_price", 0)])
    put([("TOTAL", 40, "total.total_price", 1), (_fmt(total), 480, "total.total_price", 0)])
    put([("CASH", 40, "total.cashprice", 1), (_fmt(cash), 480, "total.cashprice", 0)])
    put([("CHANGE", 40, "total.changeprice", 1), (_fmt(cash - total), 480, "total.changeprice", 0)])
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    gt = {
        "gt_parse": {
            "menu": menu,
            "sub_total": {"subtotal_price": _fmt(sub), "tax_price": _fmt(tax)},
            "total": {"total_price": _fmt(total), "cashprice": _fmt(cash), "changeprice": _fmt(cash - total)},
        },
        "meta": {"version": "fake", "split": "", "image_id": seed, "image_size": {"width": width, "height": height}},
        "valid_line": lines,
        "roi": {},
        "repeating_symbol": [],
        "dontcare": [],
    }
    return buf.getvalue(), gt


def write_fake_cord(out: Path, sizes: dict[str, int]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    out.mkdir(parents=True, exist_ok=True)
    seed = 0
    for split, n in sizes.items():
        rows = []
        for _ in range(n):
            img, gt = make_receipt(seed)
            gt["meta"]["split"] = split
            rows.append({"image": {"bytes": img, "path": f"{seed}.png"}, "ground_truth": json.dumps(gt)})
            seed += 1
        pq.write_table(pa.Table.from_pylist(rows), out / f"{split}-00000-of-00001.parquet")
