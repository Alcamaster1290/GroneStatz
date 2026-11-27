import type { Metadata } from "next";
import { notFound } from "next/navigation";
import LeagueTable, { leagueParams, type LeagueView } from "@/components/LeagueTable";
import Pills from "@/components/Pills";
import TitleChart from "@/components/TitleChart";
import { getJson } from "@/lib/api";
import { href } from "@/lib/query";
import type { LeagueCondition, LeagueTableData, LeagueValues, SeasonInfo, Standings, TitleRace } from "@/lib/types";

const TOURNAMENTS = ["Apertura", "Clausura", "Acumulada"];
const CONDITIONS: [LeagueCondition, string][] = [["general", "General"], ["local", "Local"], ["visita", "Visitante"]];
const VALUES: [LeagueValues, string][] = [["promedio", "Promedio por partido"], ["total", "Totales acumulados"]];
const SORTS = ["pts", "pj", "eff", "gf", "gc", "dg", "xg", "xga", "possession", "shots", "shots_on_target", "corners", "saves", "fouls", "yellow", "red"];

type Props = {
  params: { season: string; tournament: string };
  searchParams: { fecha?: string; cond?: string; valores?: string; orden?: string; dir?: string };
};

export function generateMetadata({ params }: Props): Metadata {
  return { title: `Liga 1 ${params.season} · ${params.tournament}` };
}

export default async function LigaPage({ params, searchParams }: Props) {
  const season = Number(params.season);
  const tournament = decodeURIComponent(params.tournament);
  if (!Number.isInteger(season) || !TOURNAMENTS.includes(tournament)) notFound();
  const round = searchParams.fecha !== undefined ? Number(searchParams.fecha) : undefined;
  if (round !== undefined && (!Number.isInteger(round) || round < 0)) notFound();
  const view: LeagueView = {
    fecha: round,
    cond: CONDITIONS.some(([key]) => key === searchParams.cond) ? (searchParams.cond as string) : "general",
    valores: VALUES.some(([key]) => key === searchParams.valores) ? (searchParams.valores as string) : "promedio",
    orden: SORTS.includes(searchParams.orden ?? "") ? (searchParams.orden as string) : "pts",
    dir: searchParams.dir === "asc" ? "asc" : "desc",
  };

  const tableQuery = `tournament=${tournament}${round !== undefined ? `&round=${round}` : ""}&condition=${view.cond}&values=${view.valores}&sort=${view.orden}&order=${view.dir}`;
  const [standings, table, { seasons }] = await Promise.all([
    getJson<Standings>(`/v1/seasons/${season}/standings?tournament=${tournament}${round !== undefined ? `&round=${round}` : ""}`),
    getJson<LeagueTableData>(`/v1/seasons/${season}/league-table?${tableQuery}`),
    getJson<{ seasons: SeasonInfo[] }>("/v1/seasons"),
  ]);
  const info = seasons.find((item) => item.season === season);
  const leader = standings.rows[0];
  const race = tournament === "Acumulada" ? null : await getJson<TitleRace>(`/v1/teams/${leader.team_id}/seasons/${season}/title-race?tournament=${tournament}`);
  const defaultTournament = (item: SeasonInfo) => (item.tournaments.includes(tournament) ? tournament : item.tournaments.includes("Clausura") ? "Clausura" : item.tournaments[0]);
  const rounds = tournament === "Acumulada" ? 0 : standings.rounds;
  const base = `/liga/${season}/${tournament}`;
  const keep = { ...view, fecha: undefined }; // al cambiar de temporada o de torneo se conservan la condición, los valores y el orden

  return (
    <div>
      <header className="mb-5">
        <h1 className="text-2xl font-bold tracking-tight">
          Liga 1 · {tournament === "Acumulada" ? "Tabla acumulada" : tournament} {season}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {tournament === "Acumulada"
            ? "Suma de Apertura y Clausura con las sanciones oficiales."
            : `Tabla tras la fecha ${standings.round_number} de ${rounds}. Los partidos aplazados cuentan en la fecha a la que pertenecen.`}
        </p>
      </header>

      <div className="mb-6 space-y-3">
        <Pills
          label="Temporada"
          items={seasons.map((item) => ({ label: String(item.season), href: href(`/liga/${item.season}/${defaultTournament(item)}`, leagueParams(keep)), active: item.season === season }))}
        />
        {info ? <Pills label="Torneo" items={info.tournaments.map((name) => ({ label: name, href: href(`/liga/${season}/${name}`, leagueParams(keep)), active: name === tournament }))} /> : null}
        {rounds > 0 ? (
          <Pills
            label="Fecha"
            items={Array.from({ length: rounds }, (_, index) => index + 1).map((value) => ({
              label: `F${value}`,
              href: href(base, leagueParams({ ...view, fecha: value === rounds ? undefined : value })),
              active: value === standings.round_number,
            }))}
          />
        ) : null}
      </div>

      <div className="mb-3 flex flex-wrap items-end gap-x-8 gap-y-3">
        <div>
          <p className="mb-1 text-xs uppercase tracking-wide text-muted">Condición</p>
          <Pills label="Condición" items={CONDITIONS.map(([key, label]) => ({ label, href: href(base, leagueParams({ ...view, cond: key })), active: key === view.cond }))} />
        </div>
        <div>
          <p className="mb-1 text-xs uppercase tracking-wide text-muted">Valores</p>
          <Pills label="Valores" items={VALUES.map(([key, label]) => ({ label, href: href(base, leagueParams({ ...view, valores: key })), active: key === view.valores }))} />
        </div>
      </div>

      <LeagueTable table={table} baseHref={base} view={view} />
      <p className="mt-2 max-w-4xl text-xs text-muted">
        Estadísticas de equipo de SofaScore; el xG es de nuestro modelo. Los promedios se calculan sobre los partidos que traen estadísticas de equipo (pasa el mouse por una cifra para ver cuántos). Pulsa un
        encabezado para ordenar; la columna # siempre es la posición por puntos.
        {table.note ? ` ${table.note}` : ""}
      </p>

      {race && race.teams.length > 0 ? (
        <section className="mt-10">
          <h2 className="text-lg font-semibold">Probabilidad de campeonar</h2>
          <p className="mb-3 mt-1 max-w-3xl text-sm text-muted">
            Tras cada partido de cada equipo: puntuación Elo con ventaja de local y de altitud, y 3.000 simulaciones del resto del calendario. El equipo líder va destacado; pasa el mouse por una línea para ver
            de quién es.
          </p>
          <div className="rounded-lg border border-line bg-surface p-4">
            <TitleChart teams={race.teams} highlightId={leader.team_id} />
          </div>
        </section>
      ) : null}
    </div>
  );
}
