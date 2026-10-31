# Document AI Extraction

Studio peninjauan struk dan faktur. Teks dibaca dengan OCR (atau lapisan teks PDF), kata disusun menjadi baris, lalu field ringkasan (subtotal, pajak, servis, diskon, total, tunai, kembalian) dan baris item (nama, jumlah, harga) diambil dengan dua cara yang dibandingkan secara jujur:

- **H, aturan heuristik**: kata kunci dan regex, tanpa pembelajaran.
- **N, model terlatih**: CRF berantai linear atas fitur teks dan tata letak tiap kata (v2; v1 memakai regresi logistik), dilatih pada 800 struk CORD-v2.
- **T, pembanding riset**: LayoutLM (`microsoft/layoutlm-base-uncased`) yang di-fine-tune untuk label yang sama. Hanya di evaluasi Python, tidak dimuat di situs.

Hasil divalidasi dengan skema Pydantic (padanannya di browser) dan aturan konsistensi. Dokumen yang gagal validasi atau keyakinannya rendah dikirim ke peninjau manusia.

> **Status (31 Oktober 2026):** versi 2 dievaluasi sekali (GitHub Actions run 41160697515); hasil lengkap di [docs/HASIL_V2.md](docs/HASIL_V2.md), versi 1 di [docs/HASIL.md](docs/HASIL.md). Situs belum dideploy.

## Hasil singkat (v2)

Split uji CORD-v2, 100 foto struk, OCR Tesseract. Angka dalam kurung = selang kepercayaan 95%.

| | H (aturan) | N (CRF) | T (LayoutLM) | N dengan teks benar | T dengan teks benar |
| --- | --- | --- | --- | --- | --- |
| Field-F1 mikro | 40,1 (32,1 s.d. 47,5) | 49,8 (41,5 s.d. 57,1) | 50,1 (41,8 s.d. 57,7) | 93,4 (90,5 s.d. 95,9) | 96,0 (93,4 s.d. 97,9) |
| F1 baris tabel | 27,1 (18,7 s.d. 36,1) | 26,0 (17,8 s.d. 34,6) | 26,8 (18,6 s.d. 36,0) | 74,8 (63,9 s.d. 84,3) | 78,3 (67,3 s.d. 87,9) |
| Dikirim ke peninjau | 90,0 | 92,0 | 85,0 | 52,0 | 45,0 |

- N lebih baik dari H untuk field ringkasan secara meyakinkan (+9,7 poin, selang +4,4 s.d. +15,6). Untuk baris tabel bedanya belum meyakinkan.
- v2 tidak lebih akurat dari v1 secara meyakinkan (N: 49,8 lawan 49,1). Struk yang dikirim ke peninjau turun dari 99% ke 92%, tetapi dari 8 yang lolos otomatis hanya 2 yang benar.
- Hambatan terbesar adalah OCR: sekitar 45% kata pada foto struk terbaca persis. Dengan teks benar, N mencapai 93,4 dan LayoutLM 96,0.
- Pada faktur sintetis (di luar domain latih), H jauh lebih baik untuk tabel (F1 baris 71,9 lawan 17,6 dengan OCR).

## Isi repositori

| Folder | Isi |
| --- | --- |
| `src/docextract/` | Paket Python: OCR, layout parsing, H, fitur + model N, skema Pydantic, metrik, generator faktur sintetis, CLI |
| `tests/` | pytest, termasuk uji ujung ke ujung pada dataset tiruan berformat CORD dan fixture paritas Python vs TypeScript |
| `web/` | Situs statis React + TypeScript (Vite): pdf.js, Tesseract.js, inti ekstraksi kembaran Python |
| `evaluation/` | Hasil evaluasi v1 (`evaluation/`) dan v2 (`evaluation/v2/`), ringkasannya di `docs/HASIL.md` dan `docs/HASIL_V2.md` |
| `notebooks/` | Notebook Kaggle yang menjalankan protokol yang sama (belum pernah dijalankan di Kaggle) |
| `docs/` | Protokol evaluasi, kartu model, kartu data, arsitektur, panduan deploy |

## Cara kerja singkat

1. **Baca teks.** PDF digital: lapisan teks lewat pdf.js. Gambar atau pindaian: OCR Tesseract (LSTM, data `tessdata_best_int`).
2. **Layout parsing.** Kata dengan kotak koordinat dikelompokkan menjadi baris berdasarkan tumpang tindih vertikal (`layout.py`).
3. **Label kata.** H memakai aturan (`heuristic.py`); N memakai fitur biner per kata (teks, bentuk, posisi, kata tetangga, kata kunci baris, keyakinan OCR) dan CRF berantai linear: Viterbi untuk label, peluang marginal untuk keyakinan (`features.py`, `model.py`).
4. **Rakit dokumen** dari kata berlabel (`assemble.py`) lalu **validasi** (`schema.py`).
5. **Tentukan peninjauan**: catatan validasi apa pun, atau keyakinan field di bawah ambang yang dipilih di data validasi.

Inti langkah 2 sampai 5 ada dua kali, di Python dan TypeScript. `tests/fixtures/parity.json` memastikan keduanya memberi hasil yang sama (40 kasus).

## Menjalankan secara lokal

```bash
sudo apt-get install tesseract-ocr poppler-utils
pip install -e ".[dev]"
pytest -q                    # 35 tes, termasuk protokol penuh pada CORD tiruan

cd web
npm ci
npm test                     # uji paritas
npm run build && node scripts/serve.mjs dist 4173
```

## Menjalankan evaluasi

Satu perintah menjalankan seluruh protokol (unduh CORD-v2, pilih pengaturan OCR di validasi, OCR semua split, latih N dan pilih C serta ambang peninjauan di validasi, lalu skor validasi, uji, dan faktur sintetis):

```bash
docextract all
```

Butuh akses ke `huggingface.co` dan CDN-nya (`*.hf.co`). Di GitHub, jalankan workflow **Evaluasi CORD** secara manual; hasilnya didorong ke cabang `eval/run-<id>` untuk ditinjau lewat pull request. Split uji sudah dipakai sekali untuk hasil di atas; menjalankannya lagi setelah mengubah pipeline harus dilaporkan sebagai hasil baru, bukan pengganti. Aturan lengkap di [docs/EVALUASI.md](docs/EVALUASI.md).

## Data dan lisensi

- Kode: MIT.
- CORD-v2 (naver-clova-ix/cord-v2): CC BY 4.0, oleh NAVER Clova. Contoh struk di `web/public/samples` mengikuti lisensi tersebut.
- Data bahasa Tesseract (`web/public/tessdata`): tessdata_best_int, Apache-2.0, didistribusikan lewat paket npm `@tesseract.js-data`.
- Faktur sintetis: dibuat oleh `docextract.synth`, semua nama perusahaan rekaan.

Detail di [NOTICE](NOTICE).
