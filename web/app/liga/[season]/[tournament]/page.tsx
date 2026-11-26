import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Pills from "@/components/Pills";
import StandingsTable from "@/components/StandingsTable";
import TitleChart from "@/components/TitleChart";
import { getJson } from "@/lib/api";
import type { SeasonInfo, Standings, TitleRace } from "@/lib/types";

const TOURNAMENTS = ["Apertura", "Clausura", "Acumulada"];

type Props = { params: { season: string; tournament: string }; searchParams: { fecha?: string } };

export function generateMetadata({ params }: Props): Metadata {
  return { title: `Liga 1 ${params.season} · ${params.tournament}` };
}

export default async function LigaPage({ params, searchParams }: Props) {
  const season = Number(params.season);
  const tournament = decodeURIComponent(params.tournament);
  if (!Number.isInteger(season) || !TOURNAMENTS.includes(tournament)) notFound();
  const round = searchParams.fecha !== undefined ? Number(searchParams.fecha) : undefined;
  if (round !== undefined && (!Number.isInteger(round) || round < 0)) notFound();

  const [standings, { seasons }] = await Promise.all([
    getJson<Standings>(`/v1/seasons/${season}/standings?tournament=${tournament}${round !== undefined ? `&round=${round}` : ""}`),
    getJson<{ seasons: SeasonInfo[] }>("/v1/seasons"),
  ]);
  const info = seasons.find((item) => item.season === season);
  const leader = standings.rows[0];
  const race = tournament === "Acumulada" ? null : await getJson<TitleRace>(`/v1/teams/${leader.team_id}/seasons/${season}/title-race?tournament=${tournament}`);
  const defaultTournament = (item: SeasonInfo) => (item.tournaments.includes(tournament) ? tournament : item.tournaments.includes("Clausura") ? "Clausura" : item.tournaments[0]);
  const rounds = tournament === "Acumulada" ? 0 : standings.rounds;

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
          items={seasons.map((item) => ({ label: String(item.season), href: `/liga/${item.season}/${defaultTournament(item)}`, active: item.season === season }))}
        />
        {info ? <Pills label="Torneo" items={info.tournaments.map((name) => ({ label: name, href: `/liga/${season}/${name}`, active: name === tournament }))} /> : null}
        {rounds > 0 ? (
          <Pills
            label="Fecha"
            items={Array.from({ length: rounds }, (_, index) => index + 1).map((value) => ({
              label: `F${value}`,
              href: value === rounds ? `/liga/${season}/${tournament}` : `/liga/${season}/${tournament}?fecha=${value}`,
              active: value === standings.round_number,
            }))}
          />
        ) : null}
      </div>

      <StandingsTable rows={standings.rows} season={season} tournament={tournament} />

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
