// Labelled words -> ExtractedDocument. Twin of src/docextract/assemble.py.
// Scalar fields: up to MAX_CANDIDATES values per field; the chosen combination maximises
// sum(log confidence) + lambda * (arithmetic checks that hold). lambda = 0 is the v1 choice.
import { type Page, pageWords } from "./layout";
import {
  type ExtractedDocument,
  type FieldName,
  type LineItem,
  SCALAR_FIELDS,
  type ScalarValue,
  emptyDocument,
} from "./schema";
import { parseAmount, parseCount } from "./text";

export const MAX_CANDIDATES = 3;
const MIN_LOG_CONF = 1e-6;

interface Item {
  name: string[];
  cnt: string[];
  unit: string[];
  price: string[];
  probs: number[];
  nameProbs: number[];
  /** indices of the words that make up this item (for highlighting) */
  words: number[];
  last: string;
  lastLine: number;
}

const clamp01 = (v: number) => Math.min(Math.max(v, 0), 1);

function toItem(it: Item): LineItem {
  const ps = it.nameProbs.length ? it.nameProbs : it.probs; // an item is as sure as its name
  const conf = ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : 0;
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

export function totalOptions(base: number, tax: number, svc: number, disc: number): number[] {
  return [base + tax + svc - disc, base + tax + svc, base - disc, base];
}

export function arithmeticChecks(
  values: Record<FieldName, number | null>,
  itemSum: number,
  hasItems: boolean,
): number {
  let n = 0;
  const sub = values.subtotal;
  const total = values.total;
  if (hasItems && sub !== null && itemSum === sub) n++;
  if (total !== null) {
    const base = sub !== null ? sub : hasItems ? itemSum : null;
    if (
      base !== null &&
      totalOptions(base, values.tax ?? 0, values.service ?? 0, values.discount ?? 0).includes(total)
    )
      n++;
    const cash = values.cash;
    const change = values.change;
    if (cash !== null && change !== null && cash - change === total) n++;
  }
  return n;
}

export function assemble(page: Page, labels: string[], probs: number[], lam = 0): Assembled {
  const words = pageWords(page);
  if (words.length !== labels.length || labels.length !== probs.length) throw new Error("length mismatch");

  // line items: walk words in reading order
  const lineOf = page.lines.flatMap((l, li) => l.words.map(() => li));
  const items: Item[] = [];
  let cur: Item | null = null;
  const fresh = (): Item => {
    const it: Item = {
      name: [],
      cnt: [],
      unit: [],
      price: [],
      probs: [],
      nameProbs: [],
      words: [],
      last: "",
      lastLine: -1,
    };
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
      cur.nameProbs.push(p);
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
  const doc = emptyDocument();
  doc.items = kept.map(toItem);
  const itemSum = doc.items.reduce((a, it) => a + (it.price ?? 0), 0);

  // scalar fields: line groups per field -> candidate values
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

  type Cand = { sv: ScalarValue; idx: number[] } | null;
  const options: Cand[][] = SCALAR_FIELDS.map((f) => {
    const cands: Cand[] = [];
    const seen = new Set<number>();
    const sorted = groups[f].slice().sort((a, b) => b.sum - a.sum || a.li - b.li);
    for (const g of sorted) {
      const value = parseAmount(g.texts.join(""));
      if (value === null || seen.has(value)) continue;
      seen.add(value);
      const conf = clamp01(g.ps.reduce((a, b) => a + b, 0) / g.ps.length);
      cands.push({ sv: { value, confidence: conf, text: g.texts.join(" ") }, idx: g.idx });
      if (cands.length === MAX_CANDIDATES || lam === 0) break;
    }
    return cands.length ? cands : [null];
  });

  // enumerate combinations in itertools.product order (last field varies fastest)
  let best: Cand[] | null = null;
  let bestScore = -Infinity;
  const combo: Cand[] = new Array(SCALAR_FIELDS.length).fill(null);
  const visit = (fi: number) => {
    if (fi === SCALAR_FIELDS.length) {
      let score = 0;
      for (const c of combo) if (c !== null) score += Math.log(Math.max(c.sv.confidence, MIN_LOG_CONF));
      if (lam !== 0) {
        const values = Object.fromEntries(
          SCALAR_FIELDS.map((f, i) => [f, combo[i] === null ? null : combo[i]!.sv.value]),
        ) as Record<FieldName, number | null>;
        score += lam * arithmeticChecks(values, itemSum, doc.items.length > 0);
      }
      if (score > bestScore) {
        best = combo.slice();
        bestScore = score;
      }
      return;
    }
    for (const c of options[fi]) {
      combo[fi] = c;
      visit(fi + 1);
    }
  };
  visit(0);
  const fieldWords: Record<string, number[]> = {};
  SCALAR_FIELDS.forEach((f, i) => {
    const c = (best as Cand[] | null)?.[i] ?? null;
    doc[f] = c === null ? null : c.sv;
    if (c !== null) fieldWords[f] = c.idx;
  });
  return { doc, fieldWords, itemWords: kept.map((it) => it.words) };
}
