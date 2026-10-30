# Protokol evaluasi

Protokol ini ditulis dan dikunci sebelum split uji CORD-v2 dijalankan. Perubahan setelah melihat hasil uji tidak diperbolehkan; bila ada perbaikan, hasil lama tetap dilaporkan.

## Data

| Set | Jumlah | Dipakai untuk |
| --- | --- | --- |
| CORD-v2 latih | 800 struk | melatih N |
| CORD-v2 validasi | 100 struk | memilih pengaturan OCR, C, ambang peninjauan |
| CORD-v2 uji | 100 struk | laporan akhir, sekali jalan |
| Faktur sintetis seed 0-99 | 100 | pengembangan aturan H dan fixture paritas |
| Faktur sintetis seed 1000-1199 | 200 | uji di luar domain, laporan akhir |

## Pilihan yang dibuat di validasi

1. **OCR**: bahasa {eng, ind, eng+ind} x mode halaman {4, 6}. Dipilih yang paling banyak membaca kata anotasi secara persis (kata OCR menutup minimal 50% kotak kata anotasi dan teksnya sama).
2. **C** regresi logistik dari {0,1; 0,3; 1; 3}. Dipilih yang memaksimalkan rata-rata field-F1 mikro dan F1 baris tabel pada validasi (masukan OCR).
3. **Ambang keyakinan** dari {0; 0,3; ...; 0,95}. Dipilih yang memaksimalkan (dokumen lolos otomatis yang benar) dikurangi 2 x (dokumen lolos otomatis yang salah). Seri dipecah dengan ambang terkecil.

Data latih N = kata OCR yang diberi label dari anotasi (kata OCR mendapat label kata anotasi yang menutup minimal 50% kotaknya) ditambah kata anotasi itu sendiri.

## Metrik

- **Field-F1**: per pasangan (dokumen, field) untuk 7 field ringkasan. Benar bila angka sama dengan anotasi (bila anotasi punya beberapa nilai, salah satunya cukup). Nilai salah dihitung sebagai FP sekaligus FN; nilai pada field yang tidak ada di anotasi adalah FP. Dilaporkan F1 mikro (gabungan) dan makro (rata-rata per field yang muncul).
- **Table accuracy**: baris item prediksi dicocokkan satu-satu dengan anotasi. Cocok longgar = harga sama dan kemiripan nama (1 - jarak Levenshtein ternormalisasi) minimal 0,8. Cocok ketat = harga sama, nama ternormalisasi persis, dan jumlah sama bila anotasi mencantumkannya. Dilaporkan F1 baris (longgar dan ketat) dan porsi dokumen dengan tabel benar penuh.
- **Review rate**: porsi dokumen yang dikirim ke peninjau. Selalu dilaporkan bersama akurasi dokumen yang lolos otomatis dan porsi dokumen salah yang tertangkap.
- **Dokumen benar**: semua 7 field benar dan tabel benar penuh (longgar).

Anotasi sub-item CORD (`menu.sub_*`) tidak dihitung sebagai baris tabel. Nama item dibandingkan setelah huruf besar, tanpa aksen, spasi tunggal.

## Ketidakpastian

Selang kepercayaan 95% dengan bootstrap persentil per dokumen (2.000 kali, seed 42). Selisih N dikurangi H memakai bootstrap berpasangan (indeks dokumen yang sama untuk kedua cara). Selisih dianggap meyakinkan hanya bila selangnya tidak memuat 0.

## Batas atas

H dan N juga dijalankan pada kata anotasi (tanpa galat OCR). Selisih antara kolom OCR dan kolom teks benar menunjukkan kerugian akibat OCR.

## Hal yang tidak dilakukan

- Tidak ada tuning pada split uji.
- Tidak ada pemilihan contoh untuk ditampilkan berdasarkan bagus tidaknya hasil.
- Angka di situs dibaca dari `evaluation/*.json` yang dibuat oleh `docextract all`, tidak diketik tangan.
