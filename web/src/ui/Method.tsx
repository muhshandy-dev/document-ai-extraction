export function Method() {
  return (
    <main className="doc-page">
      <header>
        <h1>Cara kerja</h1>
        <p className="muted">
          Studio ini membaca struk atau faktur, mengambil angka-angka penting dan baris item, lalu memutuskan apakah
          hasilnya bisa diterima otomatis atau perlu dicek manusia.
        </p>
      </header>

      <section>
        <h2>Alur pemrosesan</h2>
        <div className="steps">
          <div className="step">
            <strong>Baca teks</strong>
            PDF digital dibaca dari lapisan teksnya dengan pdf.js. Gambar atau pindaian dibaca dengan OCR Tesseract.js,
            langsung di browser.
          </div>
          <div className="step">
            <strong>Susun tata letak</strong>
            Setiap kata punya kotak koordinat. Kata yang tingginya bertumpuk digabung menjadi satu baris, lalu baris
            diurutkan dari atas ke bawah.
          </div>
          <div className="step">
            <strong>Beri label kata</strong>
            Dua cara: aturan kata kunci (H), atau model regresi logistik (N) yang dilatih pada 800 struk berlabel dengan
            fitur teks dan posisi.
          </div>
          <div className="step">
            <strong>Rakit dokumen</strong>
            Kata berlabel dirakit menjadi field (subtotal, pajak, total, dan lainnya) serta baris item (nama, jumlah,
            harga).
          </div>
          <div className="step">
            <strong>Validasi skema</strong>
            Hasil dicek terhadap skema (Pydantic di Python, padanannya di browser): tipe angka, total cocok dengan
            subtotal dan pajak, tunai dikurangi kembalian sama dengan total.
          </div>
          <div className="step">
            <strong>Tentukan peninjauan</strong>
            Dokumen dengan catatan validasi, atau field yang keyakinannya rendah, dikirim ke peninjau. Sisanya lolos
            otomatis.
          </div>
        </div>
      </section>

      <section>
        <h2>Data</h2>
        <p>
          Evaluasi utama memakai CORD-v2 (naver-clova-ix/cord-v2, lisensi CC BY 4.0): 1.000 foto struk dari Indonesia
          dengan pembagian bawaan 800 latih, 100 validasi, 100 uji. Faktur sintetis dibuat oleh generator di repositori,
          dengan nama perusahaan rekaan dan aritmetika yang konsisten. Tidak ada dokumen pribadi.
        </p>
        <p>
          Model bahasa Tesseract (eng, ind) berasal dari tessdata_best_int (Apache-2.0) dan disajikan dari situs ini
          sendiri, sehingga OCR tidak memanggil server lain.
        </p>
      </section>

      <section>
        <h2>Batasan yang perlu diketahui</h2>
        <ul>
          <li>Model hanya dilatih dengan struk CORD. Untuk dokumen lain (faktur pajak, formulir) hasilnya bisa jauh lebih buruk.</li>
          <li>
            Evaluasi Python memakai Tesseract native dengan data bahasa yang sama; Tesseract.js di browser bisa memberi
            hasil OCR yang sedikit berbeda.
          </li>
          <li>Lolos otomatis bukan jaminan benar. Tingkat kesalahan di antara dokumen yang lolos dilaporkan di halaman evaluasi.</li>
          <li>Hanya halaman pertama PDF yang diproses.</li>
          <li>Ukuran tabel memakai pencocokan nama longgar (kemiripan minimal 80%) dan ketat (nama persis); keduanya dilaporkan.</li>
        </ul>
      </section>
    </main>
  );
}
