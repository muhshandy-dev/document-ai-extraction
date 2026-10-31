import { useEffect, useState } from "react";
import { FIELD_LABELS, type FieldName, SCALAR_FIELDS } from "../core/schema";
import { EvaluationV2 } from "./EvaluationV2";
import { fmtPct } from "./labels";

export type Agg = Record<string, number | null> & {
  per_field: Record<string, { tp: number; fp: number; fn: number; support: number; f1: number | null }>;
};
export interface Results {
  split: string;
  dataset?: string;
  note?: string;
  protocol?: string;
  ocr?: { engine: string; lang: string; psm: number; thresh?: number; scale?: number };
  model?: Record<string, number | string>;
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

export async function getJson<T>(path: string): Promise<T | null> {
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

export function Ci({ ci }: { ci?: [number, number] }) {
  if (!ci || ci[0] === null) return null;
  return (
    <span className="muted" style={{ fontSize: 12 }}>
      {" "}
      [{fmtPct(ci[0], 0)}, {fmtPct(ci[1], 0)}]
    </span>
  );
}

export function signed(v: number | null | undefined) {
  if (v === null || v === undefined) return "-";
  const s = (v * 100).toFixed(1).replace(".", ",");
  return v > 0 ? `+${s}` : s;
}

export function MainTable({ res, runs, labels }: { res: Results; runs: string[]; labels: Record<string, string> }) {
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
                  {m === "auto_accept_accuracy" ? (
                    <span className="muted" style={{ fontSize: 12 }}>
                      {" "}
                      dari {res.summary[r]?.auto_accepted ?? 0} dok.
                    </span>
                  ) : (
                    <Ci ci={res.bootstrap.ci[r]?.[m]} />
                  )}
                </td>
              ))}
              {diff && (
                <td className="num">
                  {(() => {
                    const a = res.summary[runs[0]]?.[m];
                    const b = res.summary[runs[1]]?.[m];
                    if (m === "auto_accept_accuracy") return "-";
                    return typeof a === "number" && typeof b === "number" ? signed(b - a) : "-";
                  })()}
                  {m !== "auto_accept_accuracy" && diff[m] && diff[m][0] !== null && (
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
          belum meyakinkan. Akurasi yang lolos otomatis ditampilkan dengan jumlah dokumennya, tanpa selang, karena
          jumlahnya bisa sangat kecil.
        </caption>
      </table>
    </div>
  );
}

export function FieldBars({ res, a, b, la, lb }: { res: Results; a: string; b: string; la: string; lb: string }) {
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

function Conclusion({ res }: { res: Results }) {
  const S = res.summary;
  const d = res.bootstrap.diff["N-ocr - H-ocr"];
  const sig = (k: string) => {
    const c = d?.[k];
    return c && c[0] !== null && (c[0] > 0 || c[1] < 0);
  };
  const v = (r: string, m: string) => S[r]?.[m] as number | null;
  const gap = (v("N-gt", "field_micro_f1") ?? 0) - (v("N-ocr", "field_micro_f1") ?? 0);
  return (
    <div className="callout">
      <strong>Kesimpulan.</strong>{" "}
      {sig("field_micro_f1") ? "Model N lebih baik dari aturan H secara meyakinkan" : "Model N belum terbukti lebih baik dari aturan H"}{" "}
      untuk field ringkasan ({fmtPct(v("N-ocr", "field_micro_f1"))} lawan {fmtPct(v("H-ocr", "field_micro_f1"))}, selisih{" "}
      [{signed(d?.field_micro_f1?.[0])}, {signed(d?.field_micro_f1?.[1])}] poin).{" "}
      {sig("row_f1") ? "Untuk baris tabel, bedanya juga meyakinkan" : "Untuk baris tabel, bedanya belum meyakinkan"} (
      {fmtPct(v("N-ocr", "row_f1"))} lawan {fmtPct(v("H-ocr", "row_f1"))}). Hambatan terbesar adalah OCR: dengan teks
      benar, model yang sama mencapai {fmtPct(v("N-gt", "field_micro_f1"))}, atau {signed(gap)} poin lebih tinggi. Karena
      hasil OCR pada foto struk sering salah, model mengirim {fmtPct(v("N-ocr", "review_rate"), 0)} dokumen ke peninjau,
      sedangkan aturan H meloloskan {S["H-ocr"]?.auto_accepted ?? 0} dokumen yang hanya{" "}
      {fmtPct(v("H-ocr", "auto_accept_accuracy"), 0)} di antaranya benar. Lolos validasi skema saja tidak menjamin benar.
    </div>
  );
}

export const RUN_LABELS: Record<string, string> = {
  "H-ocr": "Aturan (H)",
  "N-ocr": "Model (N)",
  "H-gt": "Aturan, teks benar",
  "N-gt": "Model, teks benar",
  "H-pdf": "Aturan (H)",
  "N-pdf": "Model (N)",
  "H-ocr-v1": "Aturan (H) v1",
  "N-ocr-v1": "Model (N) v1",
  "T-ocr": "LayoutLM (T)",
  "T-gt": "LayoutLM, teks benar",
};

export function Evaluation() {
  return (
    <main className="doc-page">
      <header>
        <h1>Hasil evaluasi</h1>
        <p className="muted">
          Aturan heuristik (H) dibandingkan dengan model terlatih (N) pada data yang sama. Semua angka dihitung ulang dari
          repositori dengan satu perintah; tidak ada angka yang diketik tangan.
        </p>
      </header>
      <EvaluationV2 />
      <EvaluationV1 />
    </main>
  );
}

function EvaluationV1() {
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

  const L = RUN_LABELS;

  return (
    <div className="eval-version">
      <h2 className="version-title">Versi 1 (arsip, GitHub Actions run 41080343691)</h2>
      <p className="muted">
        Model N v1 adalah regresi logistik per kata, tanpa koreksi angka dan tanpa cek aritmetika saat memilih nilai.
        Angka di bawah ini tidak diubah setelah versi 2 dibuat.
      </p>

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
            <h3>Struk CORD-v2, split uji (sekali jalan)</h3>
            <p>
              Teks dibaca dengan OCR Tesseract ({test.ocr?.lang}, psm {test.ocr?.psm}). Kolom "teks benar" memakai kata
              dari anotasi dataset sebagai batas atas: selisihnya dengan kolom OCR menunjukkan berapa banyak kesalahan
              yang berasal dari OCR, bukan dari ekstraksi.
            </p>
            <Conclusion res={test} />
            <MainTable res={test} runs={["H-ocr", "N-ocr", "H-gt", "N-gt"]} labels={L} />
          </section>
          <section>
            <h3>Field-F1 per field (OCR)</h3>
            <FieldBars res={test} a="H-ocr" b="N-ocr" la="H" lb="N" />
          </section>
        </>
      )}

      {msel && (
        <section>
          <h3>Ambang peninjauan (dipilih di split validasi)</h3>
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
          <h3>Faktur sintetis (di luar domain latih)</h3>
          <p>
            Model dilatih hanya dengan struk CORD. Faktur sintetis ini memakai tata letak yang tidak pernah dilihat model.
            Aturan H dikembangkan dengan faktur sintetis lain (seed 0-99), jadi angkanya cenderung optimistis. Pada faktur
            ini model N tetap membaca angka ringkasan dengan baik, tetapi baris tabelnya hampir selalu salah: nama barang
            di faktur ditulis dengan huruf kecil dan panjang, berbeda dari nama menu di struk CORD, sehingga model memotong
            nama barang di tempat yang salah. Untuk faktur seperti ini, aturan H adalah pilihan yang lebih tepat.
          </p>
          <h4>Teks dari OCR atas pindaian tiruan</h4>
          <MainTable res={synth} runs={["H-ocr", "N-ocr"]} labels={L} />
          <h4>Teks dari lapisan teks PDF</h4>
          <MainTable res={synth} runs={["H-pdf", "N-pdf"]} labels={L} />
        </section>
      )}

      {osel && (
        <section>
          <h3>Pemilihan pengaturan OCR (split validasi)</h3>
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
    </div>
  );
}
