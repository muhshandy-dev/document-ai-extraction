# Kartu model: N (pelabel kata)

**Status: versi 2, dievaluasi sekali** pada 31 Oktober 2026 (GitHub Actions run 41160697515). Angka lengkap di [HASIL_V2.md](HASIL_V2.md); versi 1 (regresi logistik) di [HASIL.md](HASIL.md).

| | |
| --- | --- |
| Tugas | Memberi label tiap kata OCR: nama item, jumlah, harga satuan, harga, sub-item, subtotal, pajak, servis, diskon, total, tunai, kembalian, lainnya (13 kelas) |
| Algoritma | CRF berantai linear (python-crfsuite, L-BFGS, c1 0,05, c2 0,1). Label dipilih dengan Viterbi; keyakinan tiap kata dari peluang marginal (forward-backward) |
| Fitur | Biner: teks kata (huruf kecil), awalan/akhiran 3 huruf, bentuk (Aa0), apakah angka uang, posisi x/y, posisi dalam baris, jumlah kata dan angka di baris, kata kunci ringkasan di baris ini/sebelum/sesudah, posisi relatif terhadap baris ringkasan pertama, indentasi, kata tetangga, kelompok keyakinan OCR, beberapa kombinasi |
| Data latih | 800 struk CORD-v2 latih (kata OCR berlabel) |
| Format rilis | `web/public/model/model-n.json`: bobot fitur per label (36.553 nilai) dan matriks transisi, dibulatkan 4 desimal. Evaluasi Python memakai berkas yang sama dengan browser |
| Ambang peninjauan | 0,95 (di split validasi); field yang terbukti oleh cek aritmetika tidak ditandai keyakinan rendah |
| OCR saat latih dan uji | Tesseract 5.3.4, eng+ind, psm 11, ambang Sauvola, ditambah koreksi angka yang terbaca sebagai huruf |

## Hasil utama (split uji CORD-v2, 100 struk)

| | H (aturan) | N v2 | N v1 | N v2 dengan teks benar |
| --- | --- | --- | --- | --- |
| Field-F1 mikro | 40,1 (32,1 s.d. 47,5) | 49,8 (41,5 s.d. 57,1) | 49,1 (40,4 s.d. 57,3) | 93,4 (90,5 s.d. 95,9) |
| F1 baris tabel, longgar | 27,1 (18,7 s.d. 36,1) | 26,0 (17,8 s.d. 34,6) | 25,8 (18,6 s.d. 33,6) | 74,8 (63,9 s.d. 84,3) |
| Dikirim ke peninjau | 90,0 | 92,0 | 99,0 | 52,0 |
| Benar di antara yang lolos otomatis | 3 dari 10 | 2 dari 8 | 1 dari 1 | 40 dari 48 |

N v2 tidak lebih akurat dari N v1 secara meyakinkan (field +0,7, selang -7,3 s.d. +8,5). N tetap lebih baik dari H untuk field ringkasan (+9,7, selang +4,4 s.d. +15,6). Pembanding LayoutLM (hanya Python, tidak dimuat di situs) setara dengan N pada teks OCR dan sedikit lebih baik pada teks benar.

## Penggunaan yang dimaksud

Demo portofolio dan pembanding metode pada struk berbahasa Indonesia/Inggris dengan tata letak mirip CORD.

## Bukan untuk

Keputusan keuangan, audit, atau pajak tanpa peninjauan manusia. Faktur pajak resmi, formulir, atau dokumen multi-halaman.

## Batasan yang sudah diketahui

- Pada foto struk, OCR adalah sumber kesalahan terbesar (sekitar 45% kata terbaca persis).
- Struk yang "lolos otomatis" tidak bisa dipercaya: di split uji hanya 2 dari 8 yang benar. Tetap periksa semua hasil.
- Tidak cocok untuk tabel faktur dengan nama barang panjang berhuruf kecil; gunakan aturan H.

- Kata di luar kosakata latih hanya dikenali lewat bentuk dan posisi.
- Model tidak melihat piksel; semua kesalahan OCR diteruskan.
- Tesseract.js di browser dan Tesseract native di evaluasi memakai data bahasa yang sama tetapi build mesin berbeda; hasil OCR bisa sedikit berbeda.
