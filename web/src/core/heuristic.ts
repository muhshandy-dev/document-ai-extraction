// Approach H: keyword and regex rules. Twin of src/docextract/heuristic.py.
import { type Line, type Page, lineText } from "./layout";
import { isMoney } from "./text";

export const SUMMARY_RULES: [string, RegExp][] = [
  ["subtotal", /SUB[ \t]*-?[ \t]*TOTAL|SUBTTL|SUB[ \t]*TTL|SUBTOT/],
  ["change", /CHANGE|KEMBALI/],
  ["cash", /CASH|TUNAI/],
  ["tax", /TAX|PB[ \t]*1|PPN|PAJAK|VAT/],
  ["service", /SERVICE|SERV\b|SVC|S\/C|\bSC\b/],
  ["discount", /DISC|DISKON|POTONGAN|PROMO/],
  ["total", /TOTAL|\bTTL\b|JUMLAH|GRAND|TAGIHAN|AMOUNT[ \t]*DUE/],
];
const NOT_TOTAL = /TOTAL[ \t]*(ITEM|QTY|QTT|PCS|ITM)|ITEMS?\b|\bQTY\b/;
const HEADER =
  /\bTEL|TELP|PHONE|NPWP|\bNO\b|TABLE|MEJA|KASIR|CASHIER|DATE|TANGGAL|JAM|TIME|BILL|ORDER|[0-9]{1,2}[:/.-][0-9]{1,2}[:/.-][0-9]{2,4}|[0-9]{1,2}:[0-9]{2}/;
export const QTY = /^[xX]?[0-9]{1,3}[xX]?$/;
export const ALPHA = /[A-Za-z]{2,}/;
const SKIP_TOKENS = new Set(["RP", "RP.", "IDR", "X", "@", "-", ":"]);

export function summaryField(line: Line): string | null {
  const up = lineText(line).toUpperCase();
  for (const [field, rx] of SUMMARY_RULES) {
    if (rx.test(up)) {
      if (field === "total" && NOT_TOTAL.test(up)) return null;
      return field;
    }
  }
  return null;
}

const isText = (t: string) => ALPHA.test(t) && !SKIP_TOKENS.has(t.trim().toUpperCase());
const moneyIdx = (line: Line) => line.words.flatMap((w, i) => (isMoney(w.text) ? [i] : []));

export function labelPage(page: Page): string[] {
  const labs: string[][] = page.lines.map((l) => l.words.map(() => "O"));
  const fields = page.lines.map(summaryField);
  let firstSummary = fields.findIndex((f) => f !== null);
  if (firstSummary < 0) firstSummary = page.lines.length;

  fields.forEach((f, i) => {
    if (!f) return;
    const money = moneyIdx(page.lines[i]);
    if (money.length) labs[i][money[money.length - 1]] = f;
    else if (i + 1 < page.lines.length && !fields[i + 1]) {
      const nxt = moneyIdx(page.lines[i + 1]);
      if (nxt.length) labs[i + 1][nxt[nxt.length - 1]] = f;
    }
  });

  let pending: number | null = null;
  for (let i = 0; i < firstSummary; i++) {
    const line = page.lines[i];
    if (HEADER.test(lineText(line).toUpperCase())) {
      pending = null;
      continue;
    }
    const money = moneyIdx(line);
    const hasName = line.words.some((w) => !isMoney(w.text) && ALPHA.test(w.text));
    if (money.length === 0) {
      pending = hasName ? i : null;
      continue;
    }
    let lastAlpha = -1;
    line.words.forEach((w, j) => {
      if (isText(w.text)) lastAlpha = j;
    });
    const l = labs[i];
    const price = money[money.length - 1];
    l[price] = "menu.price";
    if (money.length >= 2 && money[money.length - 2] > lastAlpha) l[money[money.length - 2]] = "menu.unitprice";
    const trailing = money.filter((j) => j > lastAlpha);
    const firstMoney = trailing.length ? trailing[0] : money[money.length - 1];
    line.words.forEach((w, j) => {
      if (l[j] !== "O" || j > firstMoney) return;
      const t = w.text.trim();
      const seenName = l.slice(0, j).includes("menu.nm");
      let beforeMoney = true;
      for (let k = j + 1; k < firstMoney; k++) {
        if (!SKIP_TOKENS.has(line.words[k].text.trim().toUpperCase())) beforeMoney = false;
      }
      const up = t.toUpperCase();
      if (QTY.test(t) && (!seenName || beforeMoney)) l[j] = "menu.cnt";
      else if (SKIP_TOKENS.has(up) && !(seenName && up === "X")) return;
      else if (seenName || ALPHA.test(t)) l[j] = "menu.nm";
    });
    if (!hasName && pending !== null) {
      const prev = labs[pending];
      page.lines[pending].words.forEach((w, j) => {
        if (ALPHA.test(w.text)) prev[j] = "menu.nm";
      });
    }
    pending = null;
  }
  return labs.flat();
}
