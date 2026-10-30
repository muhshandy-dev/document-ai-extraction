# Document AI Extraction

Studio peninjauan struk dan faktur. Teks dibaca dengan OCR (atau lapisan teks PDF), kata disusun menjadi baris, lalu field ringkasan (subtotal, pajak, servis, diskon, total, tunai, kembalian) dan baris item (nama, jumlah, harga) diambil dengan dua cara yang dibandingkan secara jujur:

- **H, aturan heuristik**: kata kunci dan regex, tanpa pembelajaran.
- **N, model terlatih**: regresi logistik multinomial atas fitur teks dan tata letak tiap kata, dilatih pada 800 struk CORD-v2.

Hasil divalidasi dengan skema Pydantic (padanannya di browser) dan aturan konsistensi. Dokumen yang gagal validasi atau keyakinannya rendah dikirim ke peninjau manusia.

> **Status (30 Oktober 2026):** kode, tes, dan studio web selesai dan teruji. Evaluasi CORD-v2 sudah dijalankan sekali (GitHub Actions run 41080343691); hasil lengkap di [docs/HASIL.md](docs/HASIL.md). Situs belum dideploy.

## Hasil singkat

Split uji CORD-v2, 100 foto struk, OCR Tesseract. Angka dalam kurung = selang kepercayaan 95%.

| | H (aturan) | N (model) | N dengan teks benar (batas atas) |
| --- | --- | --- | --- |
| Field-F1 mikro | 40,3 (32,4 s.d. 47,8) | 49,1 (40,4 s.d. 57,3) | 94,1 (91,0 s.d. 96,6) |
| F1 baris tabel | 22,6 (15,5 s.d. 30,2) | 25,8 (18,6 s.d. 33,6) | 70,3 (59,9 s.d. 79,7) |
| Dikirim ke peninjau | 85,0 | 99,0 | 86,0 |

- N lebih baik dari H untuk field ringkasan secara meyakinkan (+8,8 poin, selang +4,1 s.d. +13,7). Untuk baris tabel bedanya belum meyakinkan.
- Hambatan terbesar adalah OCR: hanya 43% kata pada foto struk terbaca persis. Dengan teks benar, model yang sama mencapai 94,1.
- Pada faktur sintetis (di luar domain latih), H jauh lebih baik untuk tabel (F1 baris 94,5 lawan 15,3).

## Isi repositori

| Folder | Isi |
| --- | --- |
| `src/docextract/` | Paket Python: OCR, layout parsing, H, fitur + model N, skema Pydantic, metrik, generator faktur sintetis, CLI |
| `tests/` | pytest, termasuk uji ujung ke ujung pada dataset tiruan berformat CORD dan fixture paritas Python vs TypeScript |
| `web/` | Situs statis React + TypeScript (Vite): pdf.js, Tesseract.js, inti ekstraksi kembaran Python |
| `evaluation/` | Hasil evaluasi (dibuat oleh `docextract all`), ringkasannya di `docs/HASIL.md` |
| `notebooks/` | Notebook Kaggle yang menjalankan protokol yang sama (belum pernah dijalankan di Kaggle) |
| `docs/` | Protokol evaluasi, kartu model, kartu data, arsitektur, panduan deploy |

## Cara kerja singkat

1. **Baca teks.** PDF digital: lapisan teks lewat pdf.js. Gambar atau pindaian: OCR Tesseract (LSTM, data `tessdata_best_int`).
2. **Layout parsing.** Kata dengan kotak koordinat dikelompokkan menjadi baris berdasarkan tumpang tindih vertikal (`layout.py`).
3. **Label kata.** H memakai aturan (`heuristic.py`); N memakai 28+ fitur biner per kata (teks, bentuk, posisi, kata tetangga, kata kunci baris) dan bobot regresi logistik (`features.py`, `model.py`).
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
