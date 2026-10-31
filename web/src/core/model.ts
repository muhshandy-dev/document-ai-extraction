// Inference for the exported linear-chain CRF (model-n.json). Twin of src/docextract/model.py:
// Viterbi for the labels, forward-backward marginals for each word's confidence.
import { pageFeatures } from "./features";
import type { Page } from "./layout";

export interface ModelJson {
  type: "crf";
  labels: string[];
  /** attribute -> flat [labelIndex, weight, labelIndex, weight, ...] */
  weights: Record<string, number[]>;
  /** trans[i][j]: score of label i followed by label j */
  trans: number[][];
  meta: Record<string, unknown> & {
    review_min_conf?: number;
    assemble_lambda?: number;
    ocr?: { lang: string; psm: number; thresh?: number; scale?: number };
  };
}

export interface Prediction {
  labels: string[];
  probs: number[];
  /** full label distribution per word (marginals), for the review panel */
  dist: number[][];
}

const has = (o: object, k: string) => Object.prototype.hasOwnProperty.call(o, k);

export function logSumExp(xs: number[]): number {
  let m = -Infinity;
  for (const x of xs) if (x > m) m = x;
  if (m === -Infinity) return -Infinity;
  let s = 0;
  for (const x of xs) s += Math.exp(x - m);
  return m + Math.log(s);
}

export function emissions(model: ModelJson, feats: string[][]): number[][] {
  const k = model.labels.length;
  return feats.map((fs) => {
    const em = new Array<number>(k).fill(0);
    for (const f of fs) {
      if (!has(model.weights, f)) continue;
      const w = model.weights[f];
      for (let i = 0; i < w.length; i += 2) em[w[i]] += w[i + 1];
    }
    return em;
  });
}

export function viterbi(model: ModelJson, em: number[][]): number[] {
  const n = em.length;
  const k = model.labels.length;
  const tr = model.trans;
  if (n === 0) return [];
  let delta = em[0].slice();
  const back: number[][] = [];
  for (let t = 1; t < n; t++) {
    const nd = new Array<number>(k).fill(0);
    const bp = new Array<number>(k).fill(0);
    for (let y = 0; y < k; y++) {
      let best = -Infinity;
      let arg = 0;
      for (let yp = 0; yp < k; yp++) {
        const v = delta[yp] + tr[yp][y];
        if (v > best) {
          best = v;
          arg = yp;
        }
      }
      nd[y] = best + em[t][y];
      bp[y] = arg;
    }
    delta = nd;
    back.push(bp);
  }
  let last = 0;
  let best = -Infinity;
  for (let y = 0; y < k; y++) {
    if (delta[y] > best) {
      last = y;
      best = delta[y];
    }
  }
  const path = [last];
  for (let i = back.length - 1; i >= 0; i--) path.push(back[i][path[path.length - 1]]);
  path.reverse();
  return path;
}

export function marginals(model: ModelJson, em: number[][]): number[][] {
  const n = em.length;
  const k = model.labels.length;
  const tr = model.trans;
  if (n === 0) return [];
  const alpha: number[][] = [em[0].slice()];
  for (let t = 1; t < n; t++) {
    const prev = alpha[t - 1];
    const row: number[] = [];
    for (let y = 0; y < k; y++) {
      const xs: number[] = [];
      for (let yp = 0; yp < k; yp++) xs.push(prev[yp] + tr[yp][y]);
      row.push(em[t][y] + logSumExp(xs));
    }
    alpha.push(row);
  }
  const beta: number[][] = Array.from({ length: n }, () => new Array<number>(k).fill(0));
  for (let t = n - 2; t >= 0; t--) {
    const nxt = beta[t + 1];
    for (let y = 0; y < k; y++) {
      const xs: number[] = [];
      for (let yn = 0; yn < k; yn++) xs.push(tr[y][yn] + em[t + 1][yn] + nxt[yn]);
      beta[t][y] = logSumExp(xs);
    }
  }
  const logZ = logSumExp(alpha[n - 1]);
  return alpha.map((a, t) => a.map((v, y) => Math.exp(v + beta[t][y] - logZ)));
}

/** Per word: probability of each scalar field (labels that are field names). */
export function fieldProbs(labels: string[], dist: number[][], fields: readonly string[]): Record<string, number>[] {
  const idx = labels.map((lab, i) => [lab, i] as const).filter(([lab]) => fields.includes(lab));
  return dist.map((row) => Object.fromEntries(idx.map(([lab, i]) => [lab, row[i]])));
}

export function predictPage(model: ModelJson, page: Page): Prediction {
  const em = emissions(model, pageFeatures(page));
  const path = viterbi(model, em);
  const dist = marginals(model, em);
  return {
    labels: path.map((y) => model.labels[y]),
    probs: path.map((y, t) => Math.min(Math.max(dist[t][y], 0), 1)),
    dist,
  };
}
