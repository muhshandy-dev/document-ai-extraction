# Kartu model: N (pelabel kata)

**Status: dilatih dan dievaluasi sekali** pada 30 Oktober 2026 (GitHub Actions run 41080343691). Angka lengkap di [HASIL.md](HASIL.md).

| | |
| --- | --- |
| Tugas | Memberi label tiap kata OCR: nama item, jumlah, harga satuan, harga, sub-item, subtotal, pajak, servis, diskon, total, tunai, kembalian, lainnya (13 kelas) |
| Algoritma | Regresi logistik multinomial (scikit-learn, L2, lbfgs) |
| Fitur | Biner: teks kata (huruf kecil), awalan/akhiran 3 huruf, bentuk (Aa0), apakah angka uang, posisi x/y (10 kelompok), posisi dalam baris, jumlah kata dan angka di baris, kata kunci ringkasan di baris ini/sebelum/sesudah, posisi relatif terhadap baris ringkasan pertama, indentasi, kata tetangga, beberapa kombinasi |
| Data latih | 800 struk CORD-v2 latih (kata OCR berlabel + kata anotasi) |
| Format rilis | `web/public/model/model-n.json`: tabel bobot per fitur (36.942 nilai fitur), dibulatkan 4 desimal, sekitar 3,8 MB (kira-kira 0,8 MB terkompresi). Evaluasi Python memakai berkas yang sama dengan browser |
| C terpilih | 0,3 (dari 0,1 / 0,3 / 1 / 3, di split validasi) |
| Ambang peninjauan | 0,95 (dari 0 sampai 0,95, di split validasi) |
| OCR saat latih dan uji | Tesseract 5.3.4, eng+ind, psm 6 |

## Hasil utama (split uji CORD-v2, 100 struk)

| | H (aturan) | N (model) | N dengan teks benar |
| --- | --- | --- | --- |
| Field-F1 mikro | 40,3 (32,4 s.d. 47,8) | 49,1 (40,4 s.d. 57,3) | 94,1 (91,0 s.d. 96,6) |
| F1 baris tabel, longgar | 22,6 (15,5 s.d. 30,2) | 25,8 (18,6 s.d. 33,6) | 70,3 (59,9 s.d. 79,7) |
| Dokumen dengan tabel benar penuh | 11,0 | 11,0 | 62,0 |
| Dikirim ke peninjau | 85,0 | 99,0 | 86,0 |

N lebih baik dari H untuk field ringkasan (selisih +8,8 poin, selang +4,1 s.d. +13,7), belum terbukti lebih baik untuk baris tabel (+3,2, selang -2,2 s.d. +9,3). Pada faktur sintetis di luar domain, F1 baris tabel N hanya 15,3 karena nama barang dipotong di tempat yang salah.

## Penggunaan yang dimaksud

Demo portofolio dan pembanding metode pada struk berbahasa Indonesia/Inggris dengan tata letak mirip CORD.

## Bukan untuk

Keputusan keuangan, audit, atau pajak tanpa peninjauan manusia. Faktur pajak resmi, formulir, atau dokumen multi-halaman.

## Batasan yang sudah diketahui

- Pada foto struk, OCR adalah sumber kesalahan terbesar (43% kata terbaca persis); dengan ambang terpilih hampir semua struk dikirim ke peninjau.
- Tidak cocok untuk tabel faktur dengan nama barang panjang berhuruf kecil; gunakan aturan H.

- Kata di luar kosakata latih hanya dikenali lewat bentuk dan posisi.
- Model tidak melihat piksel; semua kesalahan OCR diteruskan.
- Tesseract.js di browser dan Tesseract native di evaluasi memakai data bahasa yang sama tetapi build mesin berbeda; hasil OCR bisa sedikit berbeda.
