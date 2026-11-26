const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const DASH = "—";

/** Porcentaje con coma decimal: 0.1837 → "18,4 %". Sin dato, un guion (nunca un 0 inventado). */
export function pct(p: number | null | undefined, digits = 1): string {
  if (p === null || p === undefined || Number.isNaN(p)) return DASH;
  return `${(p * 100).toFixed(digits).replace(".", ",")} %`;
}

/** La API entrega las fechas ya en hora de Lima y sin zona: se muestran tal cual, sin convertir. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "sin fecha";
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(iso);
  if (!match) return "sin fecha";
  const [, year, month, day, hour, minute] = match;
  const date = `${Number(day)} ${MONTHS[Number(month) - 1]} ${year}`;
  return hour ? `${date} · ${hour}:${minute}` : date;
}

export function shortDate(iso: string | null | undefined): string {
  const match = iso ? /^(\d{4})-(\d{2})-(\d{2})/.exec(iso) : null;
  return match ? `${Number(match[3])}/${match[2]}` : DASH;
}

export function slug(id: number, name: string): string {
  const text = name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return text ? `${id}-${text}` : String(id);
}

export function idFromSlug(value: string): number | null {
  const match = /^(\d+)(?:-|$)/.exec(value);
  return match ? Number(match[1]) : null;
}

function grouped(n: number): string {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export function meters(n: number | null | undefined): string {
  return n === null || n === undefined || Number.isNaN(n) ? DASH : `${grouped(Math.round(n))} m`;
}

export function signedMeters(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return DASH;
  const rounded = Math.round(n);
  if (rounded === 0) return "0 m";
  return `${rounded > 0 ? "+" : "−"}${grouped(Math.abs(rounded))} m`;
}

export function number(n: number | null | undefined, digits = 0): string {
  return n === null || n === undefined || Number.isNaN(n) ? DASH : n.toFixed(digits).replace(".", ",");
}
