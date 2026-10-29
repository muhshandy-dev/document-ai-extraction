from docextract.evaluate import aggregate, bootstrap, score_document
from docextract.schema import ExtractedDocument, LineItem, ScalarValue


def mk(total=None, tax=None, items=()):
    return ExtractedDocument(
        items=list(items),
        total=ScalarValue(value=total) if total is not None else None,
        tax=ScalarValue(value=tax) if tax is not None else None,
    )


def test_field_counts_wrong_value_is_fp_and_fn():
    gt = mk(total=100, items=[LineItem(name="Teh", price=100)])
    s = score_document("d", mk(total=90, tax=5, items=[LineItem(name="TEH", price=100)]), gt, {"total": [100]}, [])
    assert (s.field_tp["total"], s.field_fp["total"], s.field_fn["total"]) == (0, 1, 1)
    assert (s.field_tp["tax"], s.field_fp["tax"], s.field_fn["tax"]) == (0, 1, 0)
    assert s.rows_tp == 1 and s.table_correct and not s.doc_correct


def test_alternative_values_count_as_correct():
    s = score_document("d", mk(total=95), mk(total=100), {"total": [100, 95]}, [])
    assert s.field_tp["total"] == 1


def test_row_matching_lenient_vs_strict():
    gt = mk(items=[LineItem(name="Oli hidrolik", qty=2, price=500)])
    pred = mk(items=[LineItem(name="0li hidrolik", qty=2, price=500)])
    s = score_document("d", pred, gt, {}, [])
    assert s.rows_tp == 1 and s.rows_tp_strict == 0


def test_aggregate_and_bootstrap_are_deterministic():
    gt = mk(total=100, items=[LineItem(name="A", price=100)])
    good = score_document("a", gt, gt, {"total": [100]}, [])
    bad = score_document("b", mk(total=1), gt, {"total": [100]}, ["TOTAL_MISMATCH"])
    agg = aggregate([good, bad])
    assert agg["review_rate"] == 0.5 and agg["auto_accept_accuracy"] == 1.0 and agg["caught_error_share"] == 1.0
    good_b = score_document("b", gt, gt, {"total": [100]}, [])
    b1 = bootstrap({"x": [good, bad], "y": [good, good_b]}, n_boot=50, seed=1)
    b2 = bootstrap({"x": [good, bad], "y": [good, good_b]}, n_boot=50, seed=1)
    assert b1 == b2
    assert "y - x" in b1["diff"]
