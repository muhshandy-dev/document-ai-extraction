"""Approach H: keyword and regex rules over OCR lines (no learning).

The rules label words exactly like the trained model does, with
probability 1.0, so both approaches share the same assembler and
validator. Twin: web/src/core/heuristic.ts.
"""

from __future__ import annotations

import re

from .layout import Line, Page
from .text import is_money

SUMMARY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("subtotal", re.compile(r"SUB\s*-?\s*TOTAL|SUBTTL|SUB\s*TTL|SUBTOT", re.ASCII)),
    ("change", re.compile(r"CHANGE|KEMBALI", re.ASCII)),
    ("cash", re.compile(r"CASH|TUNAI", re.ASCII)),
    ("tax", re.compile(r"TAX|PB\s*1|PPN|PAJAK|VAT", re.ASCII)),
    ("service", re.compile(r"SERVICE|SERV\b|SVC|S/C|\bSC\b", re.ASCII)),
    ("discount", re.compile(r"DISC|DISKON|POTONGAN|PROMO", re.ASCII)),
    ("total", re.compile(r"TOTAL|\bTTL\b|JUMLAH|GRAND|TAGIHAN|AMOUNT\s*DUE", re.ASCII)),
)
NOT_TOTAL = re.compile(r"TOTAL\s*(ITEM|QTY|QTT|PCS|ITM)|ITEMS?\b|\bQTY\b", re.ASCII)
HEADER = re.compile(
    r"\bTEL|TELP|PHONE|NPWP|\bNO\b|TABLE|MEJA|KASIR|CASHIER|DATE|TANGGAL|JAM|TIME|BILL|ORDER|"
    r"[0-9]{1,2}[:/.-][0-9]{1,2}[:/.-][0-9]{2,4}|[0-9]{1,2}:[0-9]{2}",
    re.ASCII,
)
QTY = re.compile(r"^[xX]?[0-9]{1,3}[xX]?$", re.ASCII)
ALPHA = re.compile(r"[A-Za-z]{2,}", re.ASCII)
SKIP_TOKENS = {"RP", "RP.", "IDR", "X", "@", "-", ":"}


def summary_field(line: Line) -> str | None:
    up = line.text.upper()
    for field, rx in SUMMARY_RULES:
        if rx.search(up):
            if field == "total" and NOT_TOTAL.search(up):
                return None
            return field
    return None


def _is_text(t: str) -> bool:
    return bool(ALPHA.search(t)) and t.strip().upper() not in SKIP_TOKENS


def _money_idx(line: Line) -> list[int]:
    return [i for i, w in enumerate(line.words) if is_money(w.text)]


def label_page(page: Page) -> list[str]:
    labels_per_line: list[list[str]] = [["O"] * len(ln.words) for ln in page.lines]
    fields = [summary_field(ln) for ln in page.lines]
    first_summary = next((i for i, f in enumerate(fields) if f), len(page.lines))

    # summary fields: last money word on the keyword line, else on the next line
    for i, f in enumerate(fields):
        if not f:
            continue
        money = _money_idx(page.lines[i])
        if money:
            labels_per_line[i][money[-1]] = f
        elif i + 1 < len(page.lines) and not fields[i + 1]:
            nxt = _money_idx(page.lines[i + 1])
            if nxt:
                labels_per_line[i + 1][nxt[-1]] = f

    # menu rows above the first summary line
    pending: int | None = None  # previous line that holds only a name
    for i in range(first_summary):
        line = page.lines[i]
        if HEADER.search(line.text.upper()):
            pending = None
            continue
        money = _money_idx(line)
        has_name = any(ALPHA.search(w.text) for w in line.words if not is_money(w.text))
        if not money:
            pending = i if has_name else None
            continue
        last_alpha = max((j for j, w in enumerate(line.words) if _is_text(w.text)), default=-1)
        labs = labels_per_line[i]
        price = money[-1]
        labs[price] = "menu.price"
        if len(money) >= 2 and money[-2] > last_alpha:
            labs[money[-2]] = "menu.unitprice"
        # name/qty words end at the first money token after the last word with letters
        trailing = [j for j in money if j > last_alpha]
        first_money = trailing[0] if trailing else money[-1]
        for j, w in enumerate(line.words):
            if labs[j] != "O" or j > first_money:
                continue
            t = w.text.strip()
            seen_name = any(labs[k] == "menu.nm" for k in range(j))
            before_money = all(line.words[k].text.strip().upper() in SKIP_TOKENS for k in range(j + 1, first_money))
            if QTY.match(t) and (not seen_name or before_money):
                labs[j] = "menu.cnt"
            elif t.upper() in SKIP_TOKENS and not (seen_name and t.upper() == "X"):
                continue
            elif seen_name or ALPHA.search(t):
                labs[j] = "menu.nm"
        if not has_name and pending is not None:
            prev = labels_per_line[pending]
            for j, w in enumerate(page.lines[pending].words):
                if ALPHA.search(w.text):
                    prev[j] = "menu.nm"
        pending = None
    return [lab for labs in labels_per_line for lab in labs]
