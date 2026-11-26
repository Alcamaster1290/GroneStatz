import { notFound } from "next/navigation";

/** Dirección de la API desde el servidor de Next (red interna) y desde el navegador (para fotos y escudos). */
const INTERNAL_URL = process.env.GRONESTATS_API_URL ?? "http://127.0.0.1:8000";
const PUBLIC_URL = process.env.GRONESTATS_PUBLIC_API_URL ?? INTERNAL_URL; // variable de servidor: se lee al arrancar, no al compilar

/**
 * GET de la API. Los datos solo cambian al publicar un release, así que cada petición lleva la etiqueta `release`:
 * el despliegue la revalida cuando llega uno nuevo. Un 404 de la API es un 404 de la página.
 */
export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${INTERNAL_URL}${path}`, { cache: "no-store", next: { tags: ["release"] } });
  if (response.status === 404) notFound();
  if (!response.ok) throw new Error(`La API respondió ${response.status} en ${path}`);
  return (await response.json()) as T;
}

/** URL pública de un archivo de la API (foto o escudo); `null` si no hay. */
export function asset(path: string | null | undefined): string | null {
  return path ? `${PUBLIC_URL}${path}` : null;
}
