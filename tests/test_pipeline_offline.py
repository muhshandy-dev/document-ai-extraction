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
    from docextract.ocr import OcrConfig

    monkeypatch.setattr(cli, "OCR_GRID", [OcrConfig("eng", 4), OcrConfig("eng", 6, 2, 1.5)])
    monkeypatch.setattr(cli, "C1_GRID", [0.0])
    monkeypatch.setattr(cli, "C2_GRID", [0.1, 1.0])
    monkeypatch.setattr(cli, "LAM_GRID", [0.0, 1.0])

    # development mode never reads the test split
    monkeypatch.setenv("DOCEXTRACT_NO_TEST", "")  # restored to unset after the test
    cli.main(["dev", "--skip-download", "--workers", "2", "--n-boot", "20"])
    dev = json.loads((tmp_path / "out" / "evaluation" / "v2" / "results-validation.json").read_text())
    assert dev["summary"]["N-gt"]["n_docs"] == 3
    with pytest.raises(PermissionError):
        pipeline.load_gt("test")
    monkeypatch.delenv("DOCEXTRACT_NO_TEST")

    cli.main(["all", "--skip-download", "--workers", "2", "--n-boot", "50", "--n-synth", "3"])

    ev = tmp_path / "out" / "evaluation" / "v2"
    test = json.loads((ev / "results-test.json").read_text())
    assert set(test["summary"]) == {"H-ocr", "N-ocr", "H-gt", "N-gt"}
    assert test["summary"]["N-gt"]["n_docs"] == 3
    # on clean ground-truth words of these simple receipts the trained model must work
    assert test["summary"]["N-gt"]["field_micro_f1"] >= 0.8
    sel = json.loads((ev / "model-selection.json").read_text())
    assert sel["chosen"]["c2"] in (0.1, 1.0) and sel["chosen_lambda"] in (0.0, 1.0)
    model = json.loads((tmp_path / "out" / "web" / "public" / "model" / "model-n.json").read_text())
    assert model["type"] == "crf" and model["meta"]["ocr"]["lang"] == "eng"
    assert {"review_min_conf", "assemble_lambda"} <= set(model["meta"])
    synth = json.loads((ev / "results-synth.json").read_text())
    assert set(synth["summary"]) == {"H-ocr", "N-ocr", "H-pdf", "N-pdf"}
    samples = json.loads((tmp_path / "out" / "web" / "public" / "samples" / "index.json").read_text())
    assert any(s["origin"].startswith("CORD") for s in samples)

    importlib.reload(pipeline)
    importlib.reload(cli)
