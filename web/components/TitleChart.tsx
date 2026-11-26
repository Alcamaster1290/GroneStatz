import { pct } from "@/lib/format";
import type { TitleSeries } from "@/lib/types";

const W = 640;
const H = 300;
const PAD = { left: 46, right: 14, top: 12, bottom: 32 };

/** Los colores de club oscuros (azul marino, negro) desaparecen sobre fondo oscuro: se mezclan con el color del texto del tema. */
const visible = (color: string | null): string => (color ? `color-mix(in srgb, ${color} 62%, var(--ink))` : "var(--draw)");

/**
 * Probabilidad de campeonar tras cada partido de cada equipo (Elo + Monte Carlo). El eje x son los partidos jugados por
 * el equipo (k); el equipo elegido va destacado y el resto atenuado. La leyenda lista la probabilidad final de todos.
 */
export default function TitleChart({ teams, highlightId }: { teams: TitleSeries[]; highlightId?: number }) {
  if (teams.length === 0) return null;
  const maxK = Math.max(...teams.map((team) => team.series[team.series.length - 1].k), 1);
  const maxP = Math.max(...teams.flatMap((team) => team.series.map((point) => point.p_title)));
  const yMax = Math.min(1, Math.max(0.2, Math.ceil(maxP * 10) / 10));
  const step = yMax <= 0.5 ? 0.1 : 0.2;
  const x = (k: number) => PAD.left + (k / maxK) * (W - PAD.left - PAD.right);
  const y = (p: number) => PAD.top + (1 - p / yMax) * (H - PAD.top - PAD.bottom);
  const ticks = Array.from({ length: Math.floor(yMax / step + 1e-9) + 1 }, (_, index) => index * step);
  const ordered = [...teams].sort((a, b) => Number(a.team_id === highlightId) - Number(b.team_id === highlightId)); // el destacado se dibuja encima

  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Probabilidad de campeonar de cada equipo tras cada partido" className="h-auto w-full max-w-[860px]">
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} stroke="var(--line)" strokeWidth={1} />
            <text x={PAD.left - 8} y={y(tick) + 4} textAnchor="end" fontSize={11} fill="var(--muted)">
              {Math.round(tick * 100)} %
            </text>
          </g>
        ))}
        {[0, Math.round(maxK / 2), maxK].map((k) => (
          <text key={k} x={x(k)} y={H - 10} textAnchor={k === 0 ? "start" : k === maxK ? "end" : "middle"} fontSize={11} fill="var(--muted)">
            {k === 0 ? "inicio" : `partido ${k}`}
          </text>
        ))}
        {ordered.map((team) => {
          const active = team.team_id === highlightId || highlightId === undefined;
          const points = team.series.map((point) => `${x(point.k).toFixed(1)},${y(point.p_title).toFixed(1)}`).join(" ");
          return (
            <polyline
              key={team.team_id}
              points={points}
              fill="none"
              style={{ stroke: visible(team.color) }}
              strokeWidth={team.team_id === highlightId ? 3.2 : 1.6}
              strokeLinejoin="round"
              strokeLinecap="round"
              opacity={active ? 1 : 0.38}
            >
              <title>{team.name}</title>
            </polyline>
          );
        })}
      </svg>
      <figcaption className="mt-3">
        <ol className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {teams.map((team) => (
            <li key={team.team_id} className={`flex items-center gap-2 ${team.team_id === highlightId ? "font-semibold" : ""}`}>
              <span aria-hidden className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: visible(team.color) }} />
              <span className="min-w-0 flex-1 truncate">{team.name}</span>
              <span className="num text-muted">{team.final_points ?? "—"} pts</span>
              <span className="num w-14 text-right">{pct(team.series[team.series.length - 1].p_title)}</span>
            </li>
          ))}
        </ol>
      </figcaption>
    </figure>
  );
}
