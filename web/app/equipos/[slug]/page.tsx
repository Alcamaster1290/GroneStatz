import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Crest from "@/components/Crest";
import MatchStrip from "@/components/MatchStrip";
import Pills from "@/components/Pills";
import PlayerPhoto from "@/components/PlayerPhoto";
import StatCard from "@/components/StatCard";
import TitleChart from "@/components/TitleChart";
import { getJson } from "@/lib/api";
import { idFromSlug, meters, number, pct, slug } from "@/lib/format";
import { BAND_COLORS, BAND_HINTS, BAND_NAMES, POSITION_LABEL } from "@/lib/labels";
import type { SeasonInfo, TeamMatches, TeamPlayers, TitleRace } from "@/lib/types";

type Props = { params: { slug: string }; searchParams: { season?: string; torneo?: string } };

async function loadSeasons(): Promise<SeasonInfo[]> {
  return (await getJson<{ seasons: SeasonInfo[] }>("/v1/seasons")).seasons;
}

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const id = idFromSlug(params.slug);
  if (id === null) return { title: "Equipo" };
  const seasons = await loadSeasons();
  const season = searchParams.season ? Number(searchParams.season) : seasons[0].season;
  const strip = await getJson<TeamMatches>(`/v1/teams/${id}/seasons/${season}/matches`);
  return { title: `${strip.team.name} ${season}` };
}

export default async function TeamPage({ params, searchParams }: Props) {
  const id = idFromSlug(params.slug);
  if (id === null) notFound();
  const seasons = await loadSeasons();
  const season = searchParams.season ? Number(searchParams.season) : seasons[0].season;
  if (!Number.isInteger(season)) notFound();

  const [strip, squad] = await Promise.all([getJson<TeamMatches>(`/v1/teams/${id}/seasons/${season}/matches`), getJson<TeamPlayers>(`/v1/teams/${id}/seasons/${season}/players`)]);
  const team = strip.team;
  const tournaments = Object.keys(strip.tournaments);
  const tournament = searchParams.torneo && tournaments.includes(searchParams.torneo) ? searchParams.torneo : tournaments.includes("Clausura") ? "Clausura" : tournaments[0];
  const race = tournament ? await getJson<TitleRace>(`/v1/teams/${id}/seasons/${season}/title-race?tournament=${tournament}`) : null;
  const matches = tournament ? strip.tournaments[tournament] : [];
  const played = matches.filter((match) => match.result !== null && match.status !== "annulled"); // un partido anulado no cuenta en ninguna tabla
  const wins = played.filter((match) => match.result === "G").length;
  const draws = played.filter((match) => match.result === "E").length;
  const goalsFor = played.reduce((sum, match) => sum + (match.goals_for ?? 0), 0);
  const goalsAgainst = played.reduce((sum, match) => sum + (match.goals_against ?? 0), 0);
  const withXg = played.filter((match) => match.xg_for !== null);
  const xgFor = withXg.reduce((sum, match) => sum + (match.xg_for ?? 0), 0);
  const xgAgainst = withXg.reduce((sum, match) => sum + (match.xg_against ?? 0), 0);
  const last = race?.teams.find((item) => item.team_id === id)?.series.at(-1);
  const query = (value: string) => `?season=${season}&torneo=${value}`;

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-center gap-4">
        <Crest team={team} size={64} />
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight" style={{ borderBottom: `3px solid ${team.color ?? "var(--accent)"}`, display: "inline-block" }}>
            {team.name}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {team.level ? `Nivel ${team.level} · ` : ""}
            {team.stadium ?? "sin estadio"}
            {strip.base_altitude_m !== null && strip.base_altitude_m !== undefined ? ` · local a ${meters(strip.base_altitude_m)}` : ""}
          </p>
        </div>
      </header>

      <div className="mb-6 space-y-3">
        <Pills label="Temporada" items={seasons.map((item) => ({ label: String(item.season), href: `/equipos/${params.slug}?season=${item.season}`, active: item.season === season }))} />
        {tournaments.length > 1 ? <Pills label="Torneo" items={tournaments.map((name) => ({ label: name, href: `/equipos/${params.slug}${query(name)}`, active: name === tournament }))} /> : null}
      </div>

      {strip.missing_reason === "team_not_in_season" || !tournament ? (
        <p className="rounded-lg border border-dashed border-line p-6 text-muted">{team.name} no jugó el Apertura ni el Clausura de {season}. Elige otra temporada.</p>
      ) : (
        <>
          <section aria-label="Resumen del torneo" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <StatCard label="Partidos" value={String(played.length)} hint={`n=${played.length}`} />
            <StatCard label="G · E · P" value={`${wins}·${draws}·${played.length - wins - draws}`} />
            <StatCard label="Goles" value={`${goalsFor}–${goalsAgainst}`} hint="a favor – en contra" />
            <StatCard label="xG" value={withXg.length ? `${number(xgFor, 1)}–${number(xgAgainst, 1)}` : "—"} hint={withXg.length ? `n=${withXg.length} partidos` : "sin mapa de tiros"} />
            <StatCard label="Prob. título" value={pct(last?.p_title)} hint="tras su último partido" />
            <StatCard label="Puntos" value={String(wins * 3 + draws)} hint="sin sanciones" />
          </section>

          <section className="mt-10">
            <h2 className="mb-3 text-lg font-semibold">Probabilidad de campeonar · {tournament}</h2>
            {race && race.teams.length > 0 ? (
              <div className="rounded-lg border border-line bg-surface p-4">
                <TitleChart teams={race.teams} highlightId={id} />
              </div>
            ) : (
              <p className="text-muted">Sin datos de probabilidad para este torneo.</p>
            )}
          </section>

          <section className="mt-10">
            <h2 className="mb-1 text-lg font-semibold">Partido a partido · {tournament}</h2>
            <p className="mb-3 max-w-3xl text-sm text-muted">
              La importancia dice cuántas derrotas puede permitirse el equipo para seguir llegando a los 40 puntos que suele necesitar el campeón. Un * indica que ya no llegaba a 40 pero sí a 37, el campeón más bajo
              observado. ⚠ marca la formación declarada cuando el número de defensas de los 11 titulares no coincide con ella.
            </p>
            <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Bandas de importancia">
              {BAND_NAMES.map((name, index) => (
                <li key={name} className="flex items-center gap-1.5">
                  <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: BAND_COLORS[index] }} />
                  {name} ({BAND_HINTS[index]})
                </li>
              ))}
            </ul>
            <MatchStrip matches={matches} tournament={tournament} />
          </section>

          <section className="mt-10">
            <h2 className="mb-3 text-lg font-semibold">Plantel {season}</h2>
            {squad.players.length === 0 ? (
              <p className="text-muted">Sin datos de jugadores en esta temporada.</p>
            ) : (
              <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {squad.players.map((player) => (
                  <li key={player.player_id}>
                    <Link href={`/jugadores/${slug(player.player_id, player.name)}?season=${season}`} className="flex items-center gap-3 rounded-lg border border-line bg-surface p-3 hover:border-accent">
                      <PlayerPhoto name={player.name} photo={player.photo} color={team.color} size={48} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{player.name}</span>
                        <span className="block text-xs text-muted">
                          {player.position ? (POSITION_LABEL[player.position] ?? player.position) : "—"} · <span className="num">{player.matches}</span> partidos · <span className="num">{number(player.minutes)}</span> min
                        </span>
                      </span>
                      <span className="num text-right text-sm">
                        <span className="block font-semibold">{number(player.goals)} G</span>
                        <span className="block text-xs text-muted">xG {number(player.xg, 1)}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="mt-10" aria-label="Próximamente">
            <h2 className="mb-3 text-lg font-semibold">Próximamente</h2>
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {[
                ["Estilo de juego", "Bloques de 5 partidos y tendencias de la figura del equipo."],
                ["Contextos", "Cómo cambia el equipo según el nivel del rival, la altitud y la importancia del partido."],
                ["Compañeros", "Sinergia entre jugadores y posiciones equivalentes entre clubes."],
              ].map(([title, text]) => (
                <li key={title} className="rounded-lg border border-dashed border-line p-4 text-sm">
                  <p className="font-semibold">{title}</p>
                  <p className="mt-1 text-muted">{text}</p>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
