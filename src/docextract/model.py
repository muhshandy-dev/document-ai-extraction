"""Approach N: multinomial logistic regression over word features.

Training uses scikit-learn; prediction (here and in the browser) uses the
exported weight table, so the evaluated model is exactly the shipped one.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from .cord import LABELS
from .features import page_features
from .layout import Page

WEIGHT_DECIMALS = 4


class LinearModel:
    def __init__(self, labels: list[str], bias: list[float], weights: dict[str, list[float]], meta: dict):
        self.labels = labels
        self.bias = bias
        self.weights = weights
        self.meta = meta

    def predict_page(self, page: Page) -> tuple[list[str], list[float]]:
        labels: list[str] = []
        probs: list[float] = []
        k = len(self.labels)
        for feats in page_features(page):
            scores = list(self.bias)
            for f in feats:
                w = self.weights.get(f)
                if w is not None:
                    for c in range(k):
                        scores[c] += w[c]
            best = max(range(k), key=lambda c: (scores[c], -c))
            mx = scores[best]
            z = sum(math.exp(s - mx) for s in scores)
            labels.append(self.labels[best])
            probs.append(1.0 / z)
        return labels, probs

    def to_json(self) -> dict:
        return {"labels": self.labels, "bias": self.bias, "weights": self.weights, "meta": self.meta}

    @classmethod
    def load(cls, path: Path) -> LinearModel:
        d = json.loads(Path(path).read_text())
        return cls(d["labels"], d["bias"], d["weights"], d.get("meta", {}))


def train(pages: list[Page], gold: list[list[str]], c: float = 1.0, min_count: int = 2, seed: int = 0) -> LinearModel:
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression

    X_feats: list[list[str]] = []
    y: list[str] = []
    for page, labs in zip(pages, gold, strict=True):
        feats = page_features(page)
        assert len(feats) == len(labs)
        X_feats.extend(feats)
        y.extend(labs)
    counts = Counter(f for fs in X_feats for f in fs)
    keep = {f for f, n in counts.items() if n >= min_count}
    rows = [{f: 1 for f in fs if f in keep} for fs in X_feats]
    vec = DictVectorizer(sparse=True)
    X = vec.fit_transform(rows)
    clf = LogisticRegression(C=c, max_iter=3000, random_state=seed)
    clf.fit(X, y)

    classes = list(clf.classes_)
    order = [classes.index(lab) for lab in LABELS if lab in classes]
    labels = [classes[i] for i in order]
    coef = clf.coef_
    if coef.shape[0] == 1:  # binary edge case, never expected here
        raise ValueError("need at least three classes")
    names = vec.get_feature_names_out()
    weights: dict[str, list[float]] = {}
    for j, name in enumerate(names):
        col = [round(float(coef[i, j]), WEIGHT_DECIMALS) for i in order]
        if any(v != 0.0 for v in col):
            weights[str(name)] = col
    bias = [round(float(clf.intercept_[i]), WEIGHT_DECIMALS) for i in order]
    meta = {
        "algorithm": "LogisticRegression (multinomial, L2, lbfgs)",
        "C": c,
        "min_count": min_count,
        "n_train_words": len(y),
        "n_features": len(weights),
        "label_counts": dict(Counter(y)),
    }
    return LinearModel(labels, bias, weights, meta)
