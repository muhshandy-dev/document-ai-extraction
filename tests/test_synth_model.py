from conftest import make_page

from docextract.cord import gt_document
from docextract.heuristic import label_page
from docextract.model import CrfModel, train
from docextract.synth import make_invoice


def test_synthetic_invoice_arithmetic_is_consistent():
    for seed in range(30):
        _, doc = make_invoice(seed)
        assert all(it.qty * it.unit_price == it.price for it in doc.items)
        assert doc.value("subtotal") == sum(it.price for it in doc.items)
        disc = doc.value("discount") or 0
        assert doc.value("total") == doc.value("subtotal") - disc + doc.value("tax")


def test_synthetic_invoices_are_deterministic():
    assert make_invoice(7) == make_invoice(7)


def test_cord_gt_parse_with_alternatives_and_single_menu():
    doc, alts = gt_document(
        {
            "menu": {"nm": "ES TEH", "cnt": "2", "price": "10,000"},
            "sub_total": {"subtotal_price": "10,000", "tax_price": ["1,000", "500"]},
            "total": {"total_price": "11,000"},
        }
    )
    assert [(i.name, i.qty, i.price) for i in doc.items] == [("ES TEH", 2, 10000)]
    assert doc.value("tax") == 1000 and alts["tax"] == [1000, 500]
    assert doc.value("cash") is None


def test_trained_crf_roundtrips_through_json(tmp_path):
    rows = [["2", "Nasi", "Goreng", "40.000"], ["1", "Es", "Teh", "8.000"], ["TOTAL", "48.000"]]
    pages = [make_page(rows) for _ in range(4)]
    model = train(pages, [label_page(p) for p in pages], c1=0.0, c2=0.01)
    path = tmp_path / "m.json"
    import json

    path.write_text(json.dumps(model.to_json()))
    loaded = CrfModel.load(path)
    labels, probs = loaded.predict_page(pages[0])
    assert labels == label_page(pages[0])
    assert all(0 < p <= 1 for p in probs)


def test_crf_inference_matches_brute_force():
    """Viterbi = best path and marginals = normalised path weights, on a tiny model."""
    import itertools
    import math

    labels = ["O", "menu.nm", "total"]
    weights = {"a": [0, 0.5, 1, 1.2], "b": [1, -0.3, 2, 0.95], "c": [0, 0.1, 2, 0.4]}
    trans = [[0.2, -0.1, 0.3], [0.0, 0.7, -0.5], [-0.2, 0.1, 0.05]]
    m = CrfModel(labels, weights, trans, {})
    feats = [["a"], ["b", "c"], ["a", "c"], ["b"]]
    em = m.emissions(feats)

    def score(path):
        s = sum(em[t][y] for t, y in enumerate(path))
        return s + sum(trans[a][b] for a, b in zip(path, path[1:], strict=False))

    paths = list(itertools.product(range(3), repeat=len(feats)))
    best = max(paths, key=score)
    assert tuple(m.viterbi(em)) == best
    z = sum(math.exp(score(p)) for p in paths)
    marg = m.marginals(em)
    for t in range(len(feats)):
        for y in range(3):
            exact = sum(math.exp(score(p)) for p in paths if p[t] == y) / z
            assert abs(marg[t][y] - exact) < 1e-12
