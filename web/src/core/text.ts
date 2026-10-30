// Twin of src/docextract/text.py. Keep both in sync; tests/parity.test.ts checks it.

const TOKEN_RE = /[0-9][0-9.,]*[0-9]|[0-9]/g;
const GROUPED_RE = /^[0-9]{1,3}(?:[.,][0-9]{3})+(?:[.,][0-9]{2})?$/;
const DECIMAL_RE = /^([0-9]+)[.,][0-9]{1,2}$/;

export const MAX_AMOUNT = 1e12;
export const MAX_COUNT = 10_000;

export const chars = (s: string): string[] => Array.from(s);

export function normSpace(text: string): string {
  return text.split(/\s+/).filter(Boolean).join(" ");
}

export function normName(text: string): string {
  const stripped = text.normalize("NFKD").replace(/\p{M}/gu, "");
  return normSpace(stripped.toUpperCase());
}

function tokenValue(token: string): number {
  if (GROUPED_RE.test(token)) {
    let parts = token.split(/[.,]/);
    if (parts[parts.length - 1].length === 2) parts = parts.slice(0, -1);
    return parseInt(parts.join(""), 10);
  }
  const dec = DECIMAL_RE.exec(token);
  if (dec) return parseInt(dec[1], 10);
  return parseInt(token.replace(/[^0-9]/g, ""), 10);
}

export function amountTokens(text: string): string[] {
  return text.match(TOKEN_RE) ?? [];
}

export function parseAmount(text: string | null | undefined): number | null {
  if (!text) return null;
  const tokens = amountTokens(text.replace(/ /g, ""));
  if (tokens.length === 0) return null;
  let best = tokens[0];
  for (const t of tokens) if (t.length > best.length) best = t;
  const value = tokenValue(best);
  // Longer numbers are IDs or phone numbers, not money.
  return value < MAX_AMOUNT ? value : null;
}

export function parseCount(text: string | null | undefined): number | null {
  if (!text) return null;
  const m = /[0-9]+/.exec(text);
  if (!m || m[0].length > 5) return null;
  const value = parseInt(m[0], 10);
  return value <= MAX_COUNT ? value : null;
}

export function isMoney(text: string): boolean {
  const t = stripChars(text.trim().toUpperCase().replace(/^(RP\.?|IDR)/, ""), "()-: ");
  return GROUPED_RE.test(t) || /^[0-9]{3,}$/.test(t);
}

function stripChars(s: string, set: string): string {
  let a = 0;
  let b = s.length;
  while (a < b && set.includes(s[a])) a++;
  while (b > a && set.includes(s[b - 1])) b--;
  return s.slice(a, b);
}

// Letters Tesseract often reads in place of digits inside amounts.
export const OCR_DIGIT_FIX: Record<string, string> = {
  O: "0",
  o: "0",
  D: "0",
  Q: "0",
  I: "1",
  l: "1",
  i: "1",
  "|": "1",
  S: "5",
  B: "8",
  Z: "2",
};

/** Repair an amount such as '1O.0O0' -> '10.000'. Twin of fix_ocr_token. */
export function fixOcrToken(text: string): string {
  let digits = 0;
  let confusable = 0;
  let sep = false;
  for (const ch of chars(text)) {
    if (ch >= "0" && ch <= "9") digits++;
    else if (Object.prototype.hasOwnProperty.call(OCR_DIGIT_FIX, ch)) confusable++;
    else if (ch === "." || ch === ",") sep = true;
    else return text;
  }
  if (confusable === 0 || digits < 2) return text;
  if (sep && confusable > digits) return text;
  if (!sep && (confusable * 2 > digits || digits + confusable < 4)) return text;
  return chars(text)
    .map((ch) => (Object.prototype.hasOwnProperty.call(OCR_DIGIT_FIX, ch) ? OCR_DIGIT_FIX[ch] : ch))
    .join("");
}

export function wordShape(text: string): string {
  const out: string[] = [];
  for (const ch of chars(text).slice(0, 12)) {
    let c: string;
    if (ch >= "0" && ch <= "9") c = "0";
    else if (ch >= "A" && ch <= "Z") c = "A";
    else if (ch >= "a" && ch <= "z") c = "a";
    else c = ch;
    if (out.length === 0 || out[out.length - 1] !== c) out.push(c);
  }
  return out.join("");
}

export function similarity(a0: string, b0: string): number {
  const a = chars(normName(a0));
  const b = chars(normName(b0));
  if (a.length === 0 && b.length === 0) return 1;
  if (a.length === 0 || b.length === 0) return 0;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0)));
    }
    prev = cur;
  }
  return 1 - prev[b.length] / Math.max(a.length, b.length);
}

/** Python-style lower-case slice by code points: lo[:n] / lo[-n:]. */
export const head = (s: string, n: number): string => chars(s).slice(0, n).join("");
export const tail = (s: string, n: number): string => chars(s).slice(-n).join("");
