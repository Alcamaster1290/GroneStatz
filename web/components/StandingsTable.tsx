import Link from "next/link";
import Crest from "@/components/Crest";
import { slug } from "@/lib/format";
import type { StandingRow } from "@/lib/types";

export default function StandingsTable({ rows, season, tournament, highlightId }: { rows: StandingRow[]; season: number; tournament: string; highlightId?: number }) {
  const query = tournament === "Acumulada" ? `?season=${season}` : `?season=${season}&torneo=${tournament}`;
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <caption className="sr-only">
          Tabla de posiciones {tournament} {season}
        </caption>
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
            <th scope="col" className="w-10 px-3 py-2 text-right">
              #
            </th>
            <th scope="col" className="px-3 py-2">
              Equipo
            </th>
            <th scope="col" className="px-2 py-2">
              Nivel
            </th>
            {["PJ", "PG", "PE", "PP", "GF", "GC", "DG"].map((heading) => (
              <th key={heading} scope="col" className="px-2 py-2 text-right">
                {heading}
              </th>
            ))}
            <th scope="col" className="px-3 py-2 text-right">
              Pts
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.team_id} className={`border-b border-line last:border-0 ${row.team_id === highlightId ? "bg-accent/10" : ""}`}>
              <td className="num px-3 py-2 text-right text-muted">{row.pos}</td>
              <td className="px-3 py-2">
                <Link href={`/equipos/${slug(row.team_id, row.name ?? String(row.team_id))}${query}`} className="flex items-center gap-2 font-medium hover:underline">
                  <Crest team={{ name: row.name ?? "", color: row.color ?? null, crest: row.crest ?? null }} size={24} />
                  {row.name}
                </Link>
              </td>
              <td className="px-2 py-2 text-muted">{row.level ?? "—"}</td>
              {[row.pj, row.pg, row.pe, row.pp, row.gf, row.gc].map((value, index) => (
                <td key={index} className="num px-2 py-2 text-right">
                  {value}
                </td>
              ))}
              <td className="num px-2 py-2 text-right">{row.dg > 0 ? `+${row.dg}` : row.dg}</td>
              <td className="num px-3 py-2 text-right font-bold">{row.pts}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
