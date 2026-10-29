import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { assemble } from "../src/core/assemble";
import { pageFeatures } from "../src/core/features";
import { labelPage } from "../src/core/heuristic";
import { type Word, groupLines } from "../src/core/layout";
import { type ModelJson, predictPage } from "../src/core/model";
import { type ExtractedDocument, validateDocument } from "../src/core/schema";
import { isMoney, normName, parseAmount, parseCount, similarity, wordShape } from "../src/core/text";

interface Case {
  name: string;
  width: number;
  height: number;
  words: { text: string; box: number[]; conf: number }[];
  lines: string[][];
  features: string[][];
  h_labels: string[];
  n_labels: string[];
  n_probs: number[];
  doc_h: ExtractedDocument;
  doc_n: ExtractedDocument;
  issues_h: string[];
  issues_n: string[];
}

const fixture = JSON.parse(readFileSync(resolve(__dirname, "../../tests/fixtures/parity.json"), "utf8")) as {
  model: ModelJson;
  text: Record<string, unknown>[];
  cases: Case[];
};

const toWords = (c: Case): Word[] =>
  c.words.map((d) => ({ text: d.text, x0: d.box[0], y0: d.box[1], x1: d.box[2], y1: d.box[3], conf: d.conf }));

/** Compare documents, allowing tiny float differences in confidences. */
function expectSameDoc(actual: ExtractedDocument, expected: ExtractedDocument) {
  const strip = (d: ExtractedDocument) =>
    JSON.parse(JSON.stringify(d, (k, v) => (k === "confidence" ? Math.round(v * 1e6) / 1e6 : v)));
  expect(strip(actual)).toEqual(strip(expected));
}

describe("text helpers match Python", () => {
  for (const t of fixture.text) {
    it(JSON.stringify(t.text), () => {
      const s = t.text as string;
      expect(parseAmount(s)).toBe(t.amount);
      expect(parseCount(s)).toBe(t.count);
      expect(isMoney(s)).toBe(t.money);
      expect(wordShape(s)).toBe(t.shape);
      expect(normName(s)).toBe(t.norm);
      expect(similarity(s, "TOTAL")).toBeCloseTo(t.sim_total as number, 8);
    });
  }
});

describe("pipeline matches Python on fixture pages", () => {
  for (const c of fixture.cases) {
    it(c.name, () => {
      const page = groupLines(toWords(c), c.width, c.height);
      expect(page.lines.map((l) => l.words.map((w) => w.text))).toEqual(c.lines);
      expect(pageFeatures(page)).toEqual(c.features);

      const h = labelPage(page);
      expect(h).toEqual(c.h_labels);
      const docH = assemble(page, h, h.map(() => 1)).doc;
      expectSameDoc(docH, c.doc_h);
      expect(validateDocument(docH).map((i) => i.code)).toEqual(c.issues_h);

      const n = predictPage(fixture.model, page);
      expect(n.labels).toEqual(c.n_labels);
      n.probs.forEach((p, i) => expect(p).toBeCloseTo(c.n_probs[i], 9));
      const docN = assemble(page, n.labels, n.probs).doc;
      expectSameDoc(docN, c.doc_n);
      expect(validateDocument(docN, 0.6).map((i) => i.code)).toEqual(c.issues_n);
    });
  }
});
