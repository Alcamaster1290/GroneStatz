import Link from "next/link";
import Crest from "@/components/Crest";
import { formatDate, meters, number, pct, shortDate, signedMeters, slug } from "@/lib/format";
import { BAND_COLORS, BAND_HINTS, BAND_NAMES, HIGH_ALTITUDE_DIFF, MID_ALTITUDE_DIFF, RESULT_LABEL } from "@/lib/labels";
import type { Importance, StripMatch } from "@/lib/types";

const BAND_TEXT = ["#ffffff", "#06280f", "#2b2400", "#2b1700", "#ffffff", "#ffffff"];
const RESULT_CLASS: Record<string, string> = { G: "text-win", E: "text-draw", P: "text-loss" };
const FLOOR_NOTE = "Con el umbral de 40 puntos estaría «Fuera de alcance», pero todavía llega a 37, el campeón más bajo observado.";

export function ImportanceChip({ importance }: { importance: Importance | null }) {
  if (!importance || importance.band === null || importance.band_name === null) return <span className="text-muted">—</span>;
  const index = importance.band;
  const usedFloor = importance.threshold_used !== 40;
  const hint = BAND_HINTS[index] ?? "";
  return (
    <span
      className="inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-semibold"
      style={{ background: BAND_COLORS[index], color: BAND_TEXT[index] }}
      title={`${BAND_NAMES[index]}: ${hint}. Quedaban ${importance.matches_remaining} partidos y faltaban ${number(importance.points_needed)} puntos para ${importance.threshold_used}.${usedFloor ? ` ${FLOOR_NOTE}` : ""}`}
    >
      {importance.band_name}
      {usedFloor ? <span aria-label="se usó el piso de 37 puntos">*</span> : null}
    </span>
  );
}

function Formation({ match }: { match: StripMatch }) {
  if (!match.formation) return <span className="text-muted">—</span>;
  return (
    <span className="whitespace-nowrap">
      {match.formation}
      {match.defenders_ok === false ? (
        <span title="El número de defensas de los 11 titulares no coincide con el de la formación declarada" aria-label="no coincide el número de defensas" className="ml-1 text-loss">
          ⚠
        </span>
      ) : null}
    </span>
  );
}

function Altitude({ match }: { match: StripMatch }) {
  if (match.altitude_m === null) return <span className="text-muted">—</span>;
  const diff = match.altitude_diff_m ?? 0;
  const high = diff >= HIGH_ALTITUDE_DIFF;
  const mid = diff >= MID_ALTITUDE_DIFF && !high;
  return (
    <span className="whitespace-nowrap" title={`Respecto a la sede habitual del equipo: ${signedMeters(match.altitude_diff_m)}`}>
      <span className={high ? "rounded bg-[#8e44ad] px-1.5 py-0.5 font-semibold text-white" : mid ? "rounded border border-[#8e44ad] px-1.5 py-0.5" : ""}>{meters(match.altitude_m)}</span>
    </span>
  );
}

function Probability({ match }: { match: StripMatch }) {
  if (match.p_title_after === null) return <span className="text-muted">—</span>;
  const delta = match.p_title_before === null ? null : (match.p_title_after - match.p_title_before) * 100;
  return (
    <span className="num whitespace-nowrap" title={`Antes del partido: ${pct(match.p_title_before)}`}>
      {pct(match.p_title_after)}
      {delta !== null && Math.abs(delta) >= 0.05 ? (
        <span className={`ml-1 text-xs ${delta > 0 ? "text-win" : "text-loss"}`}>
          {delta > 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1).replace(".", ",")}
        </span>
      ) : null}
    </span>
  );
}

/** Partido a partido de un equipo en un torneo: resultado, rival y su nivel, sede y altitud, xG, formación declarada, importancia y probabilidad. */
export default function MatchStrip({ matches, tournament }: { matches: StripMatch[]; tournament: string }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full min-w-[860px] border-collapse text-sm">
        <caption className="sr-only">Partido a partido del {tournament}</caption>
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
            <th scope="col" className="px-3 py-2 text-right">
              Fecha
            </th>
            <th scope="col" className="px-2 py-2">
              Rival
            </th>
            <th scope="col" className="px-2 py-2">
              Nivel
            </th>
            <th scope="col" className="px-2 py-2">
              Sede
            </th>
            <th scope="col" className="px-2 py-2">
              Altitud
            </th>
            <th scope="col" className="px-2 py-2">
              Resultado
            </th>
            <th scope="col" className="px-2 py-2" title="Goles esperados a favor y en contra, con el modelo propio">
              xG
            </th>
            <th scope="col" className="px-2 py-2">
              Formación
            </th>
            <th scope="col" className="px-2 py-2" title="Cuántas derrotas puede permitirse para seguir llegando al umbral del campeón">
              Importancia
            </th>
            <th scope="col" className="px-3 py-2">
              Prob. título
            </th>
          </tr>
        </thead>
        <tbody>
          {matches.map((match) => (
            <tr key={match.match_id} className="border-b border-line last:border-0 hover:bg-bg">
              <td className="num whitespace-nowrap px-3 py-2 text-right" title={formatDate(match.date)}>
                <span className="mr-1.5 text-xs text-muted">F{match.round_number ?? "—"}</span>
                {shortDate(match.date)}
              </td>
              <td className="px-2 py-2">
                <span className="flex items-center gap-2">
                  <Crest team={match.rival} size={22} />
                  {match.rival ? (
                    <Link href={`/equipos/${slug(match.rival.team_id, match.rival.name)}`} className="hover:underline">
                      {match.rival.name}
                    </Link>
                  ) : (
                    "—"
                  )}
                </span>
              </td>
              <td className="px-2 py-2 text-muted">{match.rival?.level ?? "—"}</td>
              <td className="px-2 py-2">{match.is_home ? "Local" : "Visita"}</td>
              <td className="num px-2 py-2">
                <Altitude match={match} />
              </td>
              <td className="px-2 py-2">
                {match.result ? (
                  <Link href={`/partidos/${match.match_id}`} className={`num whitespace-nowrap font-semibold hover:underline ${RESULT_CLASS[match.result]}`} title={RESULT_LABEL[match.result]}>
                    {match.result} {match.goals_for}–{match.goals_against}
                  </Link>
                ) : (
                  <span className="whitespace-nowrap text-muted" title="Sin marcador en el bundle">
                    {match.status === "postponed" ? "Aplazado" : match.status === "canceled" ? "Cancelado" : "Sin marcador"}
                  </span>
                )}
                {match.status === "annulled" ? <span className="ml-1 text-xs text-muted">(anulado)</span> : null}
              </td>
              <td className="num px-2 py-2 text-muted whitespace-nowrap">
                {match.xg_for === null ? "—" : `${number(match.xg_for, 2)} – ${number(match.xg_against, 2)}`}
              </td>
              <td className="num px-2 py-2">
                <Formation match={match} />
              </td>
              <td className="px-2 py-2">
                <ImportanceChip importance={match.importance} />
              </td>
              <td className="px-3 py-2">
                <Probability match={match} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
