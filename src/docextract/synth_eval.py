"""Out-of-domain check on synthetic invoices (model trained on CORD only).

Two text sources per invoice:
- "ocr": the PDF rendered at 150 dpi with light scan noise, then Tesseract;
- "pdf": the PDF text layer (poppler `pdftotext -bbox`), which is what
  pdf.js gives the browser for a digital PDF.
Seeds 0-99 were used while writing the rules; seeds 1000-1199 form the
held-out set reported in evaluation/results-synth.json.
"""

from __future__ import annotations

import io
import json
import random
import re
import subprocess
from html import unescape
from pathlib import Path

from .layout import Word
from .ocr import OcrConfig, ocr_image
from .schema import SCALAR_FIELDS, ExtractedDocument
from .synth import make_invoice, render_pdf

DPI = 150
PT_TO_PX = DPI / 72


def scan_image(pdf: Path, seed: int) -> bytes:
    from PIL import Image, ImageFilter

    png_base = pdf.with_suffix("")
    subprocess.run(["pdftoppm", "-r", str(DPI), "-png", "-singlefile", str(pdf), str(png_base)], check=True)
    rnd = random.Random(seed)
    with Image.open(f"{png_base}.png") as im:
        im = im.convert("L")
        im = im.rotate(rnd.uniform(-0.8, 0.8), resample=Image.BICUBIC, fillcolor=255)
        if rnd.random() < 0.5:
            im = im.filter(ImageFilter.GaussianBlur(rnd.uniform(0.3, 0.8)))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=rnd.randint(55, 85))
    Path(f"{png_base}.png").unlink()
    return buf.getvalue()


_WORD_RE = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')
_PAGE_RE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">')


def pdf_text_words(pdf: Path) -> tuple[list[Word], float, float]:
    """Words from the PDF text layer in pixel units at DPI (same frame as OCR)."""
    out = subprocess.run(["pdftotext", "-bbox", str(pdf), "-"], check=True, capture_output=True, text=True).stdout
    pw, ph = (float(v) for v in _PAGE_RE.search(out).groups())
    words = [
        Word(unescape(t), float(a) * PT_TO_PX, float(b) * PT_TO_PX, float(c) * PT_TO_PX, float(d) * PT_TO_PX)
        for a, b, c, d, t in _WORD_RE.findall(out)
    ]
    return words, pw * PT_TO_PX, ph * PT_TO_PX


def build_cache(out_dir: Path, seeds: range, tessdata: Path, cfg: OcrConfig) -> list[dict]:
    """Render, OCR and store each invoice once. Returns records like load_gt()."""
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    recs = []
    for seed in seeds:
        name = f"faktur-{seed:04d}"
        cache = out_dir / cfg.key / f"{name}.json"
        if cache.exists():
            recs.append(json.loads(cache.read_text()))
            continue
        spec, doc = make_invoice(seed)
        pdf = out_dir / f"{name}.pdf"
        render_pdf(spec, doc, pdf)
        img = scan_image(pdf, seed)
        with Image.open(io.BytesIO(img)) as im:
            w, h = im.size
        ocr_words = ocr_image(img, cfg.lang, cfg.psm, tessdata, cfg.thresh, cfg.scale)
        pdf_words, pw, ph = pdf_text_words(pdf)
        rec = {
            "doc_id": name,
            "width": w,
            "height": h,
            "ocr_words": [x.to_dict() for x in ocr_words],
            "pdf_words": [x.to_dict() for x in pdf_words],
            "pdf_size": [pw, ph],
            "doc": doc.model_dump(mode="json"),
            "alts": {f: [doc.value(f)] for f in SCALAR_FIELDS if doc.value(f) is not None},
        }
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(rec))
        pdf.unlink()
        recs.append(rec)
    return recs


def gt_of(rec: dict) -> ExtractedDocument:
    return ExtractedDocument.model_validate(rec["doc"])
