"""v2 rules: OCR digit repair, arithmetic-aware field choice, verified fields in review."""

from conftest import make_page

from docextract.assemble import assemble
from docextract.layout import Word, group_lines
from docextract.schema import ExtractedDocument, LineItem, ScalarValue, validate_document, verified_fields
from docextract.text import fix_ocr_token


def test_fix_ocr_token_repairs_amounts_only():
    assert fix_ocr_token("1O.0O0") == "10.000"
    assert fix_ocr_token("45,5OO") == "45,500"
    assert fix_ocr_token("I00.000") == "100.000"
    assert fix_ocr_token("1O00") == "1000"
    for keep in ("B12", "10O", "SOS", "E6013", "2RS", "TOTAL", "OO.OO", "12/10", "Rp45.000", "100"):
        assert fix_ocr_token(keep) == keep


def test_group_lines_applies_the_repair():
    page = group_lines([Word("TOTAL", 0, 0, 50, 10), Word("4S.0O0", 60, 0, 120, 10)], 200, 20)
    assert [w.text for w in page.words] == ["TOTAL", "45.000"]


def _labelled(rows, labels, probs):
    page = make_page(rows)
    flat_l = [lab for row in labels for lab in row]
    flat_p = [p for row in probs for p in row]
    assert len(page.words) == len(flat_l)
    return page, flat_l, flat_p


def test_arithmetic_choice_prefers_consistent_total():
    # two words labelled total: 58.000 (more confident, wrong) and 48.000 (consistent with the items)
    rows = [["Nasi", "40.000"], ["Teh", "8.000"], ["SUBTOTAL", "48.000"], ["TOTAL", "58.000"], ["TOTAL", "48.000"]]
    labels = [
        ["menu.nm", "menu.price"],
        ["menu.nm", "menu.price"],
        ["O", "subtotal"],
        ["O", "total"],
        ["O", "total"],
    ]
    probs = [[0.9, 0.9], [0.9, 0.9], [1.0, 0.9], [1.0, 0.8], [1.0, 0.6]]
    page, lab, pr = _labelled(rows, labels, probs)
    assert assemble(page, lab, pr, lam=0.0).value("total") == 58000
    doc = assemble(page, lab, pr, lam=1.0)
    assert doc.value("total") == 48000 and doc.value("subtotal") == 48000
    assert validate_document(doc) == []


def test_item_confidence_comes_from_name_words():
    rows = [["Nasi", "40.000"], ["TOTAL", "40.000"]]
    page, lab, pr = _labelled(rows, [["menu.nm", "menu.price"], ["O", "total"]], [[0.5, 1.0], [1.0, 1.0]])
    assert assemble(page, lab, pr).items[0].confidence == 0.5


def test_verified_fields_skip_low_confidence_flags():
    doc = ExtractedDocument(
        items=[LineItem(name="NASI", price=40000, confidence=0.99), LineItem(name="TEH", price=8000, confidence=0.99)],
        subtotal=ScalarValue(value=48000, confidence=0.4),
        tax=ScalarValue(value=4800, confidence=0.4),
        total=ScalarValue(value=52800, confidence=0.4),
        cash=ScalarValue(value=60000, confidence=0.4),
        change=ScalarValue(value=7200, confidence=0.4),
    )
    assert verified_fields(doc) == {"subtotal", "tax", "total", "cash", "change"}
    assert validate_document(doc, min_conf=0.9) == []
    # an unconfirmed field (discount not used by any check) is still flagged
    doc.discount = ScalarValue(value=100, confidence=0.4)
    codes = [(i.code, i.field) for i in validate_document(doc, min_conf=0.9)]
    assert ("LOW_CONF", "discount") in codes
    # item names are never confirmed by arithmetic
    doc.discount = None
    doc.items[0].confidence = 0.5
    assert [(i.code, i.field) for i in validate_document(doc, min_conf=0.9)] == [("LOW_CONF", "items.0")]


def test_alternative_candidates_from_label_distribution():
    # the labeller put "total" on 58.000 only; 48.000 has some total probability
    rows = [["Nasi", "40.000"], ["Teh", "8.000"], ["SUBTOTAL", "48.000"], ["TOTAL", "58.000"], ["JUMLAH", "48.000"]]
    labels = [["menu.nm", "menu.price"], ["menu.nm", "menu.price"], ["O", "subtotal"], ["O", "total"], ["O", "O"]]
    probs = [[0.9, 0.9], [0.9, 0.9], [1.0, 0.9], [1.0, 0.8], [1.0, 0.7]]
    page, lab, pr = _labelled(rows, labels, probs)
    fp = [{} for _ in lab]
    fp[-1] = {"total": 0.25}
    fp[-2] = {"total": 0.8}
    assert assemble(page, lab, pr, lam=1.0).value("total") == 58000
    assert assemble(page, lab, pr, lam=0.0, field_probs=fp).value("total") == 58000
    doc = assemble(page, lab, pr, lam=2.0, field_probs=fp)
    assert doc.value("total") == 48000 and doc.total.confidence == 0.525  # mean over "JUMLAH 48.000"
    # below ALT_MIN the word is not a candidate
    fp[-1] = {"total": 0.05}
    assert assemble(page, lab, pr, lam=2.0, field_probs=fp).value("total") == 58000
