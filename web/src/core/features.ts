// Word features for approach N. Twin of src/docextract/features.py.
import { ALPHA, QTY, summaryField } from "./heuristic";
import { type Page, lineX0 } from "./layout";
import { head, isMoney, tail, wordShape } from "./text";

function bucket(v: number, size: number, n: number): number {
  if (size <= 0) return 0;
  return Math.max(0, Math.min(n - 1, Math.trunc((v / size) * n)));
}

export function pageFeatures(page: Page): string[][] {
  const kws = page.lines.map((l) => summaryField(l) ?? "none");
  let first = kws.findIndex((k) => k !== "none");
  if (first < 0) first = page.lines.length;
  const feats: string[][] = [];
  page.lines.forEach((line, li) => {
    const words = line.words;
    const n = words.length;
    const money = words.map((w) => isMoney(w.text));
    const nMoney = money.filter(Boolean).length;
    const kw = kws[li];
    const kwPrev = li > 0 ? kws[li - 1] : "bos";
    const kwNext = li + 1 < kws.length ? kws[li + 1] : "eos";
    const rel = first < page.lines.length ? Math.max(-3, Math.min(3, li - first)) : -9;
    const region = li < first ? "above" : li === first ? "at" : "below";
    const hd = head(words[0].text.toLowerCase(), 8);
    const indent = bucket(lineX0(line), page.width, 20);
    const moneyRank = new Array<number>(n).fill(0);
    let right = 0;
    for (let j = n - 1; j >= 0; j--) {
      if (money[j]) {
        moneyRank[j] = right;
        right += 1;
      }
    }
    words.forEach((w, j) => {
      const t = w.text;
      const lo = head(t.toLowerCase(), 15);
      const ridx = Math.min(n - 1 - j, 3);
      const m = money[j] ? "1" : "0";
      const prev = j > 0 ? head(words[j - 1].text.toLowerCase(), 10) : "<s>";
      const next = j + 1 < n ? head(words[j + 1].text.toLowerCase(), 10) : "</s>";
      const f = [
        "bias",
        "w=" + lo,
        "shape=" + wordShape(t),
        "p3=" + head(lo, 3),
        "s3=" + tail(lo, 3),
        "money=" + m,
        "len=" + Math.min(Array.from(t).length, 10),
        "xb=" + bucket((w.x0 + w.x1) / 2, page.width, 10),
        "yb=" + bucket((w.y0 + w.y1) / 2, page.height, 10),
        "ridx=" + ridx,
        "lidx=" + Math.min(j, 3),
        "nw=" + Math.min(n, 6),
        "nm=" + Math.min(nMoney, 3),
        "kw=" + kw,
        "kwp=" + kwPrev,
        "kwn=" + kwNext,
        "rel=" + rel,
        "region=" + region,
        "indent=" + indent,
        "head=" + hd,
        "prev=" + prev,
        "next=" + next,
        "pshape=" + (j > 0 ? wordShape(words[j - 1].text) : "<s>"),
        "nshape=" + (j + 1 < n ? wordShape(words[j + 1].text) : "</s>"),
        `kw|ridx|m=${kw}|${ridx}|${m}`,
        `region|ridx|m=${region}|${ridx}|${m}`,
        `kwp|m=${kwPrev}|${m}`,
        `head|m=${hd}|${m}`,
        "oc=" + Math.min(Math.floor(w.conf / 20), 5),
      ];
      if (money[j]) {
        const r = Math.min(moneyRank[j], 2);
        f.push("mrank=" + r, `kw|mrank=${kw}|${r}`);
      }
      if (QTY.test(t.trim())) f.push("qty", "qty|lidx=" + Math.min(j, 3));
      if (ALPHA.test(t)) f.push("alpha");
      feats.push(f);
    });
  });
  return feats;
}
