import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Crest from "@/components/Crest";
import { ImportanceChip } from "@/components/MatchStrip";
import PlayerPhoto from "@/components/PlayerPhoto";
import ShotMap from "@/components/ShotMap";
import { getJson } from "@/lib/api";
import { formatDate, meters, number, pct, slug } from "@/lib/format";
import { POSITION_LABEL } from "@/lib/labels";
import type { MatchDetail, MatchSide } from "@/lib/types";

type Props = { params: { id: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const id = Number(params.id);
  if (!Number.isInteger(id)) return { title: "Partido" };
  const { match } = await getJson<MatchDetail>(`/v1/matches/${id}`);
  return { title: `${match.home.team?.name} ${match.home.score ?? "–"}–${match.away.score ?? "–"} ${match.away.team?.name}` };
}

function SideSummary({ side, label }: { side: MatchSide; label: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 flex items-center gap-2 font-semibold">
        <Crest team={side.team} size={24} />
        {side.team?.name}
      </p>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
        <dt className="text-muted">Formación declarada</dt>
        <dd className="num">
          {side.formation ?? "—"}
          {side.defenders_ok === false ? (
            <span className="ml-1 text-loss" title="El número de defensas de los 11 titulares no coincide con el de la formación declarada" aria-label="no coincide el número de defensas">
              ⚠
            </span>
          ) : null}
        </dd>
        <dt className="text-muted">xG del partido</dt>
        <dd className="num">{number(side.xg, 2)}</dd>
        <dt className="text-muted">Importancia</dt>
        <dd>
          <ImportanceChip importance={side.importance} />
        </dd>
        <dt className="text-muted">Prob. de título después</dt>
        <dd className="num">{pct(side.p_title_after)}</dd>
      </dl>
    </div>
  );
}

export default async function MatchPage({ params }: Props) {
  const id = Number(params.id);
  if (!Number.isInteger(id)) notFound();
  const { match, shots, players } = await getJson<MatchDetail>(`/v1/matches/${id}`);
  const { home, away } = match;
  const teamLink = (team: MatchSide["team"]) => (team ? `/equipos/${slug(team.team_id, team.name)}?season=${match.season}&torneo=${match.tournament}` : "#");

  return (
    <div>
      <p className="text-sm text-muted">
        Liga 1 · {match.tournament} {match.season} · fecha {match.round_number ?? "—"} · {formatDate(match.date)}
      </p>
      <h1 className="sr-only">
        {home.team?.name} contra {away.team?.name}
      </h1>
      <div className="my-4 grid grid-cols-[1fr_auto_1fr] items-center gap-4 rounded-lg border border-line bg-surface p-5">
        <Link href={teamLink(home.team)} className="flex items-center justify-end gap-3 text-right text-lg font-semibold hover:underline sm:text-2xl">
          <span className="min-w-0 truncate">{home.team?.name}</span>
          <Crest team={home.team} size={48} />
        </Link>
        <p className="num text-3xl font-bold sm:text-4xl" aria-label={`Marcador ${home.score ?? "sin dato"} a ${away.score ?? "sin dato"}`}>
          {home.score ?? "–"} – {away.score ?? "–"}
        </p>
        <Link href={teamLink(away.team)} className="flex items-center gap-3 text-lg font-semibold hover:underline sm:text-2xl">
          <Crest team={away.team} size={48} />
          <span className="min-w-0 truncate">{away.team?.name}</span>
        </Link>
      </div>
      <p className="text-sm text-muted">
        {match.estadio ?? "Estadio sin dato"}
        {match.ciudad ? `, ${match.ciudad}` : ""} · {match.altitude_m !== null ? `a ${meters(match.altitude_m)}` : "altitud sin dato"} · árbitro: {match.arbitro ?? "sin dato"}
        {match.status === "annulled" ? " · partido anulado: no cuenta en ninguna tabla" : ""}
        {match.status === "awarded" ? " · resultado fijado por la federación" : ""}
      </p>

      <section className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <SideSummary side={home} label="Local" />
        <SideSummary side={away} label="Visita" />
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Tiros y xG</h2>
        {shots.length === 0 ? (
          <p className="text-muted">Este partido no tiene mapa de tiros en el origen.</p>
        ) : (
          <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
            {([true, false] as const).map((isHome) => (
              <ShotMap
                key={String(isHome)}
                caption={`Tiros de ${(isHome ? home : away).team?.name}`}
                shots={shots.filter((shot) => shot.is_home === isHome).map((shot) => ({ x: shot.x, y: shot.y, xg: shot.xg, is_goal: shot.is_goal, minute: shot.minute, label: shot.player_name }))}
              />
            ))}
          </div>
        )}
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Jugadores</h2>
        {players.length === 0 ? (
          <p className="text-muted">Este partido no tiene estadísticas de jugadores en el origen.</p>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {[home, away].map((side) => (
              <div key={side.team?.team_id} className="overflow-x-auto rounded-lg border border-line bg-surface">
                <table className="w-full min-w-[420px] border-collapse text-sm">
                  <caption className="px-3 py-2 text-left font-semibold">{side.team?.name}</caption>
                  <thead>
                    <tr className="border-y border-line text-left text-xs uppercase tracking-wide text-muted">
                      <th scope="col" className="px-3 py-1.5">
                        Jugador
                      </th>
                      {["Min", "G", "A", "Rating"].map((heading) => (
                        <th key={heading} scope="col" className="px-2 py-1.5 text-right">
                          {heading}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {players
                      .filter((player) => player.team_id === side.team?.team_id)
                      .map((player) => (
                        <tr key={player.player_id} className="border-b border-line last:border-0">
                          <td className="px-3 py-1.5">
                            <Link href={`/jugadores/${slug(player.player_id, player.name)}?season=${match.season}`} className="flex items-center gap-2 hover:underline">
                              <PlayerPhoto name={player.name} photo={player.photo} color={side.team?.color} size={26} />
                              <span className="truncate">{player.name}</span>
                              <span className="text-xs text-muted">{player.position ? (POSITION_LABEL[player.position] ?? player.position) : ""}</span>
                            </Link>
                          </td>
                          <td className="num px-2 py-1.5 text-right">{number(player.minutesplayed)}</td>
                          {/* quien no entró no tiene goles ni asistencias que mostrar: un 0 sería un dato inventado */}
                          <td className="num px-2 py-1.5 text-right">{(player.minutesplayed ?? 0) > 0 ? number(player.goals) : "—"}</td>
                          <td className="num px-2 py-1.5 text-right">{(player.minutesplayed ?? 0) > 0 ? number(player.assists) : "—"}</td>
                          <td className="num px-2 py-1.5 text-right">{number(player.rating, 1)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
