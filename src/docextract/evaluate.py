"""Metrics: field-F1, table accuracy, review rate, with bootstrap CIs.

Definitions (fixed before the test split was run, see docs/EVALUASI.md):
- Field: a (document, field) pair for the 7 scalar fields. TP when the
  predicted amount equals the ground truth (any listed alternative);
  a wrong value counts as both FP and FN; a value where none exists is FP.
- Row (table): predicted and true items are matched one-to-one. Lenient
  match = same price and name similarity >= 0.8; strict = same price,
  identical normalised name and same quantity when the truth has one.
- Table correct: every true row matched and no extra row (lenient).
- Document correct: all 7 fields right and table correct.
- Review: document has at least one validation issue.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .schema import SCALAR_FIELDS, ExtractedDocument, LineItem
from .text import norm_name, similarity

NAME_SIM = 0.8


@dataclass
class DocScore:
    doc_id: str
    field_tp: dict[str, int] = field(default_factory=dict)
    field_fp: dict[str, int] = field(default_factory=dict)
    field_fn: dict[str, int] = field(default_factory=dict)
    rows_gt: int = 0
    rows_pred: int = 0
    rows_tp: int = 0
    rows_tp_strict: int = 0
    qty_checked: int = 0
    qty_right: int = 0
    fields_correct: bool = False
    table_correct: bool = False
    doc_correct: bool = False
    routed: bool = False
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _match_rows(pred: list[LineItem], gt: list[LineItem], strict: bool) -> int:
    pairs = []
    for i, p in enumerate(pred):
        for j, g in enumerate(gt):
            if p.price != g.price:
                continue
            if strict:
                if norm_name(p.name) != norm_name(g.name):
                    continue
                if g.qty is not None and p.qty != g.qty:
                    continue
                sim = 1.0
            else:
                sim = similarity(p.name, g.name)
                if sim < NAME_SIM:
                    continue
            pairs.append((-sim, i, j))
    pairs.sort()
    used_p: set[int] = set()
    used_g: set[int] = set()
    for _, i, j in pairs:
        if i in used_p or j in used_g:
            continue
        used_p.add(i)
        used_g.add(j)
    return len(used_p)


def score_document(
    doc_id: str,
    pred: ExtractedDocument,
    gt: ExtractedDocument,
    alts: dict[str, list[int]],
    issues: list[str],
) -> DocScore:
    s = DocScore(doc_id=doc_id)
    all_ok = True
    for f in SCALAR_FIELDS:
        p = pred.value(f)
        options = alts.get(f, [])
        tp = int(p is not None and p in options)
        fp = int(p is not None and not tp)
        fn = int(bool(options) and not tp)
        s.field_tp[f], s.field_fp[f], s.field_fn[f] = tp, fp, fn
        if fp or fn:
            all_ok = False
    s.fields_correct = all_ok
    s.rows_gt, s.rows_pred = len(gt.items), len(pred.items)
    s.rows_tp = _match_rows(pred.items, gt.items, strict=False)
    s.rows_tp_strict = _match_rows(pred.items, gt.items, strict=True)
    s.table_correct = s.rows_tp == s.rows_gt == s.rows_pred
    for g in gt.items:
        if g.qty is None:
            continue
        s.qty_checked += 1
        if any(p.price == g.price and p.qty == g.qty and similarity(p.name, g.name) >= NAME_SIM for p in pred.items):
            s.qty_right += 1
    s.doc_correct = s.fields_correct and s.table_correct
    s.issues = list(issues)
    s.routed = bool(issues)
    return s


def _f1(tp: int, fp: int, fn: int) -> float | None:
    if tp + fp + fn == 0:
        return None
    return 2 * tp / (2 * tp + fp + fn)


def aggregate(scores: list[DocScore]) -> dict:
    out: dict = {"n_docs": len(scores)}
    per_field = {}
    tp_all = fp_all = fn_all = 0
    for f in SCALAR_FIELDS:
        tp = sum(s.field_tp[f] for s in scores)
        fp = sum(s.field_fp[f] for s in scores)
        fn = sum(s.field_fn[f] for s in scores)
        tp_all, fp_all, fn_all = tp_all + tp, fp_all + fp, fn_all + fn
        per_field[f] = {"tp": tp, "fp": fp, "fn": fn, "support": tp + fn, "f1": _f1(tp, fp, fn)}
    out["per_field"] = per_field
    out["field_micro_f1"] = _f1(tp_all, fp_all, fn_all)
    f1s = [v["f1"] for v in per_field.values() if v["support"] > 0 and v["f1"] is not None]
    out["field_macro_f1"] = sum(f1s) / len(f1s) if f1s else None
    rg = sum(s.rows_gt for s in scores)
    rp = sum(s.rows_pred for s in scores)
    rt = sum(s.rows_tp for s in scores)
    rts = sum(s.rows_tp_strict for s in scores)
    out["row_precision"] = rt / rp if rp else None
    out["row_recall"] = rt / rg if rg else None
    out["row_f1"] = 2 * rt / (rg + rp) if rg + rp else None
    out["row_f1_strict"] = 2 * rts / (rg + rp) if rg + rp else None
    qc = sum(s.qty_checked for s in scores)
    out["qty_accuracy"] = sum(s.qty_right for s in scores) / qc if qc else None
    n = len(scores) or 1
    out["table_doc_accuracy"] = sum(s.table_correct for s in scores) / n
    out["doc_accuracy"] = sum(s.doc_correct for s in scores) / n
    routed = sum(s.routed for s in scores)
    auto = [s for s in scores if not s.routed]
    out["review_rate"] = routed / n
    out["auto_accepted"] = len(auto)
    out["auto_accept_accuracy"] = sum(s.doc_correct for s in auto) / len(auto) if auto else None
    out["auto_correct_share"] = sum(s.doc_correct for s in auto) / n
    routed_docs = [s for s in scores if s.routed]
    out["caught_error_share"] = sum(not s.doc_correct for s in routed_docs) / max(
        1, sum(not s.doc_correct for s in scores)
    )
    return out


BOOT_METRICS = (
    "field_micro_f1",
    "field_macro_f1",
    "row_f1",
    "row_f1_strict",
    "table_doc_accuracy",
    "doc_accuracy",
    "review_rate",
    "auto_accept_accuracy",
)


def bootstrap(runs: dict[str, list[DocScore]], n_boot: int = 2000, seed: int = 42) -> dict:
    """Percentile CIs per run and paired CIs of differences between runs.

    All runs must score the same documents in the same order; each resample
    draws the same document indices for every run (paired bootstrap).
    """
    import numpy as np

    names = list(runs)
    n = len(runs[names[0]])
    for r in names:
        assert [s.doc_id for s in runs[r]] == [s.doc_id for s in runs[names[0]]]
    rng = np.random.default_rng(seed)
    samples: dict[str, dict[str, list[float]]] = {r: {m: [] for m in BOOT_METRICS} for r in names}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        for r in names:
            agg = aggregate([runs[r][i] for i in idx])
            for m in BOOT_METRICS:
                v = agg[m]
                samples[r][m].append(float("nan") if v is None else v)

    def ci(vals: list[float]) -> list[float | None]:
        a = np.array(vals, dtype=float)
        a = a[~np.isnan(a)]
        if a.size == 0:
            return [None, None]
        return [round(float(np.percentile(a, 2.5)), 4), round(float(np.percentile(a, 97.5)), 4)]

    out: dict = {"n_boot": n_boot, "seed": seed, "ci": {}, "diff": {}}
    for r in names:
        out["ci"][r] = {m: ci(samples[r][m]) for m in BOOT_METRICS}
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            key = f"{b} - {a}"
            out["diff"][key] = {}
            for m in BOOT_METRICS:
                d = np.array(samples[b][m]) - np.array(samples[a][m])
                out["diff"][key][m] = ci(list(d))
    return out
