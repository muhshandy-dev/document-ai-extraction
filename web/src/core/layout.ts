// Twin of src/docextract/layout.py.
import { fixOcrToken } from "./text";

export interface Word {
  text: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  conf: number;
  label?: string;
}

export interface Line {
  words: Word[];
  y0: number;
  y1: number;
}

export interface Page {
  width: number;
  height: number;
  lines: Line[];
}

export const LOOKBACK = 6;
export const MIN_OVERLAP = 0.5;

const yc = (w: Word) => (w.y0 + w.y1) / 2;
const wh = (w: Word) => Math.max(w.y1 - w.y0, 1);

export const lineText = (l: Line) => l.words.map((w) => w.text).join(" ");
export const lineX0 = (l: Line) => Math.min(...l.words.map((w) => w.x0));
export const pageWords = (p: Page): Word[] => p.lines.flatMap((l) => l.words);

export function groupLines(words: Word[], width: number, height: number): Page {
  const order = words
    .filter((w) => w.text.trim().length > 0)
    .map((w) => {
      const t = fixOcrToken(w.text);
      return t === w.text ? w : { ...w, text: t };
    })
    .map((w, i) => ({ w, i }))
    .sort((a, b) => yc(a.w) - yc(b.w) || a.w.x0 - b.w.x0 || a.i - b.i)
    .map((o) => o.w);
  const lines: Line[] = [];
  const sums: [number, number, number][] = [];
  for (const w of order) {
    let best = -1;
    let bestOv = 0;
    const start = Math.max(0, lines.length - LOOKBACK);
    for (let i = start; i < lines.length; i++) {
      const line = lines[i];
      const ov = Math.min(w.y1, line.y1) - Math.max(w.y0, line.y0);
      const denom = Math.min(wh(w), Math.max(line.y1 - line.y0, 1));
      const ratio = ov / denom;
      if (ratio > bestOv) {
        best = i;
        bestOv = ratio;
      }
    }
    if (best >= 0 && bestOv >= MIN_OVERLAP) {
      const s = sums[best];
      s[0] += w.y0;
      s[1] += w.y1;
      s[2] += 1;
      const line = lines[best];
      line.words.push(w);
      line.y0 = s[0] / s[2];
      line.y1 = s[1] / s[2];
    } else {
      lines.push({ words: [w], y0: w.y0, y1: w.y1 });
      sums.push([w.y0, w.y1, 1]);
    }
  }
  for (const line of lines) {
    const idx = line.words.map((w, i) => ({ w, i }));
    idx.sort((a, b) => a.w.x0 - b.w.x0 || a.i - b.i);
    line.words = idx.map((o) => o.w);
  }
  const li = lines.map((l, i) => ({ l, i }));
  li.sort((a, b) => (a.l.y0 + a.l.y1) / 2 - (b.l.y0 + b.l.y1) / 2 || lineX0(a.l) - lineX0(b.l) || a.i - b.i);
  return { width, height, lines: li.map((o) => o.l) };
}
