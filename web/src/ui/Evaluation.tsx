import { useEffect, useState } from "react";
import { FIELD_LABELS, type FieldName, SCALAR_FIELDS } from "../core/schema";
import { fmtPct } from "./labels";

type Agg = Record<string, number | null> & {
  per_field: Record<string, { tp: number; fp: number; fn: number; support: number; f1: number | null }>;
};
interface Results {
  split: string;
  dataset?: string;
  note?: string;
  ocr?: { engine: string; lang: string; psm: number };
  model?: { C: number; review_min_conf: number; n_features: number };
  summary: Record<string, Agg>;
  bootstrap: { n_boot: number; ci: Record<string, Record<string, [number, number]>>; diff: Record<string, Record<string, [number, number]>> };
}
interface ModelSel {
  C_grid: { C: number; field_micro_f1: number; row_f1: number }[];
  chosen_C: number;
  tau_grid: { tau: number; auto: number; auto_right: number; auto_wrong: number; utility: number }[];
  chosen_tau: number;
}
interface OcrSel {
  grid: { lang: string; psm: number; word_recall: number; seconds: number }[];
  chosen: { lang: string; psm: number };
}

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(path, { cache: "no-cache" });
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

const METRICS: [string, string][] = [
  ["field_micro_f1", "Field-F1 (7 field ringkasan)"],
  ["field_macro_f1", "Field-F1 rata-rata per field"],
  ["row_f1", "Baris tabel benar (F1, longgar)"],
  ["row_f1_strict", "Baris tabel benar (F1, ketat)"],
  ["table_doc_accuracy", "Dokumen dengan tabel benar penuh"],
  ["doc_accuracy", "Dokumen benar seluruhnya"],
  ["review_rate", "Dikirim ke peninjau (review rate)"],
  ["auto_accept_accuracy", "Benar di antara yang lolos otomatis"],
];

function Ci({ ci }: { ci?: [number, number] }) {
  if (!ci || ci[0] === null) return null;
  return (
    <span className="muted" style={{ fontSize: 12 }}>
      {" "}
      [{fmtPct(ci[0], 0)}, {fmtPct(ci[1], 0)}]
    </span>
  );
}

function signed(v: number | null | undefined) {
  if (v === null || v === undefined) return "-";
  const s = (v * 100).toFixed(1).replace(".", ",");
  return v > 0 ? `+${s}` : s;
}

function MainTable({ res, runs, labels }: { res: Results; runs: string[]; labels: Record<string, string> }) {
  const diffKey = `${runs[1]} - ${runs[0]}`;
  const diff = res.bootstrap.diff[diffKey];
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>Metrik</th>
            {runs.map((r) => (
              <th key={r}>{labels[r] ?? r}</th>
            ))}
            {diff && <th>Selisih {labels[runs[1]]} dikurangi {labels[runs[0]]} (poin %)</th>}
          </tr>
        </thead>
        <tbody>
          {METRICS.map(([m, name]) => (
            <tr key={m}>
              <td>{name}</td>
              {runs.map((r) => (
                <td key={r} className="num">
                  {fmtPct(res.summary[r]?.[m] as number | null)}
                  <Ci ci={res.bootstrap.ci[r]?.[m]} />
                </td>
              ))}
              {diff && (
                <td className="num">
                  {(() => {
                    const a = res.summary[runs[0]]?.[m];
                    const b = res.summary[runs[1]]?.[m];
                    return typeof a === "number" && typeof b === "number" ? signed(b - a) : "-";
                  })()}
                  {diff[m] && diff[m][0] !== null && (
                    <span className="muted" style={{ fontSize: 12 }}>
                      {" "}
                      [{signed(diff[m][0])}, {signed(diff[m][1])}]
                    </span>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
        <caption>
          {res.summary[runs[0]]?.n_docs} dokumen. Angka dalam kurung siku = selang kepercayaan 95% dari bootstrap per
          dokumen ({res.bootstrap.n_boot} kali). Selisih memakai bootstrap berpasangan; jika selangnya memuat 0, bedanya
          belum meyakinkan.
        </caption>
      </table>
    </div>
  );
}

function FieldBars({ res, a, b, la, lb }: { res: Results; a: string; b: string; la: string; lb: string }) {
  return (
    <div className="bars">
      {SCALAR_FIELDS.map((f) => {
        const fa = res.summary[a].per_field[f];
        const fb = res.summary[b].per_field[f];
        return (
          <div className="bar-row" key={f}>
            <span>
              {FIELD_LABELS[f as FieldName]}
              <br />
              <span className="muted" style={{ fontSize: 12 }}>
                ada di {fa.support} dok.
              </span>
            </span>
            <div className="bar-pair">
              {[
                [la, fa, "var(--border-strong)"],
                [lb, fb, "var(--accent)"],
              ].map(([name, v, color]) => {
                const val = (v as typeof fa).f1;
                return (
                  <div className="bar-line" key={name as string} title={`${name}: ${fmtPct(val)}`}>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${(val ?? 0) * 100}%`, background: color as string }} />
                    </div>
                    <span className="num" style={{ fontSize: 12 }}>
                      {name as string} {fmtPct(val, 0)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Evaluation() {
  const [test, setTest] = useState<Results | null | undefined>(undefined);
  const [synth, setSynth] = useState<Results | null>(null);
  const [msel, setMsel] = useState<ModelSel | null>(null);
  const [osel, setOsel] = useState<OcrSel | null>(null);

  useEffect(() => {
    void getJson<Results>("data/results-test.json").then(setTest);
    void getJson<Results>("data/results-synth.json").then(setSynth);
    void getJson<ModelSel>("data/model-selection.json").then(setMsel);
    void getJson<OcrSel>("data/ocr-selection.json").then(setOsel);
  }, []);

  const L: Record<string, string> = {
    "H-ocr": "Aturan (H)",
    "N-ocr": "Model (N)",
    "H-gt": "Aturan, teks benar",
    "N-gt": "Model, teks benar",
    "H-pdf": "Aturan (H)",
    "N-pdf": "Model (N)",
  };

  return (
    <main className="doc-page">
      <header>
        <h1>Hasil evaluasi</h1>
        <p className="muted">
          Aturan heuristik (H) dibandingkan dengan model terlatih (N) pada data yang sama. Semua angka dihitung ulang dari
          repositori dengan satu perintah; tidak ada angka yang diketik tangan.
        </p>
      </header>

      {test === undefined && <p className="muted">Memuat hasil…</p>}
      {test === null && (
        <div className="callout">
          <strong>Hasil uji CORD-v2 belum tersedia.</strong> Evaluasi utama pada struk CORD-v2 belum dijalankan untuk
          versi ini, jadi halaman ini belum menampilkan angka untuk data tersebut.
        </div>
      )}

      {test && (
        <>
          <section>
            <h2>Struk CORD-v2, split uji (sekali jalan)</h2>
            <p>
              Teks dibaca dengan OCR Tesseract ({test.ocr?.lang}, psm {test.ocr?.psm}). Kolom "teks benar" memakai kata
              dari anotasi dataset sebagai batas atas: selisihnya dengan kolom OCR menunjukkan berapa banyak kesalahan
              yang berasal dari OCR, bukan dari ekstraksi.
            </p>
            <MainTable res={test} runs={["H-ocr", "N-ocr", "H-gt", "N-gt"]} labels={L} />
          </section>
          <section>
            <h2>Field-F1 per field (OCR)</h2>
            <FieldBars res={test} a="H-ocr" b="N-ocr" la="H" lb="N" />
          </section>
        </>
      )}

      {msel && (
        <section>
          <h2>Ambang peninjauan (dipilih di split validasi)</h2>
          <p>
            Model mengirim dokumen ke peninjau bila ada aturan konsistensi yang gagal atau keyakinan suatu field di bawah
            ambang. Ambang dipilih di data validasi dengan skor = dokumen benar yang lolos otomatis dikurangi 2 kali
            dokumen salah yang lolos. Terpilih: <strong className="num">{msel.chosen_tau}</strong>.
          </p>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Ambang keyakinan</th>
                  <th>Lolos otomatis</th>
                  <th>Benar</th>
                  <th>Salah</th>
                  <th>Skor</th>
                </tr>
              </thead>
              <tbody>
                {msel.tau_grid.map((r) => (
                  <tr key={r.tau} style={r.tau === msel.chosen_tau ? { fontWeight: 650 } : undefined}>
                    <td className="num">{r.tau}</td>
                    <td className="num">{r.auto}</td>
                    <td className="num">{r.auto_right}</td>
                    <td className="num">{r.auto_wrong}</td>
                    <td className="num">{r.utility}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {synth && (
        <section>
          <h2>Faktur sintetis (di luar domain latih)</h2>
          <p>
            Model dilatih hanya dengan struk CORD. Faktur sintetis ini memakai tata letak yang tidak pernah dilihat model.
            Aturan H dikembangkan dengan faktur sintetis lain (seed 0-99), jadi angkanya cenderung optimistis.
          </p>
          <h3>Teks dari OCR atas pindaian tiruan</h3>
          <MainTable res={synth} runs={["H-ocr", "N-ocr"]} labels={L} />
          <h3>Teks dari lapisan teks PDF</h3>
          <MainTable res={synth} runs={["H-pdf", "N-pdf"]} labels={L} />
        </section>
      )}

      {osel && (
        <section>
          <h2>Pemilihan pengaturan OCR (split validasi)</h2>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Bahasa</th>
                  <th>Mode halaman (psm)</th>
                  <th>Kata terbaca persis</th>
                  <th>Waktu (detik)</th>
                </tr>
              </thead>
              <tbody>
                {osel.grid.map((r) => (
                  <tr key={`${r.lang}${r.psm}`}>
                    <td>{r.lang}</td>
                    <td className="num">{r.psm}</td>
                    <td className="num">{fmtPct(r.word_recall)}</td>
                    <td className="num">{r.seconds}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
