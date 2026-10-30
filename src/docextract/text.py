"""Text normalisation shared by extractors and the evaluator.

Every function here has a twin in web/src/core/text.ts; the parity
fixtures in tests/fixtures keep both implementations in sync.
"""

from __future__ import annotations

import re
import unicodedata

_TOKEN_RE = re.compile(r"[0-9][0-9.,]*[0-9]|[0-9]")
_GROUPED_RE = re.compile(r"^[0-9]{1,3}(?:[.,][0-9]{3})+(?:[.,][0-9]{2})?$")
_DECIMAL_RE = re.compile(r"^([0-9]+)[.,][0-9]{1,2}$")


MAX_AMOUNT = 10**12
MAX_COUNT = 10_000


def norm_space(text: str) -> str:
    return " ".join(text.split())


def norm_name(text: str) -> str:
    """Upper-case, accent-free, single-spaced text used for matching names."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return norm_space(text.upper())


def _token_value(token: str) -> int:
    if _GROUPED_RE.match(token):
        parts = re.split(r"[.,]", token)
        if len(parts[-1]) == 2:  # trailing cents, e.g. 12,500.00
            parts = parts[:-1]
        return int("".join(parts))
    dec = _DECIMAL_RE.match(token)
    if dec:
        return int(dec.group(1))
    return int(re.sub(r"[^0-9]", "", token))


def amount_tokens(text: str) -> list[str]:
    """Numeric tokens in reading order ('Rp 45.000 x2' -> ['45.000', '2'])."""
    return _TOKEN_RE.findall(text)


def parse_amount(text: str | None) -> int | None:
    """Money value of the longest numeric token in `text`, or None.

    The words of one field are joined without spaces before parsing, so
    an OCR split such as '45' ',500' still reads as 45500.
    """
    if not text:
        return None
    tokens = amount_tokens(text.replace(" ", ""))
    if not tokens:
        return None
    token = max(tokens, key=len)
    value = _token_value(token)
    # Longer numbers are IDs or phone numbers, not money (and would overflow
    # exact integers in the browser).
    return value if value < MAX_AMOUNT else None


def parse_count(text: str | None) -> int | None:
    """Parse an item quantity such as '2', 'x2', '2X', '2 pcs'."""
    if not text:
        return None
    match = re.search(r"[0-9]+", text)
    if not match or len(match.group(0)) > 5:
        return None
    value = int(match.group(0))
    return value if value <= MAX_COUNT else None


def is_money(text: str) -> bool:
    """True for tokens that look like a price: grouped digits or >= 3 digits."""
    t = re.sub(r"^(RP\.?|IDR)", "", text.strip().upper()).strip("()-: ")
    return bool(_GROUPED_RE.match(t) or re.fullmatch(r"[0-9]{3,}", t))


# Letters Tesseract often reads in place of digits inside amounts.
OCR_DIGIT_FIX = {
    "O": "0",
    "o": "0",
    "D": "0",
    "Q": "0",
    "I": "1",
    "l": "1",
    "i": "1",
    "|": "1",
    "S": "5",
    "B": "8",
    "Z": "2",
}


def fix_ocr_token(text: str) -> str:
    """Repair an amount such as '1O.0O0' -> '10.000'. Other tokens are returned unchanged.

    Only tokens made of digits, '.', ',' and look-alike letters qualify, with
    at least two digits. With a separator ('1O.0O0') there may be as many
    look-alikes as digits; without one ('1O00') the token needs four or more
    characters and at most one look-alike per two digits, so codes like 'B12'
    stay as they are.
    """
    digits = confusable = 0
    sep = False
    for ch in text:
        if "0" <= ch <= "9":
            digits += 1
        elif ch in OCR_DIGIT_FIX:
            confusable += 1
        elif ch in ".,":
            sep = True
        else:
            return text
    if confusable == 0 or digits < 2:
        return text
    if sep and confusable > digits:
        return text
    if not sep and (confusable * 2 > digits or digits + confusable < 4):
        return text
    return "".join(OCR_DIGIT_FIX.get(ch, ch) for ch in text)


def word_shape(text: str) -> str:
    """Collapse characters into classes: A upper, a lower, 0 digit, others kept."""
    out: list[str] = []
    for ch in text[:12]:
        if "0" <= ch <= "9":
            c = "0"
        elif "A" <= ch <= "Z":
            c = "A"
        elif "a" <= ch <= "z":
            c = "a"
        else:
            c = ch
        if not out or out[-1] != c:
            out.append(c)
    return "".join(out)


def similarity(a: str, b: str) -> float:
    """1 - normalised Levenshtein distance between norm_name(a) and norm_name(b)."""
    a, b = norm_name(a), norm_name(b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return 1.0 - prev[-1] / max(len(a), len(b))
