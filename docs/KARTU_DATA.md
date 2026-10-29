# Kartu data

## CORD-v2

- Sumber: `naver-clova-ix/cord-v2` di Hugging Face (6 berkas parquet). Hash SHA-256 dicatat di `evaluation/environment.txt` saat workflow evaluasi berjalan.
- Isi: 1.000 foto struk dari Indonesia dengan anotasi kata (kotak empat titik, teks, kategori) dan hasil parse terstruktur (`gt_parse`).
- Lisensi: CC BY 4.0. Wajib mencantumkan atribusi (lihat NOTICE).
- Data pribadi: berisi struk toko dan restoran. Proyek ini tidak mengumpulkan data tambahan dan hanya menampilkan beberapa gambar uji sebagai contoh; periksa kartu data resmi CORD sebelum memakai ulang di tempat lain.
- Pemetaan kategori ke label ada di `src/docextract/cord.py` (`CATEGORY_TO_LABEL`). Kata dengan `is_key = 1` (misalnya tulisan "TOTAL") berlabel "lainnya".

## Faktur sintetis

- Dibuat oleh `src/docextract/synth.py` dengan seed tetap; nama penjual dan pembeli rekaan, produk industri umum.
- Aritmetika konsisten: jumlah x harga satuan = harga, subtotal - diskon + PPN 11% = total.
- Variasi: 3 jenis huruf, 3 format angka (Rp 1.000 / 1.000 / 1,000.00), urutan kolom, pergeseran horizontal.
- Versi "pindaian": render 150 dpi, rotasi kecil, blur, kompresi JPEG.
- Keterbatasan: jauh lebih rapi daripada dokumen nyata; aturan H dikembangkan dengan seed 0-99, sehingga hasil H pada faktur sintetis cenderung optimistis.
