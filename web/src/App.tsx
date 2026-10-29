import { useEffect, useState } from "react";
import type { ModelJson } from "./core/model";
import { Evaluation } from "./ui/Evaluation";
import { Method } from "./ui/Method";
import { type Sample, Studio } from "./ui/Studio";

type Route = "studio" | "evaluasi" | "cara-kerja";

function readRoute(): Route {
  const h = window.location.hash.replace(/^#\/?/, "");
  return h === "evaluasi" || h === "cara-kerja" ? h : "studio";
}

export function App() {
  const [route, setRoute] = useState<Route>(readRoute);
  const [samples, setSamples] = useState<Sample[] | null>(null);
  const [model, setModel] = useState<ModelJson | null | undefined>(undefined);

  useEffect(() => {
    const on = () => setRoute(readRoute());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  useEffect(() => {
    fetch("samples/index.json", { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : []))
      .then((s: Sample[]) => setSamples(s))
      .catch(() => setSamples([]));
    fetch("model/model-n.json", { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : null))
      .then((m: ModelJson | null) => setModel(m))
      .catch(() => setModel(null));
  }, []);

  useEffect(() => {
    const titles: Record<Route, string> = {
      studio: "Studio peninjauan",
      evaluasi: "Hasil evaluasi",
      "cara-kerja": "Cara kerja",
    };
    document.title = `${titles[route]} · Document AI Extraction`;
  }, [route]);

  const link = (r: Route, label: string) => (
    <a href={`#/${r}`} aria-current={route === r ? "page" : undefined}>
      {label}
    </a>
  );

  return (
    <>
      <header className="topbar">
        <a className="brand" href="#/studio">
          <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true">
            <rect x="5" y="3" width="22" height="26" rx="3" fill="#047857" />
            <rect x="9" y="9" width="10" height="2.4" rx="1.2" fill="#fff" />
            <rect x="9" y="14" width="14" height="2.4" rx="1.2" fill="#fff" />
            <rect x="9" y="19" width="8" height="2.4" rx="1.2" fill="#fff" />
            <rect x="19" y="19" width="4" height="2.4" rx="1.2" fill="#a7f3d0" />
          </svg>
          <span className="brand-text">Document AI Extraction</span>
        </a>
        <nav className="nav" aria-label="Halaman">
          {link("studio", "Studio")}
          {link("evaluasi", "Evaluasi")}
          {link("cara-kerja", "Cara kerja")}
        </nav>
        <span className="note">Semua pemrosesan berjalan di browser Anda</span>
      </header>
      {route === "studio" &&
        (samples === null || model === undefined ? (
          <p className="muted" style={{ padding: 24 }}>
            Memuat studio…
          </p>
        ) : (
          <Studio samples={samples} model={model} />
        ))}
      {route === "evaluasi" && <Evaluation />}
      {route === "cara-kerja" && <Method />}
    </>
  );
}
