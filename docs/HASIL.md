# Hasil evaluasi (run 41080343691, 30 Oktober 2026)

> Ini hasil versi 1. Hasil versi 2 (CRF, OCR baru, pembanding LayoutLM) ada di [HASIL_V2.md](HASIL_V2.md).

Semua angka di halaman ini disalin dari berkas di `evaluation/`, hasil satu kali jalan workflow **Evaluasi CORD** di GitHub Actions ([run 41080343691](https://github.com/muhshandy-dev/document-ai-extraction/actions/runs/41080343691), commit `748fda1`, Tesseract 5.3.4, scikit-learn 1.9.1). Split uji CORD-v2 dijalankan sekali sesuai [protokol](EVALUASI.md). Tidak ada pengaturan yang diubah setelah hasil uji terlihat.

Angka dalam kurung adalah selang kepercayaan 95% dari bootstrap per dokumen (2.000 kali, seed 42).

## Pilihan yang dibuat di split validasi

| Pilihan | Kisi | Terpilih | Alasan |
| --- | --- | --- | --- |
| Pengaturan OCR | eng / ind / eng+ind × psm 4 / 6 | eng+ind, psm 6 | Kata terbaca persis 43,4% (tertinggi; terendah 33,0%) |
| C regresi logistik | 0,1 / 0,3 / 1 / 3 | 0,3 | Rata-rata field-F1 dan F1 baris tertinggi (51,4% dan 32,3%) |
| Ambang keyakinan peninjauan | 0 sampai 0,95 | 0,95 | Satu-satunya ambang dengan skor positif. Pada ambang lebih rendah, dokumen yang lolos otomatis lebih banyak salah daripada benar |

## Struk CORD-v2, split uji (100 dokumen)

"Teks benar" memakai kata dari anotasi dataset, bukan OCR. Kolom ini adalah batas atas untuk memisahkan kesalahan OCR dari kesalahan ekstraksi.

| Metrik | H, OCR | N, OCR | H, teks benar | N, teks benar |
| --- | --- | --- | --- | --- |
| Field-F1 mikro (7 field) | 40,3 (32,4 s.d. 47,8) | **49,1** (40,4 s.d. 57,3) | 83,5 (79,0 s.d. 87,5) | **94,1** (91,0 s.d. 96,6) |
| Field-F1 makro | 32,3 (24,2 s.d. 39,9) | **46,3** (33,2 s.d. 56,2) | 76,3 (69,3 s.d. 81,8) | **92,5** (86,0 s.d. 96,7) |
| F1 baris tabel, longgar | 22,6 (15,5 s.d. 30,2) | 25,8 (18,6 s.d. 33,6) | 61,9 (52,6 s.d. 70,7) | 70,3 (59,9 s.d. 79,7) |
| F1 baris tabel, ketat | 14,9 (9,4 s.d. 21,3) | 15,6 (10,0 s.d. 21,7) | 56,3 (47,0 s.d. 65,2) | 66,5 (56,8 s.d. 75,8) |
| Dokumen dengan tabel benar penuh | 11,0 (5,0 s.d. 17,0) | 11,0 (5,0 s.d. 17,0) | 46,0 (36,0 s.d. 56,0) | 62,0 (53,0 s.d. 71,0) |
| Dokumen benar seluruhnya | 2,0 (0,0 s.d. 5,0) | 5,0 (1,0 s.d. 10,0) | 24,0 (16,0 s.d. 33,0) | 53,0 (43,0 s.d. 62,0) |
| Dikirim ke peninjau (review rate) | 85,0 (78,0 s.d. 92,0) | 99,0 (97,0 s.d. 100,0) | 56,0 (46,0 s.d. 66,0) | 86,0 (79,0 s.d. 93,0) |
| Benar di antara yang lolos otomatis | 13,3 (2 dari 15) | 100 (1 dari 1) | 47,7 (21 dari 44) | 100 (14 dari 14) |

Field-F1 per field, N dengan OCR: subtotal 40,9, pajak 42,9, servis 35,3, diskon 44,4, total 53,2, tunai 48,0, kembalian 59,5. Dengan teks benar semuanya antara 83,3 (diskon, hanya 6 dokumen) dan 96,4.

### Selisih berpasangan

| Selisih | Field-F1 mikro | F1 baris longgar | Tabel benar penuh | Review rate |
| --- | --- | --- | --- | --- |
| N dikurangi H, OCR | +8,8 (+4,1 s.d. +13,7) | +3,2 (-2,2 s.d. +9,3) | 0,0 (-7 s.d. +7) | +14 (+8 s.d. +21) |
| N dikurangi H, teks benar | +10,6 (+7,4 s.d. +14,2) | +8,4 (+0,9 s.d. +15,7) | +16 (+5 s.d. +27) | +30 (+19 s.d. +41) |
| N teks benar dikurangi N OCR | +44,9 (+36,7 s.d. +54,0) | +44,5 (+34,7 s.d. +54,2) | +51 (+42 s.d. +61) | -13 (-20 s.d. -7) |

## Faktur sintetis (200 faktur, seed 1000-1199, di luar domain latih)

Model N dilatih hanya dengan struk CORD. Aturan H ditulis sambil melihat faktur sintetis dari generator yang sama (seed 0-99), jadi angka H di sini cenderung optimistis.

| Metrik | H, OCR pindaian | N, OCR pindaian | H, lapisan teks PDF | N, lapisan teks PDF |
| --- | --- | --- | --- | --- |
| Field-F1 mikro | 98,8 (97,9 s.d. 99,5) | 97,8 (96,5 s.d. 98,8) | 100 | 99,4 (98,9 s.d. 99,8) |
| F1 baris tabel, longgar | **94,5** (92,5 s.d. 96,2) | 15,3 (12,9 s.d. 18,0) | **100** | 15,8 (13,3 s.d. 18,5) |
| Dokumen dengan tabel benar penuh | 82,0 | 0,0 | 100 | 0,0 |
| Review rate | 13,0 | 100 | 0,0 | 100 |
| Benar di antara yang lolos otomatis | 92,0 (160 dari 174) | tidak ada yang lolos | 100 | tidak ada yang lolos |

Penyebab kegagalan tabel N, dilihat pada faktur contoh `faktur-5000` (bukan bagian dari set uji): harga satuan dan jumlah dilabeli benar, tetapi nama barang yang panjang dan berhuruf kecil (misalnya "Gasket spiral wound 4 inch") hanya sebagian dilabeli sebagai nama, karena nama menu di CORD umumnya pendek dan berhuruf kapital. Baris dianggap salah bila kemiripan nama di bawah 80%.

## Kesimpulan

1. **N lebih baik dari H untuk field ringkasan, secara meyakinkan.** Selisih field-F1 mikro dengan OCR +8,8 poin, selangnya tidak memuat 0. Dengan teks benar selisihnya +10,6 poin.
2. **Untuk baris tabel dengan OCR, N belum terbukti lebih baik dari H.** Selisih +3,2 poin dengan selang yang memuat 0. Keunggulan N di tabel baru terlihat dengan teks benar.
3. **OCR adalah hambatan terbesar.** Tesseract hanya membaca persis 43% kata pada foto struk CORD. Model yang sama naik dari 49,1 ke 94,1 field-F1 bila diberi teks benar. Perbaikan berikutnya yang paling berdampak ada di OCR (praproses gambar atau mesin OCR lain), bukan di model label.
4. **Peninjauan otomatis belum memberi penghematan pada foto struk.** Dengan ambang yang dipilih di validasi, N mengirim 99 dari 100 struk ke peninjau. Aturan H lebih banyak meloloskan dokumen (15), tetapi hanya 2 yang benar: lolos validasi skema saja tidak menjamin benar.
5. **Di luar domain, N gagal pada tabel faktur** (F1 baris 15%), sedangkan H hampir sempurna. Untuk faktur sintetis di studio, gunakan H.

## Status kriteria penerimaan

| Kriteria | Status | Bukti |
| --- | --- | --- |
| C1 Pipeline OCR nyata, layout, H, N, Pydantic, satu perintah | Terpenuhi | `docextract all` berjalan penuh di GitHub Actions pada CORD-v2 asli (`evaluation/run-log.txt`) |
| C2 Tabel H vs N vs batas atas pada data uji dengan CI 95% | Terpenuhi | `evaluation/results-test.json`, tabel di atas |
| C3 Kesimpulan jujur | Terpenuhi | Bagian kesimpulan: N unggul di field, belum terbukti di tabel, gagal di luar domain |
| C4 Web penuh di browser | Terpenuhi secara lokal | Lihat README; situs belum dideploy |
| C5 Paritas Python vs TypeScript | Terpenuhi | `web/tests/parity.test.ts` |
| C6 Tes otomatis dan CI | Terpenuhi | Workflow CI hijau |
| C7 Dokumentasi | Terpenuhi | README, kartu model, kartu data, halaman ini |

Penyimpangan dari spesifikasi Master tetap berlaku: benchmark dijalankan di GitHub Actions, bukan Kaggle, dan model N adalah regresi logistik, bukan transformer.
