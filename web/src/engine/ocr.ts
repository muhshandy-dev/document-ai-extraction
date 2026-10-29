// Tesseract.js running in a Web Worker, with every asset served from this site.
import { OEM, PSM, createWorker, type Worker } from "tesseract.js";
import type { Word } from "../core/layout";

let worker: Promise<Worker> | null = null;
let workerKey = "";
let progressCb: ((p: number, status: string) => void) | null = null;

export interface OcrSettings {
  lang: string;
  psm: number;
}

function getWorker(s: OcrSettings): Promise<Worker> {
  const key = `${s.lang}|${s.psm}`;
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
    await w.setParameters({ tessedit_pageseg_mode: String(s.psm) as PSM });
    return w;
  })();
  return worker;
}

export async function ocrCanvas(
  image: HTMLCanvasElement | HTMLImageElement | Blob,
  settings: OcrSettings,
  onProgress?: (p: number, status: string) => void,
): Promise<Word[]> {
  progressCb = onProgress ?? null;
  const w = await getWorker(settings);
  const res = await w.recognize(image, {}, { blocks: true, text: false });
  const words: Word[] = [];
  for (const block of res.data.blocks ?? []) {
    for (const para of block.paragraphs) {
      for (const line of para.lines) {
        for (const word of line.words) {
          const text = word.text.trim();
          if (!text || word.confidence < 0) continue;
          const b = word.bbox;
          words.push({ text, x0: b.x0, y0: b.y0, x1: b.x1, y1: b.y1, conf: word.confidence });
        }
      }
    }
  }
  progressCb = null;
  return words;
}
