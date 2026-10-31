// Document schema and validation rules. Twin of src/docextract/schema.py (Pydantic).

export const SCALAR_FIELDS = ["subtotal", "tax", "service", "discount", "total", "cash", "change"] as const;
export type FieldName = (typeof SCALAR_FIELDS)[number];

export const FIELD_LABELS: Record<FieldName, string> = {
  subtotal: "Subtotal",
  tax: "Pajak",
  service: "Servis",
  discount: "Diskon",
  total: "Total",
  cash: "Tunai",
  change: "Kembalian",
};

export interface LineItem {
  name: string;
  qty: number | null;
  unit_price: number | null;
  price: number | null;
  confidence: number;
}

export interface ScalarValue {
  value: number;
  confidence: number;
  text: string;
}

export type ExtractedDocument = { items: LineItem[] } & { [K in FieldName]: ScalarValue | null };

export interface Issue {
  code: string;
  message: string;
  field: string | null;
}

export function emptyDocument(): ExtractedDocument {
  return {
    items: [],
    subtotal: null,
    tax: null,
    service: null,
    discount: null,
    total: null,
    cash: null,
    change: null,
  };
}

export const valueOf = (doc: ExtractedDocument, f: FieldName): number | null => doc[f]?.value ?? null;

/** Schema checks equivalent to the Pydantic constraints; returns readable errors. */
export function schemaErrors(doc: ExtractedDocument): string[] {
  const errs: string[] = [];
  const isInt = (v: unknown) => typeof v === "number" && Number.isSafeInteger(v);
  for (const f of SCALAR_FIELDS) {
    const v = doc[f];
    if (v && (!isInt(v.value) || v.value < 0)) errs.push(`${FIELD_LABELS[f]} harus bilangan bulat >= 0`);
  }
  doc.items.forEach((it, i) => {
    if (it.qty !== null && (!isInt(it.qty) || it.qty < 0 || it.qty > 10_000))
      errs.push(`Item ${i + 1}: jumlah harus 0 sampai 10.000`);
    if (it.price !== null && (!isInt(it.price) || it.price < 0)) errs.push(`Item ${i + 1}: harga tidak valid`);
    if (it.unit_price !== null && (!isInt(it.unit_price) || it.unit_price < 0))
      errs.push(`Item ${i + 1}: harga satuan tidak valid`);
  });
  return errs;
}

/** Scalar fields confirmed by an arithmetic check that holds. Twin of verified_fields. */
export function verifiedFields(doc: ExtractedDocument): Set<FieldName> {
  const v = (f: FieldName) => valueOf(doc, f);
  const out = new Set<FieldName>();
  const itemSum = doc.items.reduce((a, it) => a + (it.price ?? 0), 0);
  const sub = v("subtotal");
  const total = v("total");
  if (doc.items.length && sub !== null && itemSum === sub) out.add("subtotal");
  if (total !== null) {
    const base = sub !== null ? sub : doc.items.length ? itemSum : null;
    if (base !== null) {
      const tax = v("tax") ?? 0;
      const svc = v("service") ?? 0;
      const disc = v("discount") ?? 0;
      const parts: FieldName[][] = [["tax", "service", "discount"], ["tax", "service"], ["discount"], []];
      const sums = [base + tax + svc - disc, base + tax + svc, base - disc, base];
      for (let i = 0; i < sums.length; i++) {
        if (total === sums[i]) {
          out.add("total");
          if (sub !== null) out.add("subtotal");
          for (const f of parts[i]) if (v(f) !== null) out.add(f);
          break;
        }
      }
    }
    const cash = v("cash");
    const change = v("change");
    if (cash !== null && change !== null && cash - change === total) {
      out.add("cash");
      out.add("change");
      out.add("total");
    }
  }
  return out;
}

export function validateDocument(doc: ExtractedDocument, minConf: number | null = null): Issue[] {
  const issues: Issue[] = [];
  const v = (f: FieldName) => valueOf(doc, f);
  const total = v("total");
  if (total === null) issues.push({ code: "TOTAL_MISSING", message: "Total belum ditemukan", field: "total" });
  if (doc.items.length === 0) issues.push({ code: "NO_ITEMS", message: "Belum ada baris item", field: null });

  doc.items.forEach((it, i) => {
    if (it.price === null) {
      issues.push({ code: "ITEM_NO_PRICE", message: `Item ${i + 1} belum punya harga`, field: `items.${i}` });
    } else if (it.qty && it.unit_price && it.qty * it.unit_price !== it.price) {
      issues.push({
        code: "ITEM_QTY_PRICE",
        message: `Item ${i + 1}: jumlah kali harga satuan tidak sama dengan harga`,
        field: `items.${i}`,
      });
    }
  });

  const itemSum = doc.items.reduce((a, it) => a + (it.price ?? 0), 0);
  const sub = v("subtotal");
  if (sub !== null && doc.items.length && itemSum !== sub) {
    issues.push({ code: "ITEMS_SUM", message: "Jumlah harga item berbeda dengan subtotal", field: "subtotal" });
  }

  if (total !== null) {
    const base = sub !== null ? sub : doc.items.length ? itemSum : null;
    if (base !== null) {
      const tax = v("tax") ?? 0;
      const svc = v("service") ?? 0;
      const disc = v("discount") ?? 0;
      const allowed = [base + tax + svc - disc, base + tax + svc, base - disc, base];
      if (!allowed.includes(total)) {
        issues.push({
          code: "TOTAL_MISMATCH",
          message: "Total tidak cocok dengan subtotal, pajak, servis, dan diskon",
          field: "total",
        });
      }
    }
    const cash = v("cash");
    const change = v("change");
    if (cash !== null && change !== null && cash - change !== total) {
      issues.push({ code: "CASH_CHANGE", message: "Tunai dikurangi kembalian tidak sama dengan total", field: "cash" });
    }
    if (cash !== null && change === null && cash < total) {
      issues.push({ code: "CASH_SHORT", message: "Uang tunai lebih kecil dari total", field: "cash" });
    }
  }

  if (minConf !== null) {
    const proven = verifiedFields(doc);
    for (const f of SCALAR_FIELDS) {
      const sv = doc[f];
      if (sv && sv.confidence < minConf && !proven.has(f)) issues.push({ code: "LOW_CONF", message: `Keyakinan rendah: ${f}`, field: f });
    }
    doc.items.forEach((it, i) => {
      if (it.confidence < minConf)
        issues.push({ code: "LOW_CONF", message: `Keyakinan rendah: item ${i + 1}`, field: `items.${i}` });
    });
  }
  return issues;
}
