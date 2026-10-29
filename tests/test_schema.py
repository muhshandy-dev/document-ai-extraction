from docextract.schema import ExtractedDocument, LineItem, ScalarValue, validate_document


def doc(**kw):
    items = kw.pop("items", [LineItem(name="A", price=10000)])
    return ExtractedDocument(items=items, **{k: ScalarValue(value=v, confidence=0.99) for k, v in kw.items()})


def codes(d, **kw):
    return {i.code for i in validate_document(d, **kw)}


def test_consistent_document_has_no_issues():
    assert codes(doc(subtotal=10000, tax=1000, total=11000, cash=20000, change=9000)) == set()


def test_tax_inclusive_total_is_accepted():
    assert codes(doc(subtotal=10000, tax=909, total=10000)) == set()


def test_detects_mismatches():
    assert "TOTAL_MISMATCH" in codes(doc(subtotal=10000, total=12345))
    assert "CASH_CHANGE" in codes(doc(subtotal=10000, total=10000, cash=20000, change=5000))
    assert "ITEMS_SUM" in codes(doc(subtotal=9000, total=9000))
    assert "TOTAL_MISSING" in codes(doc(subtotal=10000))


def test_low_confidence_only_with_threshold():
    d = ExtractedDocument(
        items=[LineItem(name="A", price=100, confidence=0.4)], total=ScalarValue(value=100, confidence=0.9)
    )
    assert "LOW_CONF" not in codes(d)
    assert "LOW_CONF" in codes(d, min_conf=0.5)


def test_pydantic_rejects_negative_amounts():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ScalarValue(value=-1)
