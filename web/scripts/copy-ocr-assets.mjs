// Copy Tesseract.js worker + LSTM wasm cores into public/ so OCR runs from our own origin
// (no CDN at runtime). Language data lives in public/tessdata (committed).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const nm = resolve(here, "../node_modules");
const out = resolve(here, "../public/tesseract");
mkdirSync(out, { recursive: true });
const files = [
  ["tesseract.js/dist/worker.min.js", "worker.min.js"],
  ["tesseract.js-core/tesseract-core-lstm.wasm.js", "tesseract-core-lstm.wasm.js"],
  ["tesseract.js-core/tesseract-core-simd-lstm.wasm.js", "tesseract-core-simd-lstm.wasm.js"],
];
for (const [src, dst] of files) copyFileSync(resolve(nm, src), resolve(out, dst));
console.log("ocr assets ->", out);
