from conftest import make_page

from docextract.assemble import assemble
from docextract.heuristic import label_page, summary_field


def run(rows):
    page = make_page(rows)
    labels = label_page(page)
    return assemble(page, labels, [1.0] * len(labels))


def test_receipt_rows_and_totals():
    doc = run(
        [
            ["TOKO", "CONTOH"],
            ["2", "Nasi", "Goreng", "40.000"],
            ["1", "Es", "Teh", "8.000"],
            ["SUBTOTAL", "48.000"],
            ["PB1", "10%", "4.800"],
            ["TOTAL", "52.800"],
            ["CASH", "60.000"],
            ["CHANGE", "7.200"],
        ]
    )
    assert [(i.name, i.qty, i.price) for i in doc.items] == [("Nasi Goreng", 2, 40000), ("Es Teh", 1, 8000)]
    assert doc.scalar_values() == {
        "subtotal": 48000,
        "tax": 4800,
        "service": None,
        "discount": None,
        "total": 52800,
        "cash": 60000,
        "change": 7200,
    }


def test_name_then_qty_price_on_next_line():
    doc = run([["Kopi", "Susu", "Gula", "Aren"], ["2", "x", "18.000", "36.000"], ["TOTAL", "36.000"]])
    assert len(doc.items) == 1
    it = doc.items[0]
    assert (it.name, it.qty, it.unit_price, it.price) == ("Kopi Susu Gula Aren", 2, 18000, 36000)


def test_digits_inside_names_are_not_prices():
    doc = run([["Bearing", "6205", "2RS", "5", "Rp", "57.000", "Rp", "285.000"], ["TOTAL", "285.000"]])
    it = doc.items[0]
    assert (it.name, it.qty, it.unit_price, it.price) == ("Bearing 6205 2RS", 5, 57000, 285000)


def test_total_item_count_is_not_total():
    page = make_page([["TOTAL", "ITEM", "3"]])
    assert summary_field(page.lines[0]) is None
