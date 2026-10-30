// Inference for the exported logistic-regression weight table (model-n.json).
import { pageFeatures } from "./features";
import type { Page } from "./layout";

export interface ModelJson {
  labels: string[];
  bias: number[];
  weights: Record<string, number[]>;
  meta: Record<string, unknown> & { review_min_conf?: number };
}

export interface Prediction {
  labels: string[];
  probs: number[];
  /** full class distribution per word, for the review panel */
  dist: number[][];
}

export function predictPage(model: ModelJson, page: Page): Prediction {
  const k = model.labels.length;
  const labels: string[] = [];
  const probs: number[] = [];
  const dist: number[][] = [];
  for (const feats of pageFeatures(page)) {
    const scores = model.bias.slice();
    for (const f of feats) {
      const w = Object.prototype.hasOwnProperty.call(model.weights, f) ? model.weights[f] : undefined;
      if (w) for (let c = 0; c < k; c++) scores[c] += w[c];
    }
    let best = 0;
    for (let c = 1; c < k; c++) if (scores[c] > scores[best]) best = c;
    const mx = scores[best];
    const ex = scores.map((s) => Math.exp(s - mx));
    const z = ex.reduce((a, b) => a + b, 0);
    labels.push(model.labels[best]);
    probs.push(1 / z);
    dist.push(ex.map((e) => e / z));
  }
  return { labels, probs, dist };
}
