# Kartu model: N (pelabel kata)

**Status: belum dilatih.** Bagian bertanda (menunggu) diisi dari `evaluation/` setelah `docextract all` dijalankan.

| | |
| --- | --- |
| Tugas | Memberi label tiap kata OCR: nama item, jumlah, harga satuan, harga, sub-item, subtotal, pajak, servis, diskon, total, tunai, kembalian, lainnya (13 kelas) |
| Algoritma | Regresi logistik multinomial (scikit-learn, L2, lbfgs) |
| Fitur | Biner: teks kata (huruf kecil), awalan/akhiran 3 huruf, bentuk (Aa0), apakah angka uang, posisi x/y (10 kelompok), posisi dalam baris, jumlah kata dan angka di baris, kata kunci ringkasan di baris ini/sebelum/sesudah, posisi relatif terhadap baris ringkasan pertama, indentasi, kata tetangga, beberapa kombinasi |
| Data latih | 800 struk CORD-v2 latih (kata OCR berlabel + kata anotasi) |
| Format rilis | `web/public/model/model-n.json`: tabel bobot per fitur, dibulatkan 4 desimal. Evaluasi Python memakai berkas yang sama dengan browser |
| C terpilih | (menunggu) |
| Ambang peninjauan | (menunggu) |

## Penggunaan yang dimaksud

Demo portofolio dan pembanding metode pada struk berbahasa Indonesia/Inggris dengan tata letak mirip CORD.

## Bukan untuk

Keputusan keuangan, audit, atau pajak tanpa peninjauan manusia. Faktur pajak resmi, formulir, atau dokumen multi-halaman.

## Batasan yang sudah diketahui

- Kata di luar kosakata latih hanya dikenali lewat bentuk dan posisi.
- Model tidak melihat piksel; semua kesalahan OCR diteruskan.
- Tesseract.js di browser dan Tesseract native di evaluasi memakai data bahasa yang sama tetapi build mesin berbeda; hasil OCR bisa sedikit berbeda.
