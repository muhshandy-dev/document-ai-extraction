# Deploy ke Cloudflare Pages

1. Cloudflare dashboard, Workers & Pages, Create, Pages, Connect to Git, pilih repo `document-ai-extraction`.
2. Pengaturan build:
   - Production branch: `main`
   - Root directory: `web`
   - Build command: `npm ci && npm run build`
   - Build output directory: `dist`
   - Environment variable: `NODE_VERSION = 22`
3. Nama proyek `document-ai-extraction` agar alamatnya `document-ai-extraction.pages.dev`.
4. Setelah deploy, buka situs, pilih contoh "(pindaian)", dan pastikan OCR selesai tanpa galat di konsol.

Catatan: berkas terbesar adalah worker pdf.js (sekitar 1,4 MB) dan data bahasa Tesseract (sekitar 3 MB); semua jauh di bawah batas 25 MiB per berkas. Situs statis tidak tidur saat tidak dipakai.
