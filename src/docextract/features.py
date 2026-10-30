"""Word features for approach N (text + layout). Twin: web/src/core/features.ts.

All features are binary strings, so a model is just a weight table and
the browser can reproduce scores exactly.
"""

from __future__ import annotations

from .heuristic import ALPHA, QTY, summary_field
from .layout import Page
from .text import is_money, word_shape


def _bucket(v: float, size: float, n: int) -> int:
    if size <= 0:
        return 0
    return max(0, min(n - 1, int(v / size * n)))


def page_features(page: Page) -> list[list[str]]:
    kws = [summary_field(ln) or "none" for ln in page.lines]
    first = next((i for i, k in enumerate(kws) if k != "none"), len(page.lines))
    feats: list[list[str]] = []
    for li, line in enumerate(page.lines):
        words = line.words
        n = len(words)
        money = [is_money(w.text) for w in words]
        n_money = sum(money)
        kw = kws[li]
        kw_prev = kws[li - 1] if li > 0 else "bos"
        kw_next = kws[li + 1] if li + 1 < len(kws) else "eos"
        rel = max(-3, min(3, li - first)) if first < len(page.lines) else -9
        region = "above" if li < first else ("at" if li == first else "below")
        head = words[0].text.lower()[:8]
        indent = _bucket(line.x0, page.width, 20)
        money_right = 0
        money_rank: list[int] = [0] * n
        for j in range(n - 1, -1, -1):
            if money[j]:
                money_rank[j] = money_right
                money_right += 1
        for j, w in enumerate(words):
            t = w.text
            lo = t.lower()[:15]
            ridx = min(n - 1 - j, 3)
            m = "1" if money[j] else "0"
            prev = words[j - 1].text.lower()[:10] if j > 0 else "<s>"
            nxt = words[j + 1].text.lower()[:10] if j + 1 < n else "</s>"
            f = [
                "bias",
                "w=" + lo,
                "shape=" + word_shape(t),
                "p3=" + lo[:3],
                "s3=" + lo[-3:],
                "money=" + m,
                "len=" + str(min(len(t), 10)),
                "xb=" + str(_bucket((w.x0 + w.x1) / 2, page.width, 10)),
                "yb=" + str(_bucket((w.y0 + w.y1) / 2, page.height, 10)),
                "ridx=" + str(ridx),
                "lidx=" + str(min(j, 3)),
                "nw=" + str(min(n, 6)),
                "nm=" + str(min(n_money, 3)),
                "kw=" + kw,
                "kwp=" + kw_prev,
                "kwn=" + kw_next,
                "rel=" + str(rel),
                "region=" + region,
                "indent=" + str(indent),
                "head=" + head,
                "prev=" + prev,
                "next=" + nxt,
                "pshape=" + (word_shape(words[j - 1].text) if j > 0 else "<s>"),
                "nshape=" + (word_shape(words[j + 1].text) if j + 1 < n else "</s>"),
                "kw|ridx|m=" + kw + "|" + str(ridx) + "|" + m,
                "region|ridx|m=" + region + "|" + str(ridx) + "|" + m,
                "kwp|m=" + kw_prev + "|" + m,
                "head|m=" + head + "|" + m,
            ]
            if money[j]:
                f.append("mrank=" + str(min(money_rank[j], 2)))
                f.append("kw|mrank=" + kw + "|" + str(min(money_rank[j], 2)))
            if QTY.match(t.strip()):
                f.append("qty")
                f.append("qty|lidx=" + str(min(j, 3)))
            if ALPHA.search(t):
                f.append("alpha")
            feats.append(f)
    return feats
