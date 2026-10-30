import { useState } from "react";
import type { Word } from "../core/layout";
import { LABEL_NAMES, labelGroup } from "./labels";

interface Props {
  imageUrl: string;
  width: number;
  height: number;
  words: Word[];
  labels: string[];
  probs: number[];
  showBoxes: boolean;
  highlight: Set<number>;
  lowConf: number;
  onPick: (wordIndex: number) => void;
}

interface Tip {
  x: number;
  y: number;
  text: string;
}

export function Viewer({ imageUrl, width, height, words, labels, probs, showBoxes, highlight, lowConf, onPick }: Props) {
  const [tip, setTip] = useState<Tip | null>(null);
  return (
    <div className="paper" style={{ width: Math.min(width, 980), aspectRatio: `${width} / ${height}` }}>
      <img src={imageUrl} alt="Pratinjau dokumen" width={width} height={height} />
      <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Kotak kata hasil OCR">
        {words.map((w, i) => {
          const lab = labels[i] ?? "O";
          const hl = highlight.has(i);
          if (!showBoxes && !hl) return null;
          const cls = ["box", labelGroup(lab), hl ? "hl" : "", lab !== "O" && probs[i] < lowConf ? "lowconf" : ""]
            .filter(Boolean)
            .join(" ");
          const text = `"${w.text}" · ${LABEL_NAMES[lab] ?? lab} · keyakinan ${(probs[i] * 100).toFixed(0)}% · OCR ${w.conf.toFixed(0)}`;
          return (
            <rect
              key={i}
              className={cls}
              x={w.x0 - 2}
              y={w.y0 - 2}
              width={w.x1 - w.x0 + 4}
              height={w.y1 - w.y0 + 4}
              rx={3}
              onMouseMove={(e) => setTip({ x: e.clientX + 12, y: e.clientY + 12, text })}
              onMouseLeave={() => setTip(null)}
              onClick={() => onPick(i)}
            >
              <title>{text}</title>
            </rect>
          );
        })}
      </svg>
      {tip && (
        <div className="tip" style={{ left: tip.x, top: tip.y }}>
          {tip.text}
        </div>
      )}
    </div>
  );
}
