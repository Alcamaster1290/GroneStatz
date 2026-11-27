export type Params = Record<string, string | number | null | undefined>;

/** Ruta con parámetros de consulta: los vacíos (`undefined`, `null` o texto vacío) se omiten. */
export function href(base: string, params: Params): string {
  const query = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`)
    .join("&");
  return query ? `${base}?${query}` : base;
}

/** Sentido al pulsar el encabezado de una columna: una columna nueva ordena de mayor a menor; la ya ordenada invierte el sentido. */
export function nextDirection(current: string, chosen: string, direction: "asc" | "desc"): "asc" | "desc" {
  if (current !== chosen) return "desc";
  return direction === "desc" ? "asc" : "desc";
}
