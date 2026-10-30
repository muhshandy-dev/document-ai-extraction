# Arsitektur

```
berkas (PDF/gambar)
   │
   ├─ PDF dengan lapisan teks ──► pdf.js getTextContent ──┐
   └─ gambar / Paksa OCR ──────► Tesseract.js (worker) ───┤   kata + kotak
                                                          ▼
                                     layout.groupLines (baris)
                                                          │
                     ┌────────────────────────────────────┴───────────────┐
                     ▼                                                    ▼
          heuristic.labelPage (H)                    features.pageFeatures + model (N)
                     └──────────────► assemble ◄──────────────────────────┘
                                         │
                                 validateDocument (aturan + ambang keyakinan)
                                         │
                       panel peninjauan: sunting, setujui, unduh JSON
```

- Semua langkah berjalan di browser. Tidak ada server aplikasi; Cloudflare Pages hanya menyajikan berkas statis.
- Worker Tesseract, inti WebAssembly, dan data bahasa disajikan dari origin sendiri (`web/public/tesseract`, `web/public/tessdata`). CSP di `web/public/_headers` hanya mengizinkan `'self'` dan `'wasm-unsafe-eval'`.
- Inti di `web/src/core/*.ts` adalah kembaran `src/docextract/*.py`. Fixture `tests/fixtures/parity.json` (dibuat `tools/make_parity_fixtures.py`) diuji oleh `web/tests/parity.test.ts`.
- Python memakai Pydantic untuk skema; browser memakai pemeriksaan setara di `web/src/core/schema.ts` (`schemaErrors`, `validateDocument`).
