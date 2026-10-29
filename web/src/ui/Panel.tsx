import type { Approach, ApproachResult } from "../engine/extract";
import {
  type ExtractedDocument,
  FIELD_LABELS,
  type FieldName,
  type Issue,
  type LineItem,
  SCALAR_FIELDS,
} from "../core/schema";
import { fmtMoney, parseTyped } from "./labels";

interface Props {
  approach: Approach;
  onApproach: (a: Approach) => void;
  hasModel: boolean;
  result: ApproachResult;
  doc: ExtractedDocument;
  issues: Issue[];
  schemaErrors: string[];
  edited: boolean;
  approved: boolean;
  lowConf: number;
  source: "ocr" | "pdf";
  onChange: (doc: ExtractedDocument) => void;
  onHighlight: (wordIdx: number[]) => void;
  onApprove: () => void;
  onReset: () => void;
  onExport: () => void;
}

function Conf({ value, low }: { value: number; low: number }) {
  const isLow = value < low;
  return (
    <div className={`conf${isLow ? " low" : ""}`} title="Keyakinan model untuk kata-kata pada field ini">
      <span className="num">{Math.round(value * 100)}%</span>
      <div className="bar">
        <div style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  );
}

export function Panel(p: Props) {
  const { doc, issues } = p;
  const flagged = new Set(issues.map((i) => i.field).filter(Boolean) as string[]);
  const needsReview = issues.length > 0 || p.schemaErrors.length > 0;

  const setField = (f: FieldName, text: string) => {
    const v = parseTyped(text);
    p.onChange({ ...doc, [f]: v === null ? null : { value: v, confidence: 1, text } });
  };
  const setItem = (i: number, patch: Partial<LineItem>) => {
    const items = doc.items.map((it, k) => (k === i ? { ...it, ...patch, confidence: 1 } : it));
    p.onChange({ ...doc, items });
  };
  const removeItem = (i: number) => p.onChange({ ...doc, items: doc.items.filter((_, k) => k !== i) });
  const addItem = () =>
    p.onChange({ ...doc, items: [...doc.items, { name: "", qty: 1, unit_price: null, price: null, confidence: 1 }] });

  const focusIssue = (field: string | null) => {
    if (!field) return;
    if (field.startsWith("items.")) p.onHighlight(p.result.itemWords[Number(field.slice(6))] ?? []);
    else p.onHighlight(p.result.fieldWords[field] ?? []);
  };

  return (
    <aside className="panel" aria-label="Hasil ekstraksi">
      <div>
        <h2 id="approach-label">Cara ekstraksi</h2>
        <div className="segmented" role="group" aria-labelledby="approach-label">
          <button
            type="button"
            aria-pressed={p.approach === "N"}
            disabled={!p.hasModel}
            onClick={() => p.onApproach("N")}
            title={p.hasModel ? "" : "Model belum tersedia"}
          >
            Model terlatih (N)
          </button>
          <button type="button" aria-pressed={p.approach === "H"} onClick={() => p.onApproach("H")}>
            Aturan heuristik (H)
          </button>
        </div>
      </div>

      <div className={`status ${p.approved ? "done" : needsReview ? "warn" : "ok"}`} role="status">
        <strong>
          {p.approved
            ? "Sudah disetujui peninjau"
            : needsReview
              ? `Perlu ditinjau: ${issues.length + p.schemaErrors.length} catatan`
              : "Lolos pemeriksaan otomatis"}
        </strong>
        {!p.approved && !needsReview && (
          <span className="muted" style={{ fontSize: 13 }}>
            Semua aturan konsistensi terpenuhi{p.approach === "N" ? " dan keyakinan model di atas ambang" : ""}.
            Lolos otomatis bukan jaminan benar; lihat tingkat kesalahan di halaman Hasil evaluasi.
          </span>
        )}
        {(issues.length > 0 || p.schemaErrors.length > 0) && (
          <ul>
            {p.schemaErrors.map((e) => (
              <li key={e}>{e}</li>
            ))}
            {issues.map((i, k) => (
              <li key={k}>
                <button type="button" onClick={() => focusIssue(i.field)}>
                  {i.message}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3>Ringkasan pembayaran</h3>
        <div className="fields">
          {SCALAR_FIELDS.map((f) => {
            const sv = doc[f];
            return (
              <div
                key={f}
                className={`field${flagged.has(f) ? " flag" : ""}`}
                onMouseEnter={() => p.onHighlight(p.result.fieldWords[f] ?? [])}
                onMouseLeave={() => p.onHighlight([])}
              >
                <label htmlFor={`f-${f}`}>{FIELD_LABELS[f]}</label>
                <input
                  id={`f-${f}`}
                  className="num"
                  inputMode="numeric"
                  placeholder="tidak ada"
                  value={sv ? fmtMoney(sv.value) : ""}
                  onChange={(e) => setField(f, e.target.value)}
                  onFocus={() => p.onHighlight(p.result.fieldWords[f] ?? [])}
                />
                {sv && p.approach === "N" ? <Conf value={sv.confidence} low={p.lowConf} /> : <span />}
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <h3>Baris item ({doc.items.length})</h3>
        <table className="items">
          <thead>
            <tr>
              <th>Nama</th>
              <th className="col-qty">Jml</th>
              <th className="col-money">Harga</th>
              <th className="col-x">
                <span className="sr-only">Hapus</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {doc.items.map((it, i) => (
              <tr
                key={i}
                className={flagged.has(`items.${i}`) ? "flag" : ""}
                onMouseEnter={() => p.onHighlight(p.result.itemWords[i] ?? [])}
                onMouseLeave={() => p.onHighlight([])}
              >
                <td>
                  <input
                    aria-label={`Nama item ${i + 1}`}
                    value={it.name}
                    onChange={(e) => setItem(i, { name: e.target.value })}
                  />
                </td>
                <td className="col-qty">
                  <input
                    aria-label={`Jumlah item ${i + 1}`}
                    className="num"
                    inputMode="numeric"
                    value={it.qty ?? ""}
                    onChange={(e) => setItem(i, { qty: parseTyped(e.target.value) })}
                  />
                </td>
                <td className="col-money">
                  <input
                    aria-label={`Harga item ${i + 1}`}
                    className="num"
                    inputMode="numeric"
                    value={fmtMoney(it.price)}
                    onChange={(e) => setItem(i, { price: parseTyped(e.target.value) })}
                  />
                </td>
                <td className="col-x">
                  <button type="button" className="icon-btn" aria-label={`Hapus item ${i + 1}`} onClick={() => removeItem(i)}>
                    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                      <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                    </svg>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" className="btn small" style={{ marginTop: 8 }} onClick={addItem}>
          Tambah baris
        </button>
      </div>

      <div className="actions">
        <button type="button" className="btn primary" onClick={p.onApprove} disabled={p.approved}>
          {p.approved ? "Disetujui" : "Setujui hasil"}
        </button>
        <button type="button" className="btn" onClick={p.onExport}>
          Unduh JSON
        </button>
        {p.edited && (
          <button type="button" className="btn" onClick={p.onReset}>
            Kembalikan hasil mesin
          </button>
        )}
      </div>
      <p className="notice">
        Sumber teks: {p.source === "pdf" ? "lapisan teks PDF (tanpa OCR)" : "OCR Tesseract.js di browser ini"}. Berkas
        tidak dikirim ke server mana pun.
      </p>
    </aside>
  );
}
