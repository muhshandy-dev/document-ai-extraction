import { useEffect, useState } from "react";
import { FieldBars, MainTable, RUN_LABELS, type Results, getJson, signed } from "./Evaluation";
import { fmtPct } from "./labels";

interface ModelSelV2 {
  crf_grid: { c1: number; c2: number; field_micro_f1: number; row_f1: number; selection_score: number }[];
  chosen: { c1: number; c2: number };
  lambda_grid: { lambda: number; field_micro_f1: number; row_f1: number; selection_score: number }[];
  chosen_lambda: number;
  tau_grid: { tau: number; auto: number; auto_right: number; auto_wrong: number; utility: number }[];
  chosen_tau: number;
}

interface OcrSelV2 {
  grid: { lang: string; psm: number; thresh: number; scale: number; word_recall: number; seconds: number }[];
  chosen: { lang: string; psm: number; thresh: number; scale: number };
}

const THRESH = ["Otsu", "Otsu adaptif", "Sauvola"];

type Ci = [number | null, number | null] | undefined;
const sure = (c: Ci) => Boolean(c && c[0] !== null && c[1] !== null && (c[0] > 0 || c[1] < 0));
const range = (c: Ci) => (c && c[0] !== null ? `[${signed(c[0])}, ${signed(c[1])}]` : "");

function ConclusionV2({ res }: { res: Results }) {
  const S = res.summary;
  const D = res.bootstrap.diff as Record<string, Record<string, Ci>>;
  const v = (r: string, m: string) => S[r]?.[m] as number | null;
  const d = (a: string, b: string, m: string) => (v(b, m) ?? 0) - (v(a, m) ?? 0);
  const hasV1 = Boolean(S["N-ocr-v1"]);
  const nh = D["N-ocr - H-ocr"];
  const nv = D["N-ocr - N-ocr-v1"];
  const hv = D["H-ocr - H-ocr-v1"];
  return (
    <div className="callout">
      <strong>Kesimpulan v2.</strong>{" "}
      {hasV1 && (
        <>
          Dibanding v1 pada {S["N-ocr"]?.n_docs} struk uji yang sama, field-F1 model N berubah {signed(d("N-ocr-v1", "N-ocr", "field_micro_f1"))}{" "}
          poin {range(nv?.field_micro_f1)} ({sure(nv?.field_micro_f1) ? "meyakinkan" : "belum meyakinkan"}) dan F1 baris
          tabelnya {signed(d("N-ocr-v1", "N-ocr", "row_f1"))} poin {range(nv?.row_f1)} (
          {sure(nv?.row_f1) ? "meyakinkan" : "belum meyakinkan"}). Untuk aturan H, field-F1 berubah{" "}
          {signed(d("H-ocr-v1", "H-ocr", "field_micro_f1"))} poin {range(hv?.field_micro_f1)}.{" "}
        </>
      )}
      Di v2, model N {sure(nh?.field_micro_f1) && d("H-ocr", "N-ocr", "field_micro_f1") > 0 ? "lebih baik" : "belum terbukti lebih baik"}{" "}
      dari aturan H untuk field ringkasan ({fmtPct(v("N-ocr", "field_micro_f1"))} lawan {fmtPct(v("H-ocr", "field_micro_f1"))})
      dan {sure(nh?.row_f1) && d("H-ocr", "N-ocr", "row_f1") > 0 ? "lebih baik" : "belum terbukti lebih baik"} untuk baris
      tabel ({fmtPct(v("N-ocr", "row_f1"))} lawan {fmtPct(v("H-ocr", "row_f1"))}). Model N mengirim{" "}
      {fmtPct(v("N-ocr", "review_rate"), 0)} struk ke peninjau; {S["N-ocr"]?.auto_accepted ?? 0} lolos otomatis dan{" "}
      {fmtPct(v("N-ocr", "auto_accept_accuracy"), 0)} di antaranya benar. Dengan teks benar, model yang sama mencapai
      field-F1 {fmtPct(v("N-gt", "field_micro_f1"))}.
    </div>
  );
}

export function EvaluationV2() {
  const [test, setTest] = useState<Results | null | undefined>(undefined);
  const [synth, setSynth] = useState<Results | null>(null);
  const [msel, setMsel] = useState<ModelSelV2 | null>(null);
  const [osel, setOsel] = useState<OcrSelV2 | null>(null);

  useEffect(() => {
    void getJson<Results>("data/v2/results-test.json").then(setTest);
    void getJson<Results>("data/v2/results-synth.json").then(setSynth);
    void getJson<ModelSelV2>("data/v2/model-selection.json").then(setMsel);
    void getJson<OcrSelV2>("data/v2/ocr-selection.json").then(setOsel);
  }, []);

  if (test === undefined) return <p className="muted">Memuat hasil…</p>;
  if (test === null) return null;
  const L = RUN_LABELS;
  const o = test.ocr;
  return (
    <div className="eval-version">
      <h2 className="version-title">Versi 2</h2>
      <p>
        Perubahan: OCR dengan pengaturan baru ({o?.lang}, psm {o?.psm}, ambang {THRESH[o?.thresh ?? 0]}, skala{" "}
        {String(o?.scale ?? 1).replace(".", ",")}), koreksi angka yang terbaca sebagai huruf, model N berupa CRF yang
        memperhitungkan urutan label, pemilihan nilai yang mengutamakan angka yang cocok secara aritmetika, dan aturan
        peninjauan yang menerima field yang sudah terbukti oleh aritmetika. Semua pilihan dibuat di split validasi.
      </p>
      <p className="muted">
        Split uji sudah dipakai sekali oleh v1, dan arah perbaikan v2 diambil dari hasil agregat v1. Karena itu v2 tidak
        sepenuhnya buta terhadap split uji, walaupun tidak ada pengaturan yang dipilih dengan melihat data uji.
      </p>

      <section>
        <h3>Struk CORD-v2, split uji</h3>
        <ConclusionV2 res={test} />
        <MainTable res={test} runs={["H-ocr", "N-ocr", "H-gt", "N-gt"]} labels={L} />
      </section>

      {test.summary["N-ocr-v1"] && (
        <section>
          <h3>Versi 2 dibanding versi 1 (dokumen uji yang sama)</h3>
          <h4>Model N</h4>
          <MainTable res={test} runs={["N-ocr-v1", "N-ocr"]} labels={L} />
          <h4>Aturan H</h4>
          <MainTable res={test} runs={["H-ocr-v1", "H-ocr"]} labels={L} />
        </section>
      )}

      <section>
        <h3>Field-F1 per field (OCR)</h3>
        <FieldBars res={test} a="H-ocr" b="N-ocr" la="H" lb="N" />
      </section>

      {msel && (
        <section>
          <h3>Pilihan di split validasi</h3>
          <p>
            Regularisasi CRF terpilih: c1 {msel.chosen.c1}, c2 {msel.chosen.c2}. Bobot aritmetika (lambda) terpilih:{" "}
            {msel.chosen_lambda}. Ambang peninjauan terpilih: {msel.chosen_tau}.
          </p>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Lambda</th>
                  <th>Field-F1</th>
                  <th>F1 baris</th>
                  <th>Skor pemilihan</th>
                </tr>
              </thead>
              <tbody>
                {msel.lambda_grid.map((r) => (
                  <tr key={r.lambda} style={r.lambda === msel.chosen_lambda ? { fontWeight: 650 } : undefined}>
                    <td className="num">{r.lambda}</td>
                    <td className="num">{fmtPct(r.field_micro_f1)}</td>
                    <td className="num">{fmtPct(r.row_f1)}</td>
                    <td className="num">{fmtPct(r.selection_score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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

      {osel && (
        <section>
          <h3>Pemilihan pengaturan OCR (split validasi)</h3>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>psm</th>
                  <th>Ambang</th>
                  <th>Skala</th>
                  <th>Kata terbaca persis</th>
                  <th>Waktu (detik)</th>
                </tr>
              </thead>
              <tbody>
                {osel.grid.map((r) => {
                  const chosen =
                    r.psm === osel.chosen.psm && r.thresh === osel.chosen.thresh && r.scale === osel.chosen.scale;
                  return (
                    <tr key={`${r.psm}-${r.thresh}-${r.scale}`} style={chosen ? { fontWeight: 650 } : undefined}>
                      <td className="num">{r.psm}</td>
                      <td>{THRESH[r.thresh]}</td>
                      <td className="num">{String(r.scale).replace(".", ",")}</td>
                      <td className="num">{fmtPct(r.word_recall)}</td>
                      <td className="num">{r.seconds}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {synth && (
        <section>
          <h3>Faktur sintetis (di luar domain latih)</h3>
          <p>
            Model tetap dilatih hanya dengan struk CORD. Aturan H dikembangkan dengan faktur sintetis lain (seed 0-99),
            jadi angkanya cenderung optimistis.
          </p>
          <h4>Teks dari OCR atas pindaian tiruan</h4>
          <MainTable res={synth} runs={["H-ocr", "N-ocr"]} labels={L} />
          <h4>Teks dari lapisan teks PDF</h4>
          <MainTable res={synth} runs={["H-pdf", "N-pdf"]} labels={L} />
        </section>
      )}
    </div>
  );
}
