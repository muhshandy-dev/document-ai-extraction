"""End-to-end run of the CLI protocol on a fake CORD set (no network).

Proves the download-free part of `docextract all` works: OCR grid on
validation, OCR caching, training with C and threshold selection, scoring
validation and test, synthetic out-of-domain run and web export.
"""

import importlib
import json
import shutil

import pytest
from fake_cord import write_fake_cord

pytestmark = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")


def test_full_protocol_on_fake_cord(tmp_path, monkeypatch):
    data = tmp_path / "data"
    write_fake_cord(data / "cord", {"train": 8, "validation": 3, "test": 3})
    monkeypatch.setenv("DOCEXTRACT_DATA", str(data))
    monkeypatch.setenv("DOCEXTRACT_OUT", str(tmp_path / "out"))
    import docextract.cli as cli
    import docextract.pipeline as pipeline

    importlib.reload(pipeline)
    importlib.reload(cli)
    monkeypatch.setattr(cli, "OCR_GRID", [("eng", 4), ("eng", 6)])
    monkeypatch.setattr(cli, "C_GRID", [0.3, 1.0])

    cli.main(["all", "--skip-download", "--workers", "2", "--n-boot", "50", "--n-synth", "3"])

    ev = tmp_path / "out" / "evaluation"
    test = json.loads((ev / "results-test.json").read_text())
    assert set(test["summary"]) == {"H-ocr", "N-ocr", "H-gt", "N-gt"}
    assert test["summary"]["N-gt"]["n_docs"] == 3
    # on clean ground-truth words of these simple receipts the trained model must work
    assert test["summary"]["N-gt"]["field_micro_f1"] >= 0.8
    sel = json.loads((ev / "model-selection.json").read_text())
    assert sel["chosen_C"] in (0.3, 1.0)
    model = json.loads((tmp_path / "out" / "web" / "public" / "model" / "model-n.json").read_text())
    assert model["meta"]["ocr"]["lang"] == "eng" and "review_min_conf" in model["meta"]
    synth = json.loads((ev / "results-synth.json").read_text())
    assert set(synth["summary"]) == {"H-ocr", "N-ocr", "H-pdf", "N-pdf"}
    samples = json.loads((tmp_path / "out" / "web" / "public" / "samples" / "index.json").read_text())
    assert any(s["origin"].startswith("CORD") for s in samples)

    importlib.reload(pipeline)
    importlib.reload(cli)
