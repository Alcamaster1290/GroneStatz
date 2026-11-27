import Link from "next/link";
import Crest from "@/components/Crest";
import { number, pct, slug } from "@/lib/format";
import { href, nextDirection, type Params } from "@/lib/query";
import type { LeagueRow, LeagueTableData } from "@/lib/types";

type Kind = "count" | "goals" | "decimal" | "percent" | "signed";

interface Column {
  key: keyof LeagueRow & string;
  label: string;
  title: string;
  kind: Kind;
  /** Decimales cuando la columna es un promedio por partido y cuando es un total. */
  digits?: [number, number];
}

const RESULTS: Column[] = [
  { key: "pj", label: "PJ", title: "Partidos jugados", kind: "count" },
  { key: "pts", label: "PTS", title: "Puntos", kind: "count" },
  { key: "eff", label: "Efec %", title: "Efectividad: puntos obtenidos sobre los posibles (3 por partido)", kind: "percent" },
  { key: "gf", label: "GF", title: "Goles a favor", kind: "goals", digits: [2, 0] },
  { key: "gc", label: "GC", title: "Goles en contra", kind: "goals", digits: [2, 0] },
  { key: "dg", label: "DG", title: "Diferencia de gol (siempre el total)", kind: "signed" },
];

const STATS: Column[] = [
  { key: "xg", label: "xG", title: "Goles esperados a favor, con el modelo propio", kind: "decimal", digits: [2, 1] },
  { key: "xga", label: "xGC", title: "Goles esperados en contra, con el modelo propio", kind: "decimal", digits: [2, 1] },
  { key: "possession", label: "Pos %", title: "Posesión media (un total de porcentajes no tiene sentido)", kind: "decimal", digits: [1, 1] },
  { key: "shots", label: "Tiros", title: "Tiros totales", kind: "decimal", digits: [1, 0] },
  { key: "shots_on_target", label: "Al arco", title: "Tiros al arco", kind: "decimal", digits: [1, 0] },
  { key: "corners", label: "Córners", title: "Tiros de esquina", kind: "decimal", digits: [1, 0] },
  { key: "saves", label: "Atajadas", title: "Atajadas del arquero", kind: "decimal", digits: [1, 0] },
  { key: "fouls", label: "Faltas", title: "Faltas cometidas", kind: "decimal", digits: [1, 0] },
  { key: "yellow", label: "TA", title: "Tarjetas amarillas", kind: "decimal", digits: [2, 0] },
  { key: "red", label: "TR", title: "Tarjetas rojas", kind: "decimal", digits: [2, 0] },
];

export interface LeagueView {
  fecha?: number;
  cond: string;
  valores: string;
  orden: string;
  dir: "asc" | "desc";
}

/** Parámetros de la URL de la tabla; los valores por defecto se omiten para que las rutas queden limpias. */
export function leagueParams(view: LeagueView): Params {
  return {
    fecha: view.fecha,
    cond: view.cond === "general" ? undefined : view.cond,
    valores: view.valores === "promedio" ? undefined : view.valores,
    orden: view.orden === "pts" ? undefined : view.orden,
    dir: view.dir === "desc" ? undefined : view.dir,
  };
}

function format(row: LeagueRow, column: Column, values: string): string {
  const value = row[column.key] as number | null;
  if (value === null || value === undefined) return "—";
  if (column.kind === "percent") return pct(value, 1);
  if (column.kind === "signed") return value > 0 ? `+${value}` : String(value).replace("-", "−");
  if (column.kind === "count") return number(value);
  const [average, total] = column.digits ?? [1, 0];
  return number(value, values === "promedio" || column.key === "possession" ? average : total);
}

export default function LeagueTable({ table, baseHref, view }: { table: LeagueTableData; baseHref: string; view: LeagueView }) {
  const season = table.season;
  const query = table.tournament === "Acumulada" ? `?season=${season}` : `?season=${season}&torneo=${table.tournament}`;
  const sortHref = (key: string) => href(baseHref, leagueParams({ ...view, orden: key, dir: nextDirection(view.orden, key, view.dir) }));
  const header = (column: Column, divider = false) => {
    const sorted = view.orden === column.key;
    return (
      <th key={column.key} scope="col" aria-sort={sorted ? (view.dir === "asc" ? "ascending" : "descending") : undefined} className={`px-2 py-2 text-right ${divider ? "border-l border-line" : ""}`}>
        <Link href={sortHref(column.key)} title={`${column.title}. Pulsa para ordenar.`} className={`inline-flex items-center gap-0.5 whitespace-nowrap hover:text-ink ${sorted ? "text-ink" : ""}`}>
          {column.label}
          {sorted ? <span aria-hidden>{view.dir === "asc" ? "▲" : "▼"}</span> : null}
        </Link>
      </th>
    );
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full min-w-[1180px] border-collapse text-sm">
        <caption className="sr-only">
          Tabla de liga {table.tournament} {season}, {table.condition}, {table.values === "promedio" ? "promedio por partido" : "totales acumulados"}
        </caption>
        <thead>
          <tr className="border-b border-line text-xs uppercase tracking-wide text-muted">
            <th scope="col" className="w-10 px-3 py-2 text-right">
              #
            </th>
            <th scope="col" className="sticky left-0 z-10 bg-surface px-3 py-2 text-left">
              Equipo
            </th>
            {RESULTS.map((column) => header(column))}
            {STATS.map((column, index) => header(column, index === 0))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row) => (
            <tr key={row.team_id} className="border-b border-line last:border-0 hover:bg-bg">
              <td className="num px-3 py-2 text-right text-muted">{row.pos}</td>
              <td className="sticky left-0 z-10 bg-surface px-3 py-2">
                <Link href={`/equipos/${slug(row.team_id, row.name ?? String(row.team_id))}${query}`} className="flex items-center gap-2 whitespace-nowrap font-medium hover:underline">
                  <Crest team={{ name: row.name ?? "", color: row.color, crest: row.crest }} size={24} />
                  {row.name}
                </Link>
              </td>
              {RESULTS.map((column) => (
                <td key={column.key} className={`num px-2 py-2 text-right ${column.key === "pts" ? "bg-accent/10 font-bold" : ""} ${view.orden === column.key && column.key !== "pts" ? "bg-accent/5" : ""}`}>
                  {format(row, column, table.values)}
                </td>
              ))}
              {STATS.map((column, index) => (
                <td
                  key={column.key}
                  className={`num px-2 py-2 text-right ${index === 0 ? "border-l border-line" : ""} ${view.orden === column.key ? "bg-accent/5" : ""}`}
                  title={column.key === "possession" || row.n_stats < row.pj ? `${row.n_stats} de ${row.pj} partidos con estadísticas de equipo` : undefined}
                >
                  {format(row, column, table.values)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
