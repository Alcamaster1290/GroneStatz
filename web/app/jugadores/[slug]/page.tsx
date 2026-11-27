import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Crest from "@/components/Crest";
import Heatmap from "@/components/Heatmap";
import Pills from "@/components/Pills";
import PlayerPhoto from "@/components/PlayerPhoto";
import ShotMap from "@/components/ShotMap";
import StatCard from "@/components/StatCard";
import { getJson } from "@/lib/api";
import { formatDate, idFromSlug, number, slug } from "@/lib/format";
import { POSITION_LABEL } from "@/lib/labels";
import type { Heatmap as HeatmapData, PlayerProfile, PlayerShots } from "@/lib/types";

type Props = { params: { slug: string }; searchParams: { season?: string } };

const SMALL_SAMPLE = 6; // partidos: con menos, la cifra se atenúa y se muestra su n

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const id = idFromSlug(params.slug);
  if (id === null) return { title: "Jugador" };
  const profile = await getJson<PlayerProfile>(`/v1/players/${id}${searchParams.season ? `?season=${searchParams.season}` : ""}`);
  return { title: profile.player.name };
}

export default async function PlayerPage({ params, searchParams }: Props) {
  const id = idFromSlug(params.slug);
  if (id === null) notFound();
  const profile = await getJson<PlayerProfile>(`/v1/players/${id}${searchParams.season ? `?season=${searchParams.season}` : ""}`);
  const { player, seasons } = profile;
  const selected = profile.selected_season;
  const stats = profile.season_stats;
  const [shots, heat] =
    selected !== null
      ? await Promise.all([getJson<PlayerShots>(`/v1/players/${id}/shots?season=${selected}`), getJson<HeatmapData>(`/v1/players/${id}/heatmap?season=${selected}`)])
      : [null, null];
  const color = stats?.team?.color ?? player.team?.color ?? null;
  const dim = stats !== null && stats.matches < SMALL_SAMPLE;
  const per90 = (value: number | null | undefined) => (stats && stats.minutes && value !== null && value !== undefined ? number((value / stats.minutes) * 90, 2) : "—");
  const playerHref = `/jugadores/${params.slug}`;

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-center gap-5">
        <PlayerPhoto name={player.name} photo={player.photo} color={color} size={96} />
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight">{player.name}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
            <span>{player.position ? (POSITION_LABEL[player.position] ?? player.position) : "Posición sin dato"}</span>
            {player.team ? (
              <>
                <span aria-hidden>·</span>
                <Link href={`/equipos/${slug(player.team.team_id, player.team.name)}${selected ? `?season=${selected}` : ""}`} className="flex items-center gap-1.5 hover:underline">
                  <Crest team={player.team} size={18} />
                  {player.team.name}
                </Link>
              </>
            ) : null}
          </p>
        </div>
      </header>

      {seasons.length > 0 ? (
        <div className="mb-6">
          <Pills label="Temporada" items={seasons.map((item) => ({ label: String(item.season), href: `${playerHref}?season=${item.season}`, active: item.season === selected }))} />
        </div>
      ) : null}

      {stats === null ? (
        <p className="rounded-lg border border-dashed border-line p-6 text-muted">Sin datos de {player.name} en {searchParams.season ?? "ninguna temporada"}. Elige otra temporada.</p>
      ) : (
        <>
          <section aria-label="Resumen de la temporada" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Partidos" value={String(stats.matches)} hint={`n=${stats.matches}${dim ? " · muestra chica" : ""}`} dim={dim} />
            <StatCard label="Minutos" value={number(stats.minutes)} />
            <StatCard label="Goles" value={number(stats.goals)} hint={`${per90(stats.goals)} cada 90`} dim={dim} />
            <StatCard label="Asistencias" value={number(stats.assists)} hint={`${per90(stats.assists)} cada 90`} dim={dim} />
            <StatCard label="xG" value={number(stats.xg, 2)} hint={`${stats.shots} tiros · ${per90(stats.xg)} cada 90`} dim={dim} />
            <StatCard label="Goles − xG" value={`${stats.goals_minus_xg > 0 ? "+" : ""}${number(stats.goals_minus_xg, 2)}`} hint="rinde sobre lo esperado si es positivo" dim={dim} />
            <StatCard label="Rating" value={number(stats.rating, 2)} hint="promedio de SofaScore" dim={dim} />
            <StatCard label="Tarjetas" value="sin dato" hint="no vienen por jugador; las del equipo están en su página" />
          </section>

          <section className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-2">
            <div>
              <h2 className="mb-3 text-lg font-semibold">Mapa de tiros {selected}</h2>
              {shots && shots.shots.length > 0 ? (
                <ShotMap
                  caption={`Tiros de ${player.name} en ${selected}`}
                  shots={shots.shots.map((shot) => ({ x: shot.x, y: shot.y, xg: shot.xg, is_goal: shot.is_goal, minute: shot.minute, label: shot.rival ? `vs ${shot.rival}${shot.date ? ` (${formatDate(shot.date)})` : ""}` : null }))}
                />
              ) : (
                <p className="text-muted">Sin tiros registrados en esta temporada ({shots?.missing_reason ?? "sin dato"}).</p>
              )}
            </div>
            <div>
              <h2 className="mb-3 text-lg font-semibold">Dónde jugó {selected}</h2>
              {heat && heat.total > 0 ? (
                <Heatmap cells={heat.cells} cols={heat.cols} rows={heat.rows} total={heat.total} matches={heat.matches} caption={`Heatmap de ${player.name} en ${selected}`} />
              ) : (
                <p className="text-muted">Sin heatmap en esta temporada: SofaScore no lo trae para sus partidos.</p>
              )}
            </div>
          </section>
        </>
      )}

      {seasons.length > 0 ? (
        <section className="mt-10">
          <h2 className="mb-3 text-lg font-semibold">Por temporada</h2>
          <div className="overflow-x-auto rounded-lg border border-line bg-surface">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <caption className="sr-only">Estadísticas de {player.name} por temporada</caption>
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                  <th scope="col" className="px-3 py-2">
                    Temporada
                  </th>
                  <th scope="col" className="px-2 py-2">
                    Equipo
                  </th>
                  {["PJ", "Min", "G", "A", "xG", "G − xG", "Rating"].map((heading) => (
                    <th key={heading} scope="col" className="px-2 py-2 text-right">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {seasons.map((item) => (
                  <tr key={item.season} className={`border-b border-line last:border-0 ${item.season === selected ? "bg-accent/10" : ""}`}>
                    <td className="num px-3 py-2 font-medium">
                      <Link href={`${playerHref}?season=${item.season}`} className="hover:underline">
                        {item.season}
                      </Link>
                    </td>
                    <td className="px-2 py-2">{item.team?.name ?? "—"}</td>
                    <td className="num px-2 py-2 text-right">{item.matches}</td>
                    <td className="num px-2 py-2 text-right">{number(item.minutes)}</td>
                    <td className="num px-2 py-2 text-right">{number(item.goals)}</td>
                    <td className="num px-2 py-2 text-right">{number(item.assists)}</td>
                    <td className="num px-2 py-2 text-right">{number(item.xg, 2)}</td>
                    <td className="num px-2 py-2 text-right">{`${item.goals_minus_xg > 0 ? "+" : ""}${number(item.goals_minus_xg, 2)}`}</td>
                    <td className="num px-2 py-2 text-right">{number(item.rating, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="mt-10" aria-label="Próximamente">
        <h2 className="mb-3 text-lg font-semibold">Próximamente</h2>
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Percentiles por rol", "Cómo se compara con los de su misma posición."],
            ["Jugadores parecidos", "Similitud de perfil dentro y fuera de su club."],
            ["Compañeros", "Con quién rinde mejor: xGD o diferencia de goles."],
            ["Pases y zonas", "Inicio y fin de pases, take-ons y zonas defensivas."],
          ].map(([title, text]) => (
            <li key={title} className="rounded-lg border border-dashed border-line p-4 text-sm">
              <p className="font-semibold">{title}</p>
              <p className="mt-1 text-muted">{text}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
