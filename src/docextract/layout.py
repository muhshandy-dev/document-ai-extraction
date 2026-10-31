"""Layout parsing: OCR words with boxes -> reading-order lines.

Mirrors web/src/core/layout.ts. Only plain float arithmetic in a fixed
order is used so both languages give identical groupings.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .text import fix_ocr_token


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float = 100.0
    label: str = "O"

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def h(self) -> float:
        return max(self.y1 - self.y0, 1.0)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "box": [round(self.x0, 1), round(self.y0, 1), round(self.x1, 1), round(self.y1, 1)],
            "conf": round(self.conf, 1),
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Word:
        x0, y0, x1, y1 = d["box"]
        return cls(d["text"], x0, y0, x1, y1, d.get("conf", 100.0), d.get("label", "O"))


@dataclass
class Line:
    words: list[Word] = field(default_factory=list)
    y0: float = 0.0
    y1: float = 0.0

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def x0(self) -> float:
        return min(w.x0 for w in self.words)

    @property
    def x1(self) -> float:
        return max(w.x1 for w in self.words)


@dataclass
class Page:
    width: float
    height: float
    lines: list[Line]

    @property
    def words(self) -> list[Word]:
        return [w for line in self.lines for w in line.words]


LOOKBACK = 6
MIN_OVERLAP = 0.5


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return min(a1, b1) - max(a0, b0)


def group_lines(words: list[Word], width: float, height: float) -> Page:
    """Greedy vertical-overlap clustering of words into text lines.

    Amounts misread with look-alike letters are repaired first (fix_ocr_token).
    A word joins the recent line whose y-band overlaps it the most, if the
    overlap covers at least MIN_OVERLAP of the smaller height. The band is
    the running mean of member tops and bottoms, so slightly skewed rows
    still group together without one tall word swallowing two rows.
    """
    fixed = []
    for w in words:
        if not w.text.strip():
            continue
        t = fix_ocr_token(w.text)
        fixed.append(w if t == w.text else replace(w, text=t))
    order = sorted(fixed, key=lambda w: (w.yc, w.x0))
    lines: list[Line] = []
    sums: list[list[float]] = []  # per line: [sum_y0, sum_y1, n]
    for w in order:
        best, best_ov = -1, 0.0
        start = max(0, len(lines) - LOOKBACK)
        for i in range(start, len(lines)):
            line = lines[i]
            ov = _overlap(w.y0, w.y1, line.y0, line.y1)
            denom = min(w.h, max(line.y1 - line.y0, 1.0))
            ratio = ov / denom
            if ratio > best_ov:
                best, best_ov = i, ratio
        if best >= 0 and best_ov >= MIN_OVERLAP:
            s = sums[best]
            s[0] += w.y0
            s[1] += w.y1
            s[2] += 1
            line = lines[best]
            line.words.append(w)
            line.y0 = s[0] / s[2]
            line.y1 = s[1] / s[2]
        else:
            lines.append(Line([w], w.y0, w.y1))
            sums.append([w.y0, w.y1, 1.0])
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    lines.sort(key=lambda ln: ((ln.y0 + ln.y1) / 2, ln.x0))
    return Page(width, height, lines)
