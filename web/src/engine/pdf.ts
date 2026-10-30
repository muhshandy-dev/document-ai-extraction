// pdf.js: render page 1 to a canvas and read its text layer as words.
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { Word } from "../core/layout";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

/** Same resolution as the Python benchmark renders synthetic invoices (150 dpi). */
export const PDF_SCALE = 150 / 72;

export interface RenderedPdf {
  canvas: HTMLCanvasElement;
  textWords: Word[];
  pages: number;
}

export async function renderPdf(data: ArrayBuffer): Promise<RenderedPdf> {
  const doc = await pdfjs.getDocument({ data, isEvalSupported: false }).promise;
  const page = await doc.getPage(1);
  const viewport = page.getViewport({ scale: PDF_SCALE });
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(viewport.width);
  canvas.height = Math.round(viewport.height);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas 2d tidak tersedia");
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  await page.render({ canvasContext: ctx, viewport }).promise;

  const content = await page.getTextContent();
  const textWords: Word[] = [];
  for (const item of content.items) {
    if (!("str" in item) || !item.str.trim()) continue;
    const [a, b, , , e, f] = pdfjs.Util.transform(viewport.transform, item.transform);
    const fontH = Math.hypot(a, b);
    const width = item.width * PDF_SCALE;
    const x0 = e;
    const yBase = f;
    // split the text run into words, spreading x by character count
    const str = item.str;
    const n = str.length || 1;
    const re = /\S+/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(str))) {
      const wx0 = x0 + (width * m.index) / n;
      const wx1 = x0 + (width * (m.index + m[0].length)) / n;
      textWords.push({ text: m[0], x0: wx0, y0: yBase - fontH * 0.8, x1: wx1, y1: yBase + fontH * 0.2, conf: 100 });
    }
  }
  return { canvas, textWords, pages: doc.numPages };
}

export async function loadImage(blob: Blob): Promise<HTMLCanvasElement> {
  const bmp = await createImageBitmap(blob);
  const canvas = document.createElement("canvas");
  canvas.width = bmp.width;
  canvas.height = bmp.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas 2d tidak tersedia");
  ctx.drawImage(bmp, 0, 0);
  bmp.close();
  return canvas;
}
