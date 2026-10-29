// Labelled words -> ExtractedDocument. Twin of src/docextract/assemble.py.
import { type Page, pageWords } from "./layout";
import { type ExtractedDocument, type LineItem, SCALAR_FIELDS, emptyDocument } from "./schema";
import { parseAmount, parseCount } from "./text";

interface Item {
  name: string[];
  cnt: string[];
  unit: string[];
  price: string[];
  probs: number[];
  /** indices of the words that make up this item (for highlighting) */
  words: number[];
  last: string;
  lastLine: number;
}

const clamp01 = (v: number) => Math.min(Math.max(v, 0), 1);

function toItem(it: Item): LineItem {
  const conf = it.probs.length ? it.probs.reduce((a, b) => a + b, 0) / it.probs.length : 0;
  return {
    name: it.name.join(" ").split(/\s+/).filter(Boolean).join(" "),
    qty: parseCount(it.cnt.join(" ")),
    unit_price: parseAmount(it.unit.join("")),
    price: parseAmount(it.price.join("")),
    confidence: clamp01(conf),
  };
}

export interface Assembled {
  doc: ExtractedDocument;
  /** word indices per scalar field and per item, for the viewer */
  fieldWords: Record<string, number[]>;
  itemWords: number[][];
}

export function assemble(page: Page, labels: string[], probs: number[]): Assembled {
  const words = pageWords(page);
  if (words.length !== labels.length || labels.length !== probs.length) throw new Error("length mismatch");
  type Group = { sum: number; li: number; texts: string[]; ps: number[]; idx: number[] };
  const groups: Record<string, Group[]> = Object.fromEntries(SCALAR_FIELDS.map((f) => [f, []]));
  let k = 0;
  page.lines.forEach((line, li) => {
    const perLine = new Map<string, Group>();
    for (const w of line.words) {
      const lab = labels[k];
      if (lab in groups) {
        let g = perLine.get(lab);
        if (!g) {
          g = { sum: 0, li, texts: [], ps: [], idx: [] };
          perLine.set(lab, g);
        }
        g.texts.push(w.text);
        g.ps.push(probs[k]);
        g.idx.push(k);
      }
      k++;
    }
    for (const [lab, g] of perLine) {
      // same summation order as Python's sum(ps)
      g.sum = g.ps.reduce((a, b) => a + b, 0);
      groups[lab].push(g);
    }
  });

  const doc = emptyDocument();
  const fieldWords: Record<string, number[]> = {};
  for (const f of SCALAR_FIELDS) {
    const cands = groups[f].slice().sort((a, b) => b.sum - a.sum || a.li - b.li);
    for (const g of cands) {
      const value = parseAmount(g.texts.join(""));
      if (value !== null) {
        const conf = g.ps.reduce((a, b) => a + b, 0) / g.ps.length;
        doc[f] = { value, confidence: clamp01(conf), text: g.texts.join(" ") };
        fieldWords[f] = g.idx;
        break;
      }
    }
  }

  const lineOf = page.lines.flatMap((l, li) => l.words.map(() => li));
  const items: Item[] = [];
  let cur: Item | null = null;
  const fresh = (): Item => {
    const it: Item = { name: [], cnt: [], unit: [], price: [], probs: [], words: [], last: "", lastLine: -1 };
    items.push(it);
    return it;
  };
  words.forEach((w, i) => {
    const lab = labels[i];
    const p = probs[i];
    const li = lineOf[i];
    if (!lab.startsWith("menu.") || lab === "menu.sub") return;
    if (lab === "menu.nm") {
      if (cur === null || cur.price.length || (cur.name.length && cur.last !== "menu.nm")) cur = fresh();
      cur.name.push(w.text);
    } else if (lab === "menu.cnt") {
      if (cur === null || cur.price.length || cur.cnt.length) cur = fresh();
      cur.cnt.push(w.text);
    } else if (lab === "menu.unitprice") {
      if (cur === null || cur.price.length) cur = fresh();
      if (cur.unit.length && cur.last !== "menu.unitprice") return;
      cur.unit.push(w.text);
    } else if (lab === "menu.price") {
      if (cur === null || (cur.price.length && (cur.last !== "menu.price" || cur.lastLine !== li))) cur = fresh();
      cur.price.push(w.text);
    } else {
      return;
    }
    cur.probs.push(p);
    cur.words.push(i);
    cur.last = lab;
    cur.lastLine = li;
  });
  const kept = items.filter((it) => it.name.length || it.price.length);
  doc.items = kept.map(toItem);
  return { doc, fieldWords, itemWords: kept.map((it) => it.words) };
}
