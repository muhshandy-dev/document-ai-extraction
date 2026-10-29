// Display helpers for word labels.

export const LABEL_NAMES: Record<string, string> = {
  O: "Lainnya",
  "menu.nm": "Nama item",
  "menu.cnt": "Jumlah item",
  "menu.unitprice": "Harga satuan",
  "menu.price": "Harga item",
  "menu.sub": "Sub-item",
  subtotal: "Subtotal",
  tax: "Pajak",
  service: "Servis",
  discount: "Diskon",
  total: "Total",
  cash: "Tunai",
  change: "Kembalian",
};

export function labelGroup(label: string): string {
  if (label === "menu.nm") return "g-name";
  if (label === "menu.cnt" || label === "menu.unitprice" || label === "menu.price") return "g-amount";
  if (label === "menu.sub") return "g-sub";
  if (label === "O") return "lab-O";
  return "g-summary";
}

const rupiah = new Intl.NumberFormat("id-ID");
export const fmtMoney = (v: number | null | undefined) => (v === null || v === undefined ? "" : rupiah.format(v));
export const fmtPct = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined ? "-" : `${(v * 100).toFixed(digits).replace(".", ",")}%`;

/** Parse what a reviewer typed: '45.500', '45,500', 'Rp 45.500' -> 45500. Empty -> null. */
export function parseTyped(text: string): number | null {
  const digits = text.replace(/[^0-9]/g, "");
  if (!digits) return null;
  const v = parseInt(digits, 10);
  return Number.isSafeInteger(v) ? v : null;
}
