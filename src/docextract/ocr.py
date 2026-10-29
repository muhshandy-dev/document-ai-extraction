"""Tesseract OCR wrapper and OCR-to-ground-truth alignment.

The benchmark runs native Tesseract with the same traineddata files the
browser loads through Tesseract.js (web/public/tessdata), so the model
weights are identical; only the engine build differs (see docs).
"""

from __future__ import annotations

import io
from pathlib import Path

from .layout import Word


def ocr_image(image_bytes: bytes, lang: str = "eng", psm: int = 4, tessdata_dir: Path | None = None) -> list[Word]:
    import pytesseract
    from PIL import Image

    config = f"--oem 1 --psm {psm} -c preserve_interword_spaces=0"
    if tessdata_dir is not None:
        config += f' --tessdata-dir "{tessdata_dir}"'
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = im.convert("RGB")
        data = pytesseract.image_to_data(im, lang=lang, config=config, output_type=pytesseract.Output.DICT)
    words: list[Word] = []
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(Word(text, float(x), float(y), float(x + w), float(y + h), conf))
    return words


def _area(x0: float, y0: float, x1: float, y1: float) -> float:
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def align_labels(ocr_words: list[Word], gt: list[Word], min_cover: float = 0.5) -> list[Word]:
    """Give each OCR word the label of the GT word covering most of its box.

    Coverage = intersection / OCR-word area. Words below `min_cover` stay "O".
    Returns new Word objects; the input list is not modified.
    """
    out: list[Word] = []
    for w in ocr_words:
        area = _area(w.x0, w.y0, w.x1, w.y1) or 1.0
        best, best_cov = "O", 0.0
        for g in gt:
            inter = _area(max(w.x0, g.x0), max(w.y0, g.y0), min(w.x1, g.x1), min(w.y1, g.y1))
            cov = inter / area
            if cov > best_cov:
                best, best_cov = g.label, cov
        out.append(Word(w.text, w.x0, w.y0, w.x1, w.y1, w.conf, best if best_cov >= min_cover else "O"))
    return out


def word_recall(ocr_words: list[Word], gt: list[Word], min_cover: float = 0.5) -> tuple[int, int]:
    """(GT words whose text is exactly reproduced by an overlapping OCR word, total GT words)."""
    hit = 0
    for g in gt:
        garea = _area(g.x0, g.y0, g.x1, g.y1) or 1.0
        for w in ocr_words:
            inter = _area(max(w.x0, g.x0), max(w.y0, g.y0), min(w.x1, g.x1), min(w.y1, g.y1))
            if inter / garea >= min_cover and w.text == g.text:
                hit += 1
                break
    return hit, len(gt)
