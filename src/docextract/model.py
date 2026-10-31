"""Approach N (v2): linear-chain CRF over word features in reading order.

Training uses python-crfsuite. Prediction (here and in the browser,
web/src/core/model.ts) uses the exported weight table: Viterbi for the
labels and forward-backward marginals for each word's confidence, so the
evaluated model is exactly the shipped one.

Version 1 (multinomial logistic regression) is kept in git history at
commit 748fda1; its test results stay in evaluation/.
"""

from __future__ import annotations

import json
import math
import tempfile
from collections import Counter
from pathlib import Path

from .cord import LABELS
from .features import page_features
from .layout import Page

WEIGHT_DECIMALS = 4
NEG_INF = float("-inf")


def logsumexp(xs: list[float]) -> float:
    m = NEG_INF
    for x in xs:
        if x > m:
            m = x
    if m == NEG_INF:
        return NEG_INF
    s = 0.0
    for x in xs:
        s += math.exp(x - m)
    return m + math.log(s)


class CrfModel:
    """labels: K names. weights: attribute -> flat [label_index, weight, ...]. trans[i][j]: label i -> j."""

    def __init__(self, labels: list[str], weights: dict[str, list[float]], trans: list[list[float]], meta: dict):
        self.labels = labels
        self.weights = weights
        self.trans = trans
        self.meta = meta

    def emissions(self, feats: list[list[str]]) -> list[list[float]]:
        k = len(self.labels)
        out = []
        for fs in feats:
            em = [0.0] * k
            for f in fs:
                w = self.weights.get(f)
                if w is not None:
                    for i in range(0, len(w), 2):
                        em[int(w[i])] += w[i + 1]
            out.append(em)
        return out

    def viterbi(self, em: list[list[float]]) -> list[int]:
        n, k, tr = len(em), len(self.labels), self.trans
        if n == 0:
            return []
        delta = list(em[0])
        back: list[list[int]] = []
        for t in range(1, n):
            nd = [0.0] * k
            bp = [0] * k
            for y in range(k):
                best, arg = NEG_INF, 0
                for yp in range(k):
                    v = delta[yp] + tr[yp][y]
                    if v > best:
                        best, arg = v, yp
                nd[y] = best + em[t][y]
                bp[y] = arg
            delta = nd
            back.append(bp)
        last, best = 0, NEG_INF
        for y in range(k):
            if delta[y] > best:
                last, best = y, delta[y]
        path = [last]
        for bp in reversed(back):
            path.append(bp[path[-1]])
        path.reverse()
        return path

    def marginals(self, em: list[list[float]]) -> list[list[float]]:
        n, k, tr = len(em), len(self.labels), self.trans
        if n == 0:
            return []
        alpha = [list(em[0])]
        for t in range(1, n):
            prev = alpha[-1]
            alpha.append([em[t][y] + logsumexp([prev[yp] + tr[yp][y] for yp in range(k)]) for y in range(k)])
        beta = [[0.0] * k for _ in range(n)]
        for t in range(n - 2, -1, -1):
            nxt = beta[t + 1]
            beta[t] = [logsumexp([tr[y][yn] + em[t + 1][yn] + nxt[yn] for yn in range(k)]) for y in range(k)]
        log_z = logsumexp(alpha[-1])
        return [[math.exp(alpha[t][y] + beta[t][y] - log_z) for y in range(k)] for t in range(n)]

    def predict_dist(self, page: Page) -> tuple[list[str], list[float], list[list[float]]]:
        """Viterbi labels, their marginal probabilities, and the full marginals per word."""
        em = self.emissions(page_features(page))
        path = self.viterbi(em)
        marg = self.marginals(em)
        labels = [self.labels[y] for y in path]
        probs = [min(max(marg[t][y], 0.0), 1.0) for t, y in enumerate(path)]
        return labels, probs, marg

    def predict_page(self, page: Page) -> tuple[list[str], list[float]]:
        labels, probs, _ = self.predict_dist(page)
        return labels, probs

    def to_json(self) -> dict:
        return {"type": "crf", "labels": self.labels, "weights": self.weights, "trans": self.trans, "meta": self.meta}

    @classmethod
    def from_json(cls, d: dict) -> CrfModel:
        return cls(d["labels"], d["weights"], d["trans"], d.get("meta", {}))

    @classmethod
    def load(cls, path: Path) -> CrfModel:
        return cls.from_json(json.loads(Path(path).read_text()))


def train(
    pages: list[Page], gold: list[list[str]], c1: float = 0.05, c2: float = 0.1, max_iterations: int = 300
) -> CrfModel:
    import pycrfsuite

    trainer = pycrfsuite.Trainer(verbose=False)
    n_words = 0
    counts: Counter[str] = Counter()
    for page, labs in zip(pages, gold, strict=True):
        feats = page_features(page)
        assert len(feats) == len(labs)
        if not feats:
            continue
        trainer.append(feats, labs)
        n_words += len(labs)
        counts.update(labs)
    trainer.set_params({"c1": c1, "c2": c2, "max_iterations": max_iterations, "feature.possible_transitions": True})
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "crf.model")
        trainer.train(path)
        tagger = pycrfsuite.Tagger()
        tagger.open(path)
        info = tagger.info()
        known = set(tagger.labels())
        tagger.close()
    labels = [lab for lab in LABELS if lab in known]
    index = {lab: i for i, lab in enumerate(labels)}
    trans = [[0.0] * len(labels) for _ in labels]
    for (a, b), w in info.transitions.items():
        trans[index[a]][index[b]] = round(float(w), WEIGHT_DECIMALS)
    per_attr: dict[str, list[tuple[int, float]]] = {}
    for (attr, lab), w in info.state_features.items():
        w = round(float(w), WEIGHT_DECIMALS)
        if w != 0.0:
            per_attr.setdefault(attr, []).append((index[lab], w))
    weights: dict[str, list[float]] = {}
    for attr in sorted(per_attr):
        flat: list[float] = []
        for i, w in sorted(per_attr[attr]):
            flat += [i, w]
        weights[attr] = flat
    meta = {
        "algorithm": "linear-chain CRF (python-crfsuite, L-BFGS)",
        "c1": c1,
        "c2": c2,
        "max_iterations": max_iterations,
        "n_train_words": n_words,
        "n_attributes": len(weights),
        "n_state_features": sum(len(v) // 2 for v in weights.values()),
        "label_counts": dict(counts),
    }
    return CrfModel(labels, weights, trans, meta)
