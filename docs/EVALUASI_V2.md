# Protokol evaluasi v2

Ditulis 30 Oktober 2026, sebelum kode v2 dijalankan pada data CORD apa pun. Protokol v1 ([EVALUASI.md](EVALUASI.md)) dan hasilnya ([HASIL.md](HASIL.md)) tetap berlaku dan tetap dilaporkan.

## Latar belakang dan pengungkapan

Hasil uji v1 (sekali jalan, run 41080343691) menunjukkan empat kelemahan: field ringkasan masih rendah, tabel item tidak lebih baik dari aturan, OCR hanya membaca persis 43% kata, dan hampir semua struk dikirim ke peninjau. Shandy meminta keempatnya diperbaiki.

Karena itu v2 **tidak buta penuh** terhadap split uji:

- Arah perbaikan diambil dari angka agregat uji v1 (misalnya "OCR adalah hambatan terbesar").
- Satu dokumen uji (test-0000) terlihat di layar studio saat pemeriksaan tampilan. Prediksi per dokumen uji tidak dibuka dan tidak dipakai.
- Semua pilihan v2 dibuat di split validasi. Split uji dijalankan **sekali lagi** setelah semua pilihan v2 dibekukan.

## Perubahan v2

1. **OCR.** Kisi pengaturan Tesseract yang juga bisa dipasang di Tesseract.js:
   - bahasa: eng+ind (pilihan v1)
   - mode halaman (psm): 4, 6, 11
   - metode ambang (`thresholding_method`): 0 Otsu, 1 Otsu adaptif Leptonica, 2 Sauvola
   - skala gambar: 1,0 atau 1,5 (gambar diperbesar sebelum OCR, kotak kata dikembalikan ke ukuran asli)

   Dipilih yang paling banyak membaca kata anotasi validasi secara persis (definisi sama dengan v1). Seri dipecah dengan waktu tercepat.
2. **Koreksi angka OCR.** Token yang hanya terdiri dari angka, titik, koma, dan huruf yang mirip angka (O, o, D, Q jadi 0; I, l, i, | jadi 1; S jadi 5; B jadi 8; Z jadi 2) diperbaiki saat kata disusun menjadi baris. Syaratnya minimal dua angka; dengan pemisah (titik atau koma) jumlah huruf mirip angka paling banyak sama dengan jumlah angka; tanpa pemisah token minimal empat karakter dan huruf mirip angka paling banyak separuh jumlah angka, sehingga kode seperti "B12" tidak berubah (`fix_ocr_token`). Aturannya tetap dan tidak dituning. Berlaku untuk H dan N, di Python dan browser.
3. **Model N v2: CRF berantai linear** (python-crfsuite, L-BFGS) atas fitur kata v1 ditambah kelompok keyakinan OCR. Label dipilih dengan Viterbi dan keyakinan tiap kata dihitung dari peluang marginal (forward-backward). Inferensi memakai tabel bobot yang diekspor, di Python dan browser. Kisi regularisasi: c1 dari {0; 0,05; 0,2}, c2 dari {0,01; 0,1; 1}.
4. **Pemilihan nilai dengan cek aritmetika** (perakit bersama, dipakai H dan N). Untuk tiap field ringkasan diambil hingga 3 kandidat. Kombinasi dipilih dengan skor = jumlah log keyakinan + lambda x (banyak cek aritmetika yang terpenuhi): jumlah harga item = subtotal, total cocok dengan subtotal/pajak/servis/diskon, tunai dikurangi kembalian = total. Lambda dari {0; 0,5; 1; 2; 4}.
5. **Aturan peninjauan v2.** Dokumen lolos otomatis bila tidak ada catatan validasi aritmetika atau struktur, dan setiap field punya keyakinan di atas ambang **atau** nilainya sudah dibuktikan oleh cek aritmetika yang terpenuhi. Keyakinan item = rata-rata keyakinan kata namanya, dan nama item tetap harus di atas ambang. Aturan H tetap tanpa ambang (hanya catatan validasi), sama dengan v1. Ambang dari {0; 0,3; 0,4; ...; 0,95}; skor pemilihan sama dengan v1 (benar lolos dikurangi 2 x salah lolos).

6. **Pembanding T (opsional, hanya bila Shandy menyetujui): LayoutLM** (`microsoft/layoutlm-base-uncased`, lisensi MIT) yang di-fine-tune untuk label kata yang sama, hanya di evaluasi Python (tidak dipakai situs). Data latih sama dengan N. AdamW, laju belajar 5e-5, batch 8, 4 epoch, seed 0; epoch terbaik dipilih dengan skor pemilihan di validasi. Perakit memakai lambda yang terpilih untuk N; ambang peninjauan T dipilih tersendiri di validasi dengan skor yang sama. Halaman yang lebih panjang dari 512 token dipotong.

Urutan pemilihan di validasi: OCR, lalu (c1, c2) dengan lambda 1, lalu lambda, lalu ambang. Skor pemilihan model dan lambda sama dengan v1: rata-rata field-F1 mikro dan F1 baris tabel (masukan OCR).

## Pengembangan

- Mode pengembangan (`docextract dev`, workflow dengan penanda `[dev-validasi]`) hanya memuat split latih dan validasi. Kode menolak memuat split uji di mode ini. Hasil dan cache validasi disimpan di cabang `dev-cache/...`, bukan di cabang PR.
- Iterasi di validasi boleh berulang. Setiap iterasi tercatat di riwayat git.
- Aturan H juga ikut memakai OCR v2 dan koreksi angka, tetapi aturannya sendiri tidak diubah.

## Laporan akhir

- Satu kali `docextract all` (workflow dengan penanda `[jalankan-evaluasi]`): semua pilihan di validasi, lalu split uji sekali, lalu faktur sintetis seed 1000-1199.
- Hasil v2 ditulis ke `evaluation/v2/`; berkas v1 di `evaluation/` tidak diubah.
- Dilaporkan: H dan N v2 (OCR dan teks benar) dengan CI 95%, serta **selisih berpasangan v2 dikurangi v1** pada dokumen uji yang sama untuk H dan N.
- Perbaikan hanya diklaim bila selang selisih berpasangan tidak memuat 0. Bila v2 tidak lebih baik, itu yang ditulis.
- Metrik, bootstrap (2.000 kali, seed 42), dan definisi lain sama dengan v1.
