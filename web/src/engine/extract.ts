// Run both approaches on one page of words and validate the results.
import { type Assembled, assemble } from "../core/assemble";
import { labelPage } from "../core/heuristic";
import { type Page, type Word, groupLines, pageWords } from "../core/layout";
import { type ModelJson, predictPage } from "../core/model";
import { type Issue, validateDocument } from "../core/schema";

export type Approach = "N" | "H";

export interface ApproachResult extends Assembled {
  labels: string[];
  probs: number[];
  issues: Issue[];
}

export interface Extraction {
  page: Page;
  words: Word[];
  source: "ocr" | "pdf";
  results: Record<Approach, ApproachResult>;
  ms: number;
}

export function extract(
  words: Word[],
  width: number,
  height: number,
  source: "ocr" | "pdf",
  model: ModelJson,
): Extraction {
  const t0 = performance.now();
  const page = groupLines(words, width, height);
  const ordered = pageWords(page);
  const hLabels = labelPage(page);
  const hProbs = hLabels.map(() => 1);
  const h = assemble(page, hLabels, hProbs);
  const n = predictPage(model, page);
  const nAsm = assemble(page, n.labels, n.probs);
  const tau = model.meta.review_min_conf ?? 0.5;
  return {
    page,
    words: ordered,
    source,
    results: {
      H: { ...h, labels: hLabels, probs: hProbs, issues: validateDocument(h.doc) },
      N: { ...nAsm, labels: n.labels, probs: n.probs, issues: validateDocument(nAsm.doc, tau) },
    },
    ms: performance.now() - t0,
  };
}
