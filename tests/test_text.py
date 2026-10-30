import pytest

from docextract.text import is_money, norm_name, parse_amount, parse_count, similarity, word_shape


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("Rp 45.500", 45500),
        ("45,500", 45500),
        ("12,500.00", 12500),
        ("1.234.567", 1234567),
        ("(5,000)", 5000),
        ("45.50", 45),
        ("25000", 25000),
        ("abc", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_amount(text, value):
    assert parse_amount(text) == value


def test_parse_amount_joins_split_ocr_tokens():
    assert parse_amount("".join(["45", ",500"])) == 45500


def test_parse_count():
    assert parse_count("x2") == 2
    assert parse_count("3 pcs") == 3
    assert parse_count("-") is None


def test_is_money():
    assert is_money("45.000")
    assert is_money("Rp45.000")
    assert is_money("250")
    assert not is_money("12")
    assert not is_money("A4")


def test_word_shape_and_names():
    assert word_shape("Rp45.000") == "Aa0.0"
    assert norm_name("  nasi   goréng ") == "NASI GORENG"
    assert similarity("Nasi Goreng", "NASI GORENG") == 1.0
    assert 0.8 <= similarity("0li hidrolik", "Oli hidrolik") < 1.0
