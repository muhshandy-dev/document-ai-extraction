// Tesseract.js running in a Web Worker, with every asset served from this site.
import { OEM, PSM, createWorker, type Worker } from "tesseract.js";
import type { Word } from "../core/layout";

let worker: Promise<Worker> | null = null;
let workerKey = "";
let progressCb: ((p: number, status: string) => void) | null = null;

export interface OcrSettings {
  lang: string;
  psm: number;
  /** Tesseract thresholding_method: 0 Otsu, 1 Leptonica adaptive Otsu, 2 Sauvola */
  thresh: number;
  /** enlarge the image by this factor before OCR; boxes are mapped back */
  scale: number;
}

function getWorker(s: OcrSettings): Promise<Worker> {
  const key = `${s.lang}|${s.psm}|${s.thresh}`;
  if (worker && key === workerKey) return worker;
  if (worker) void worker.then((w) => w.terminate());
  workerKey = key;
  const base = new URL(import.meta.env.BASE_URL, window.location.href);
  worker = (async () => {
    const w = await createWorker(s.lang, OEM.LSTM_ONLY, {
      workerPath: new URL("tesseract/worker.min.js", base).href,
      corePath: new URL("tesseract/", base).href,
      langPath: new URL("tessdata", base).href,
      gzip: true,
      workerBlobURL: false,
      cacheMethod: "none",
      logger: (m) => progressCb?.(m.progress ?? 0, m.status ?? ""),
    });
    await w.setParameters({
      tessedit_pageseg_mode: String(s.psm) as PSM,
      thresholding_method: String(s.thresh),
    } as Parameters<Worker["setParameters"]>[0]);
    return w;
  })();
  return worker;
}

function scaled(src: HTMLCanvasElement, scale: number): HTMLCanvasElement {
  if (scale === 1) return src;
  const c = document.createElement("canvas");
  c.width = Math.round(src.width * scale);
  c.height = Math.round(src.height * scale);
  const ctx = c.getContext("2d");
  if (!ctx) throw new Error("canvas 2d tidak tersedia");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high"; // the Python benchmark uses bicubic resampling
  ctx.drawImage(src, 0, 0, c.width, c.height);
  return c;
}

export async function ocrCanvas(
  canvas: HTMLCanvasElement,
  settings: OcrSettings,
  onProgress?: (p: number, status: string) => void,
): Promise<Word[]> {
  progressCb = onProgress ?? null;
  const w = await getWorker(settings);
  const k = settings.scale;
  const res = await w.recognize(scaled(canvas, k), {}, { blocks: true, text: false });
  const words: Word[] = [];
  for (const block of res.data.blocks ?? []) {
    for (const para of block.paragraphs) {
      for (const line of para.lines) {
        for (const word of line.words) {
          const text = word.text.trim();
          if (!text || word.confidence < 0) continue;
          const b = word.bbox;
          words.push({ text, x0: b.x0 / k, y0: b.y0 / k, x1: b.x1 / k, y1: b.y1 / k, conf: word.confidence });
        }
      }
    }
  }
  progressCb = null;
  return words;
}
