# Hasil evaluasi v2 (run 41160697515, 31 Oktober 2026)

Semua angka disalin dari `evaluation/v2/`, hasil satu kali jalan workflow **Evaluasi CORD** di GitHub Actions ([run 41160697515](https://github.com/muhshandy-dev/document-ai-extraction/actions/runs/41160697515), commit `8d739c1`, Tesseract 5.3.4, python-crfsuite 0.9.12). Protokol: [EVALUASI_V2.md](EVALUASI_V2.md). Hasil v1 tetap di [HASIL.md](HASIL.md).

**Bukan evaluasi buta penuh.** Split uji yang sama sudah dipakai v1, dan arah perbaikan v2 diambil dari angka agregat v1. Semua pilihan v2 dibuat di split validasi (dua iterasi, tercatat di protokol), lalu split uji dijalankan sekali.

Angka dalam kurung: selang kepercayaan 95% dari bootstrap berpasangan per dokumen (2.000 kali, seed 42). Perbaikan hanya diklaim bila selang selisih tidak memuat 0.

## Kesimpulan

1. **Field ringkasan: tidak membaik.** Model N v2 49,8 lawan v1 49,1 (selisih +0,7, selang -7,3 s.d. +8,5). N tetap lebih baik dari aturan H (+9,7, selang +4,4 s.d. +15,6), sama seperti di v1.
2. **Baris tabel: tidak membaik.** N v2 26,0 lawan v1 25,8. Aturan H naik ke 27,1 (dari 22,6) tetapi selisihnya juga belum meyakinkan.
3. **OCR: naik tipis.** Pengaturan terpilih (psm 11, ambang Sauvola) membaca persis 44,9% kata validasi, lawan 43,4% untuk pengaturan v1. OCR tetap hambatan utama: dengan teks benar, N mencapai field-F1 93,4 dan T 96,0, tetapi dengan OCR keduanya sekitar 50.
4. **Peninjauan: lebih sedikit dikirim, tetapi yang lolos tidak bisa dipercaya.** N v2 mengirim 92% struk ke peninjau (v1: 99%, selisih -7,0, selang -13,0 s.d. -2,0, meyakinkan). Namun dari 8 struk yang lolos otomatis hanya 2 yang benar (v1: 1 dari 1). Empat dari enam struk yang salah hanya melewatkan satu field (tunai, diskon, atau kembalian) yang tidak terbaca sama sekali, jadi tidak ada cek aritmetika yang gagal; dua lainnya salah membaca nilai total atau kembalian. Di validasi, 6 dari 8 yang lolos benar; jumlahnya terlalu kecil untuk diandalkan.
5. **Pemilihan nilai dengan cek aritmetika** diuji di validasi tetapi tidak membantu (lambda 0 terbaik), jadi tidak dipakai.
6. **LayoutLM (T) sebagai pembanding.** Dengan teks benar, T lebih baik dari N secara meyakinkan (field +2,6, selang +0,5 s.d. +5,0; baris +3,5, selang +0,4 s.d. +7,2). Dengan OCR, T setara dengan N (field +0,3, selang -2,4 s.d. +2,8). T lebih jarang mengirim ke peninjau (85%), tetapi hanya 4 dari 15 yang lolos otomatis benar.

Ringkasnya, v2 belum menghasilkan perbaikan akurasi yang meyakinkan. Batas utamanya adalah OCR Tesseract pada foto struk, bukan pelabel kata.

## Struk CORD-v2, split uji (100 dokumen)

| Metrik | H, OCR | N, OCR | T (LayoutLM), OCR | H, teks benar | N, teks benar | T, teks benar |
| --- | --- | --- | --- | --- | --- | --- |
| Field-F1 mikro (7 field) | 40,1 (32,1 s.d. 47,5) | 49,8 (41,5 s.d. 57,1) | 50,1 (41,8 s.d. 57,7) | 83,5 (79,0 s.d. 87,5) | 93,4 (90,5 s.d. 95,9) | 96,0 (93,4 s.d. 97,9) |
| Field-F1 makro | 34,0 (25,4 s.d. 41,5) | 42,7 (34,2 s.d. 50,0) | 47,4 (36,6 s.d. 56,5) | 76,3 (69,3 s.d. 81,8) | 91,5 (84,8 s.d. 95,9) | 94,7 (88,1 s.d. 98,5) |
| F1 baris tabel, longgar | 27,1 (18,7 s.d. 36,1) | 26,0 (17,8 s.d. 34,6) | 26,8 (18,6 s.d. 36,0) | 61,9 (52,6 s.d. 70,7) | 74,8 (63,9 s.d. 84,3) | 78,3 (67,3 s.d. 87,9) |
| F1 baris tabel, ketat | 15,1 (9,3 s.d. 21,9) | 13,6 (8,2 s.d. 20,3) | 13,8 (8,4 s.d. 20,6) | 56,3 (47,0 s.d. 65,2) | 72,9 (62,1 s.d. 82,3) | 75,6 (65,2 s.d. 84,8) |
| Dokumen dengan tabel benar penuh | 16,0 (9,0 s.d. 24,0) | 18,0 (11,0 s.d. 26,0) | 20,0 (12,0 s.d. 28,0) | 46,0 (36,0 s.d. 56,0) | 70,0 (61,0 s.d. 78,0) | 78,0 (70,0 s.d. 86,0) |
| Dokumen benar seluruhnya | 4,0 (1,0 s.d. 8,0) | 3,0 (0,0 s.d. 7,0) | 5,0 (1,0 s.d. 10,0) | 24,0 (16,0 s.d. 33,0) | 55,0 (45,0 s.d. 64,0) | 65,0 (55,0 s.d. 74,0) |
| Dikirim ke peninjau | 90,0 (84,0 s.d. 96,0) | 92,0 (87,0 s.d. 97,0) | 85,0 (78,0 s.d. 91,0) | 56,0 (46,0 s.d. 66,0) | 52,0 (42,0 s.d. 62,0) | 45,0 (35,0 s.d. 55,0) |
| Benar di antara yang lolos otomatis | 3 dari 10 | 2 dari 8 | 4 dari 15 | 21 dari 44 | 40 dari 48 | 49 dari 55 |

## Selisih berpasangan

| Selisih (poin) | field-F1 mikro | F1 baris | Dikirim ke peninjau |
| --- | --- | --- | --- |
| N v2 dikurangi N v1 (OCR) | +0,7 (-7,3 s.d. 8,5) | +0,1 (-8,6 s.d. 8,7) | -7,0 (-13,0 s.d. -2,0) |
| H v2 dikurangi H v1 (OCR) | -0,3 (-7,5 s.d. 6,9) | +4,5 (-3,6 s.d. 12,5) | +5,0 (-1,0 s.d. 11,0) |
| N dikurangi H (OCR, v2) | +9,7 (4,4 s.d. 15,6) | -1,1 (-5,9 s.d. 4,0) | +2,0 (-4,0 s.d. 8,0) |
| T dikurangi N (OCR) | +0,3 (-2,4 s.d. 2,8) | +0,9 (-2,4 s.d. 4,3) | -7,0 (-13,0 s.d. -2,0) |
| N dikurangi H (teks benar) | +10,0 (6,8 s.d. 13,5) | +12,9 (5,1 s.d. 21,1) | -4,0 (-17,0 s.d. 9,0) |
| T dikurangi N (teks benar) | +2,6 (0,5 s.d. 5,0) | +3,5 (0,4 s.d. 7,2) | -7,0 (-15,0 s.d. 1,0) |

## Pilihan di validasi

| Pilihan | Terpilih |
| --- | --- |
| OCR | eng+ind, psm 11, ambang Sauvola, skala 1,0 (kata terbaca persis 44,9%) |
| CRF | c1 0,05, c2 0,1 (36.553 bobot fitur) |
| Lambda cek aritmetika | 0 (nilai lain tidak lebih baik) |
| Ambang peninjauan N | 0,95 |
| LayoutLM | epoch 3 dari 4, ambang peninjauan 0,95 |

Catatan: di run pengembangan, LayoutLM memilih epoch 4 dan ambang 0,9; di run akhir epoch 3 dan ambang 0,95. Pelatihan di CPU tidak sepenuhnya deterministik antar mesin, jadi angka T bisa bergeser sedikit bila diulang. Bagian Python lain (OCR, CRF) memberi angka validasi yang identik di kedua run.

## Faktur sintetis (di luar domain, 200 faktur)

| | H, OCR | N, OCR | H, teks PDF | N, teks PDF |
| --- | --- | --- | --- | --- |
| Field-F1 mikro | 88,8 | 88,6 | 100,0 | 98,7 |
| F1 baris tabel | 71,9 | 17,6 | 100,0 | 22,2 |
| Dikirim ke peninjau | 30,0 | 100,0 | 0,0 | 100,0 |

Model N tetap tidak cocok untuk tabel faktur (nama barang panjang berhuruf kecil); aturan H tetap yang dipakai untuk itu.
