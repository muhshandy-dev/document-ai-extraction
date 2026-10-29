import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ModelJson } from "../core/model";
import { type ExtractedDocument, schemaErrors, validateDocument } from "../core/schema";
import { type Approach, type Extraction, extract } from "../engine/extract";
import { ocrCanvas } from "../engine/ocr";
import { loadImage, renderPdf } from "../engine/pdf";
import { Panel } from "./Panel";
import { Viewer } from "./Viewer";

export interface Sample {
  id: string;
  title: string;
  origin: string;
  kind: "pdf" | "image";
  src: string;
  note?: string;
}

interface QueueDoc extends Sample {
  file?: File;
  state: "idle" | "running" | "ready" | "error";
  error?: string;
  imageUrl?: string;
  width?: number;
  height?: number;
  extraction?: Extraction;
  edits: Partial<Record<Approach, ExtractedDocument>>;
  approved: Partial<Record<Approach, boolean>>;
  forceOcr: boolean;
}

interface Props {
  samples: Sample[];
  model: ModelJson | null;
}

const DEFAULT_OCR = { lang: "eng", psm: 4 };

function canvasUrl(canvas: HTMLCanvasElement): Promise<string> {
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(URL.createObjectURL(b)) : reject(new Error("render gagal"))), "image/png"),
  );
}

export function Studio({ samples, model }: Props) {
  const [docs, setDocs] = useState<QueueDoc[]>(() =>
    samples.map((s) => ({ ...s, state: "idle", edits: {}, approved: {}, forceOcr: false })),
  );
  const [selected, setSelected] = useState<string>(samples[0]?.id ?? "");
  const [approach, setApproach] = useState<Approach>(model ? "N" : "H");
  const [showBoxes, setShowBoxes] = useState(true);
  const [highlight, setHighlight] = useState<Set<number>>(new Set());
  const [progress, setProgress] = useState<{ p: number; status: string } | null>(null);
  const running = useRef(false);

  useEffect(() => {
    if (!model && approach === "N") setApproach("H");
  }, [model, approach]);

  const ocrSettings = useMemo(() => {
    const o = model?.meta?.ocr as { lang?: string; psm?: number } | undefined;
    return { lang: o?.lang ?? DEFAULT_OCR.lang, psm: o?.psm ?? DEFAULT_OCR.psm };
  }, [model]);
  const lowConf = model?.meta.review_min_conf ?? 0.5;

  const patch = useCallback((id: string, p: Partial<QueueDoc>) => {
    setDocs((ds) => ds.map((d) => (d.id === id ? { ...d, ...p } : d)));
  }, []);

  const process = useCallback(
    async (doc: QueueDoc) => {
      if (running.current) return;
      running.current = true;
      patch(doc.id, { state: "running", error: undefined });
      setProgress({ p: 0, status: "memuat" });
      try {
        const blob = doc.file ?? (await (await fetch(doc.src)).blob());
        let canvas: HTMLCanvasElement;
        let textWords: Extraction["words"] = [];
        if (doc.kind === "pdf") {
          const r = await renderPdf(await blob.arrayBuffer());
          canvas = r.canvas;
          textWords = r.textWords;
        } else {
          canvas = await loadImage(blob);
        }
        const imageUrl = await canvasUrl(canvas);
        const textChars = textWords.reduce((n, w) => n + w.text.length, 0);
        const usePdfText = doc.kind === "pdf" && !doc.forceOcr && textChars >= 20;
        const words = usePdfText
          ? textWords
          : await ocrCanvas(canvas, ocrSettings, (p, status) => setProgress({ p, status }));
        const emptyModel: ModelJson = { labels: ["O"], bias: [0], weights: {}, meta: {} };
        const extraction = extract(words, canvas.width, canvas.height, usePdfText ? "pdf" : "ocr", model ?? emptyModel);
        patch(doc.id, {
          state: "ready",
          imageUrl,
          width: canvas.width,
          height: canvas.height,
          extraction,
          edits: {},
          approved: {},
        });
      } catch (e) {
        patch(doc.id, { state: "error", error: e instanceof Error ? e.message : String(e) });
      } finally {
        running.current = false;
        setProgress(null);
      }
    },
    [model, ocrSettings, patch],
  );

  const current = docs.find((d) => d.id === selected);

  useEffect(() => {
    if (current && current.state === "idle") void process(current);
  }, [current, process]);

  const onFile = (file: File) => {
    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    const id = `file-${Date.now()}`;
    const doc: QueueDoc = {
      id,
      title: file.name,
      origin: "Berkas Anda (lokal)",
      kind: isPdf ? "pdf" : "image",
      src: "",
      file,
      state: "idle",
      edits: {},
      approved: {},
      forceOcr: false,
    };
    setDocs((ds) => [...ds, doc]);
    setSelected(id);
  };

  const result = current?.extraction?.results[approach];
  const doc = current && result ? (current.edits[approach] ?? result.doc) : null;
  const edited = Boolean(current?.edits[approach]);
  const issues = useMemo(() => {
    if (!doc || !result) return [];
    return edited ? validateDocument(doc) : result.issues;
  }, [doc, result, edited]);
  const sErrors = useMemo(() => (doc ? schemaErrors(doc) : []), [doc]);

  const statusChip = (d: QueueDoc) => {
    if (d.state === "running") return <span className="chip">diproses</span>;
    if (d.state === "error") return <span className="chip warn">gagal</span>;
    if (d.state !== "ready" || !d.extraction) return <span className="chip">belum dibuka</span>;
    if (d.approved[approach]) return <span className="chip done">disetujui</span>;
    const r = d.extraction.results[approach];
    const docA = d.edits[approach] ?? r.doc;
    const n = d.edits[approach] ? validateDocument(docA).length : r.issues.length;
    return n ? <span className="chip warn">{n} catatan</span> : <span className="chip ok">lolos otomatis</span>;
  };

  const exportJson = () => {
    if (!current || !doc || !current.extraction) return;
    const payload = {
      document: current.title,
      origin: current.origin,
      approach: approach === "N" ? "model terlatih (N)" : "aturan heuristik (H)",
      text_source: current.extraction.source,
      reviewed: Boolean(current.approved[approach]),
      edited,
      issues: issues.map((i) => ({ code: i.code, message: i.message, field: i.field })),
      extraction: doc,
      generator: "document-ai-extraction web 0.1",
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${current.title.replace(/\.[a-z]+$/i, "")}-ekstraksi.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="studio">
      <nav className="queue" aria-label="Antrean dokumen">
        <h2>Antrean dokumen</h2>
        <ul>
          {docs.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                className="queue-item"
                aria-current={d.id === selected}
                onClick={() => {
                  setSelected(d.id);
                  setHighlight(new Set());
                }}
              >
                <span className="title">{d.title}</span>
                <span className="meta">
                  {d.origin} {statusChip(d)}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <div className="upload">
          <label htmlFor="file-in">Buka berkas sendiri</label>
          <span className="muted">PDF, PNG, atau JPG. Diproses di browser ini saja, tidak diunggah.</span>
          <input
            id="file-in"
            className="sr-only"
            type="file"
            accept="application/pdf,image/png,image/jpeg,image/webp"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFile(f);
              e.target.value = "";
            }}
          />
        </div>
      </nav>

      <section className="viewer" aria-label="Penampil dokumen">
        <div className="toolbar">
          <label className="check">
            <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />
            Kotak kata
          </label>
          {current?.kind === "pdf" && (
            <label className="check" title="Abaikan lapisan teks PDF dan baca halaman sebagai gambar">
              <input
                type="checkbox"
                checked={current.forceOcr}
                disabled={current.state === "running"}
                onChange={(e) => {
                  patch(current.id, { forceOcr: e.target.checked, state: "idle", extraction: undefined });
                }}
              />
              Paksa OCR
            </label>
          )}
          <span className="spacer" />
          <span className="legend" aria-hidden="true">
            <span style={{ ["--swatch" as string]: "var(--c-name)" }}>nama item</span>
            <span style={{ ["--swatch" as string]: "var(--c-amount)" }}>jumlah/harga</span>
            <span style={{ ["--swatch" as string]: "var(--c-summary)" }}>ringkasan</span>
          </span>
        </div>
        <div className="stage">
          {!current && <div className="empty-stage">Pilih dokumen di antrean.</div>}
          {current?.state === "running" && (
            <div className="empty-stage">
              <div>
                <strong>Membaca dokumen…</strong>
                <div className="muted" style={{ fontSize: 13 }}>
                  {progress?.status === "recognizing text"
                    ? "OCR sedang berjalan di browser"
                    : progress?.status
                      ? `Menyiapkan OCR (${progress.status})`
                      : "Memuat berkas"}
                </div>
                <div className="progress" aria-hidden="true">
                  <div style={{ width: `${Math.round((progress?.p ?? 0) * 100)}%` }} />
                </div>
              </div>
            </div>
          )}
          {current?.state === "error" && (
            <div className="empty-stage">
              <div>
                <strong>Dokumen gagal dibaca</strong>
                <div className="muted">{current.error}</div>
                <button type="button" className="btn small" onClick={() => patch(current.id, { state: "idle" })}>
                  Coba lagi
                </button>
              </div>
            </div>
          )}
          {current?.state === "ready" && current.extraction && result && current.imageUrl && (
            <Viewer
              imageUrl={current.imageUrl}
              width={current.width ?? 1}
              height={current.height ?? 1}
              words={current.extraction.words}
              labels={result.labels}
              probs={result.probs}
              showBoxes={showBoxes}
              highlight={highlight}
              lowConf={approach === "N" ? lowConf : 0}
              onPick={(i) => {
                const item = result.itemWords.findIndex((ws) => ws.includes(i));
                if (item >= 0) setHighlight(new Set(result.itemWords[item]));
                else {
                  const f = Object.entries(result.fieldWords).find(([, ws]) => ws.includes(i));
                  setHighlight(new Set(f ? f[1] : [i]));
                }
              }}
            />
          )}
        </div>
      </section>

      {current?.state === "ready" && current.extraction && result && doc ? (
        <Panel
          approach={approach}
          onApproach={(a) => {
            setApproach(a);
            setHighlight(new Set());
          }}
          hasModel={Boolean(model)}
          result={result}
          doc={doc}
          issues={issues}
          schemaErrors={sErrors}
          edited={edited}
          approved={Boolean(current.approved[approach])}
          lowConf={lowConf}
          source={current.extraction.source}
          onChange={(d) =>
            patch(current.id, { edits: { ...current.edits, [approach]: d }, approved: { ...current.approved, [approach]: false } })
          }
          onHighlight={(ws) => setHighlight(new Set(ws))}
          onApprove={() => patch(current.id, { approved: { ...current.approved, [approach]: true } })}
          onReset={() => {
            const edits = { ...current.edits };
            delete edits[approach];
            patch(current.id, { edits, approved: { ...current.approved, [approach]: false } });
          }}
          onExport={exportJson}
        />
      ) : (
        <aside className="panel" aria-label="Hasil ekstraksi">
          <p className="muted">Hasil ekstraksi tampil di sini setelah dokumen selesai dibaca.</p>
          {!model && (
            <p className="notice">
              Model terlatih (N) belum disertakan pada versi ini, jadi studio hanya menjalankan aturan heuristik (H).
            </p>
          )}
        </aside>
      )}
    </div>
  );
}
