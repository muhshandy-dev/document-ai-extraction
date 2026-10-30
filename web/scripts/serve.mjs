// Static server for dist/ that applies the CSP from public/_headers (used by e2e checks).
import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, resolve } from "node:path";

const root = resolve(process.argv[2] ?? "dist");
const port = Number(process.argv[3] ?? 4173);
const headersText = readFileSync(join(root, "_headers"), "utf8");
const csp = /Content-Security-Policy: (.*)/.exec(headersText)?.[1] ?? "";
const types = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".svg": "image/svg+xml", ".pdf": "application/pdf", ".jpg": "image/jpeg",
  ".png": "image/png", ".gz": "application/gzip", ".wasm": "application/wasm",
};
createServer((req, res) => {
  const url = new URL(req.url ?? "/", "http://x");
  let file = join(root, decodeURIComponent(url.pathname));
  if (!file.startsWith(root)) return res.writeHead(403).end();
  if (existsSync(file) && statSync(file).isDirectory()) file = join(file, "index.html");
  if (!existsSync(file)) return res.writeHead(404).end("not found");
  res.writeHead(200, {
    "Content-Type": types[extname(file)] ?? "application/octet-stream",
    "Content-Security-Policy": csp,
  });
  createReadStream(file).pipe(res);
}).listen(port, () => console.log(`serving ${root} on ${port}`));
