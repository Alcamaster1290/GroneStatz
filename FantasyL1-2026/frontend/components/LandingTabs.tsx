"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import PremiumBadge from "@/components/PremiumBadge";
import {
  getFixtures,
  getPublicAppConfig,
  getPublicLeaderboard,
  getPublicPremiumConfig,
  getRounds,
  getTeams,
} from "@/lib/api";
import {
  Fixture,
  PremiumBadgeConfig,
  PublicLeaderboardEntry,
  PublicPremiumConfig,
  RoundInfo,
} from "@/lib/types";

type PremiumPlanCode = "PREMIUM_2R" | "PREMIUM_4R" | "PREMIUM_APERTURA";

const NAV_LINKS = [
  { href: "#inicio", label: "Inicio" },
  { href: "#como-jugar", label: "Cómo se juega" },
  { href: "#ranking", label: "Ranking" },
  { href: "#premium", label: "Premium" },
  { href: "#fixtures", label: "Fixtures" },
  { href: "#faq", label: "FAQ" },
];

const isPremiumPlanCode = (plan: string): plan is PremiumPlanCode => plan !== "FREE";

const DEFAULT_PREMIUM_BADGE_CONFIG: PremiumBadgeConfig = {
  enabled: true,
  text: "P",
  color: "#7C3AED",
  shape: "circle",
};

const PREMIUM_PLAN_LABELS: Record<PremiumPlanCode, string> = {
  PREMIUM_2R: "PREMIUM 2 SEMANAS",
  PREMIUM_4R: "PREMIUM 1 MES",
  PREMIUM_APERTURA: "PREMIUM APERTURA",
};

const premiumPlanDurationText = (plan: PremiumPlanCode) => {
  if (plan === "PREMIUM_2R") return "por 2 rondas.";
  if (plan === "PREMIUM_4R") return "por 4 rondas.";
  return "hasta que termine el Apertura 2026.";
};

const formatKickoff = (kickoffAt: string | null) => {
  if (!kickoffAt) return "Horario por confirmar";
  const normalized = kickoffAt.replace("T", " ").trim();
  const [datePart, timePart] = normalized.split(" ");
  if (!datePart) return "Horario por confirmar";
  const [, month, day] = datePart.split("-");
  const dayLabel = Number(day);
  const monthLabel = Number(month);
  const time = timePart ? timePart.slice(0, 5) : "";
  if (!dayLabel || !monthLabel) {
    return time || "Horario por confirmar";
  }
  return `${dayLabel}/${monthLabel}${time ? `, ${time}` : ""}`;
};

function TeamLogo({
  teamId,
  teamName,
}: {
  teamId: number | null | undefined;
  teamName: string;
}) {
  const [hidden, setHidden] = useState(false);
  if (!teamId || hidden) {
    return <div className="h-6 w-6 shrink-0 rounded-full bg-white/10" />;
  }
  return (
    <div className="h-6 w-6 shrink-0 rounded-full bg-white/10 p-1">
      <img
        src={`/images/teams/${teamId}.png`}
        alt={`Escudo de ${teamName}`}
        className="h-full w-full object-contain"
        onError={() => setHidden(true)}
      />
    </div>
  );
}

const toFriendlyError = (value: unknown) => {
  const code = String(value || "").replace(/^Error:\s*/i, "").trim();
  if (!code) return "No se pudo cargar la información.";
  const map: Record<string, string> = {
    db_unavailable: "Base de datos no disponible temporalmente.",
    network_error: "No se pudo conectar con el backend.",
    service_unavailable: "Servicio temporalmente no disponible.",
    endpoint_not_found: "Endpoint no encontrado.",
    server_error: "Error interno del servidor.",
  };
  return map[code] || "No se pudo cargar la información.";
};

export default function LandingTabs() {
  const [leaderboard, setLeaderboard] = useState<PublicLeaderboardEntry[]>([]);
  const [leaderboardError, setLeaderboardError] = useState<string | null>(null);
  const [leaderboardLoading, setLeaderboardLoading] = useState(true);

  const [premiumConfig, setPremiumConfig] = useState<PublicPremiumConfig | null>(null);
  const [premiumError, setPremiumError] = useState<string | null>(null);
  const [premiumBadgeConfig, setPremiumBadgeConfig] = useState<PremiumBadgeConfig>(
    DEFAULT_PREMIUM_BADGE_CONFIG
  );

  const [roundsError, setRoundsError] = useState<string | null>(null);
  const [nextRoundFixtures, setNextRoundFixtures] = useState<Fixture[]>([]);
  const [fixturesError, setFixturesError] = useState<string | null>(null);
  const [featuredRound, setFeaturedRound] = useState<RoundInfo | null>(null);
  const [teamNamesById, setTeamNamesById] = useState<Record<number, string>>({});

  useEffect(() => {
    let active = true;

    const loadLeaderboard = async () => {
      setLeaderboardLoading(true);
      setLeaderboardError(null);
      try {
        const leaderboardData = await getPublicLeaderboard(10, 2026);
        if (!active) return;
        setLeaderboard(leaderboardData.entries);
      } catch (error) {
        if (!active) return;
        setLeaderboard([]);
        setLeaderboardError(toFriendlyError(error));
      } finally {
        if (active) {
          setLeaderboardLoading(false);
        }
      }
    };

    loadLeaderboard().catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    const loadPremium = async () => {
      setPremiumError(null);
      try {
        const [premiumData, appConfigData] = await Promise.all([
          getPublicPremiumConfig(2026),
          getPublicAppConfig().catch(() => null),
        ]);
        if (!active) return;
        setPremiumConfig(premiumData);
        setPremiumBadgeConfig(appConfigData?.premium_badge || DEFAULT_PREMIUM_BADGE_CONFIG);
      } catch (error) {
        if (!active) return;
        setPremiumConfig(null);
        setPremiumBadgeConfig(DEFAULT_PREMIUM_BADGE_CONFIG);
        setPremiumError(toFriendlyError(error));
      }
    };

    loadPremium().catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    const loadRoundsAndFixtures = async () => {
      setRoundsError(null);
      setFixturesError(null);
      try {
        const [roundsData, teamsData] = await Promise.all([getRounds(), getTeams().catch(() => [])]);
        if (!active) return;
        setTeamNamesById(
          Object.fromEntries(
            teamsData.map((team) => [
              team.id,
              team.name_short || team.name_full || `Equipo ${team.id}`,
            ])
          )
        );

        const pendingRounds = [...roundsData]
          .filter((round) => !round.is_closed)
          .sort((a, b) => a.round_number - b.round_number);

        const selectedRound = pendingRounds[0] || null;
        let selectedFixtures: Fixture[] = [];
        if (selectedRound) {
          selectedFixtures = await getFixtures(selectedRound.round_number);
        }

        if (!active) return;
        setFeaturedRound(selectedRound);
        setNextRoundFixtures(selectedFixtures);
      } catch (error) {
        if (!active) return;
        setNextRoundFixtures([]);
        setFeaturedRound(null);
        setRoundsError(toFriendlyError(error));
      }
    };

    loadRoundsAndFixtures().catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const premiumPlans = useMemo(() => {
    if (!premiumConfig) return [];
    return premiumConfig.available_plans.filter((plan) => isPremiumPlanCode(plan));
  }, [premiumConfig]);

  const fixtureBlocks = useMemo(() => {
    const blocks: Fixture[][] = [];
    for (let i = 0; i < nextRoundFixtures.length; i += 10) {
      blocks.push(nextRoundFixtures.slice(i, i + 10));
    }
    return blocks;
  }, [nextRoundFixtures]);

  const getTeamName = (teamId: number | null | undefined) => {
    if (teamId === null || teamId === undefined) {
      return "Equipo por definir";
    }
    return teamNamesById[teamId] || `Equipo ${teamId}`;
  };

  return (
    <div className="relative isolate overflow-hidden pb-12 pt-2 md:pb-16">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-28 -top-20 h-72 w-72 rounded-full bg-[#f2c94c]/12 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 top-44 h-72 w-72 rounded-full bg-[#7C3AED]/15 blur-3xl"
      />

      <header className="sticky top-4 z-40">
        <div className="rounded-2xl border border-white/15 bg-[#130912]/85 px-4 py-3 backdrop-blur-xl shadow-[0_20px_50px_rgba(0,0,0,0.35)]">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-[0.22em] text-zinc-400">Fantasy Liga 1 Peru</p>
            </div>
            <Link
              href="/login?redirect=/app"
              className="shrink-0 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-black transition hover:brightness-110"
            >
              JUEGA YA
            </Link>
          </div>
          <nav className="mt-3 overflow-x-auto scrollbar-hide">
            <div className="flex min-w-max items-center gap-2">
              {NAV_LINKS.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className="rounded-full border border-white/15 px-3 py-1 text-xs text-zinc-200 transition hover:border-white/30 hover:bg-white/5"
                >
                  {item.label}
                </a>
              ))}
            </div>
          </nav>
        </div>
      </header>

      <section id="inicio" className="mt-8 grid gap-4 lg:grid-cols-[1.35fr_0.65fr]">
        <article className="relative overflow-hidden rounded-3xl border border-white/15 bg-[#150a12]/80 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.3)] md:p-8">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-8 -top-8 h-40 w-40 rounded-full bg-[#f2c94c]/12 blur-3xl"
          />
          <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Fantasy Liga 1 Peru 2026</p>
          <h1 className="mt-3 max-w-3xl text-3xl font-semibold leading-tight text-white md:text-5xl">
            Vive la nueva forma de ver la poderosa Liga 1.
          </h1>
          <p className="mt-4 max-w-2xl text-sm text-zinc-300 md:text-base">
            Juego simple, competitivo y real: arma tu plantel, selecciona a tu capitán y compite en
            el ranking general y ligas privadas con datos reales de cada fecha.
          </p>
        </article>

        <aside className="grid gap-3">
          <div className="rounded-3xl border border-white/12 bg-[#120910]/75 p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-zinc-400">Por qué entrar</p>
            <div className="mt-3 space-y-2 text-sm text-zinc-300">
              <p>1. Gana premios por el rendimiento real de tus jugadores en el Ranking General 2026.</p>
              <p>2. Disfruta sin necesidad de apostar, juega solo con tus conocimientos del fútbol peruano.</p>
              <p>3. Compite por el título de Conocedor Supremo del fútbol peruano 2026.</p>
            </div>
            <div className="mt-5 flex justify-center">
              <img
                src="/favicon.png"
                alt="Logo Fantasy Liga 1"
                className="h-20 w-20 rounded-full border border-white/15 bg-black/30 p-2 object-contain"
              />
            </div>
          </div>
        </aside>
      </section>

      <section id="como-jugar" className="mt-10 space-y-4">
        <div className="flex items-end justify-between gap-3">
          <h2 className="text-xl font-semibold text-white">Cómo se juega</h2>
          <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">4 pasos</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4">
            <p className="text-xs text-zinc-500">Paso 1</p>
            <p className="mt-1 text-sm text-zinc-200">Registra tu cuenta y entra al juego.</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4">
            <p className="text-xs text-zinc-500">Paso 2</p>
            <p className="mt-1 text-sm text-zinc-200">Arma tu plantilla de 15 jugadores con presupuesto limitado.</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4">
            <p className="text-xs text-zinc-500">Paso 3</p>
            <p className="mt-1 text-sm text-zinc-200">Define capitán y vicecapitán antes del cierre.</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4">
            <p className="text-xs text-zinc-500">Paso 4</p>
            <p className="mt-1 text-sm text-zinc-200">Suma puntos por jornada y escala en ranking y ligas privadas.</p>
          </div>
        </div>
      </section>

      <section id="ranking" className="mt-10 space-y-3">
        <h2 className="text-xl font-semibold text-white">Ranking Top 10</h2>
        {leaderboardLoading ? (
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4 text-xs text-zinc-400">
            Cargando Top 10...
          </div>
        ) : null}
        {leaderboardError ? (
          <div className="rounded-2xl border border-warning/40 bg-warning/10 p-4 text-xs text-warning">
            {leaderboardError}
          </div>
        ) : null}
        {!leaderboardLoading && !leaderboardError ? (
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-3">
            <div className="mb-2 grid grid-cols-[56px_1fr_auto] gap-2 px-2 text-[11px] uppercase tracking-[0.08em] text-zinc-500">
              <span>Pos</span>
              <span>Equipo</span>
              <span>Puntos</span>
            </div>
            <div className="space-y-2">
              {leaderboard.length === 0 ? (
                <p className="px-2 py-3 text-xs text-zinc-400">Aún no hay equipos registrados.</p>
              ) : (
                leaderboard.map((entry) => (
                  <div
                    key={`top-${entry.rank}-${entry.fantasy_team_id}`}
                    className="grid grid-cols-[56px_1fr_auto] items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-2 py-2 text-xs"
                  >
                    <span className="font-semibold text-zinc-300">#{entry.rank}</span>
                    <span className="truncate font-semibold text-white">{entry.team_name}</span>
                    <span className="font-semibold text-accent">{Math.round(entry.points_total)}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        ) : null}
      </section>

      <section id="premium" className="mt-10 space-y-3">
        <h2 className="text-xl font-semibold text-white">Premium</h2>
        {premiumError ? (
          <div className="rounded-2xl border border-warning/40 bg-warning/10 p-4 text-xs text-warning">
            {premiumError}
          </div>
        ) : null}
        {!premiumError && premiumConfig ? (
          <div className="space-y-3">
            <div className="grid gap-3 md:grid-cols-3">
              {premiumPlans.map((plan) => {
                return (
                  <div
                    key={plan}
                    className="rounded-2xl border border-white/10 bg-[#120910]/75 p-4 shadow-[0_15px_35px_rgba(0,0,0,0.25)]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <PremiumBadge config={premiumBadgeConfig} size="sm" className="mt-0.5" />
                      <span className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] uppercase tracking-wider text-zinc-400">
                        Plan
                      </span>
                    </div>
                    <p className="mt-3 text-sm font-semibold text-white">{PREMIUM_PLAN_LABELS[plan]}</p>
                    <p className="mt-1 text-xs text-zinc-400">Vigencia {premiumPlanDurationText(plan)}</p>
                    <p className="mt-3 text-lg font-semibold text-zinc-200">
                      Próximamente
                    </p>
                    <button
                      type="button"
                      disabled
                      className="mt-4 w-full cursor-not-allowed rounded-xl border border-white/10 bg-black/25 px-3 py-2 text-xs font-semibold text-zinc-400"
                    >
                      Próximamente
                    </button>
                  </div>
                );
              })}
            </div>
            {!premiumConfig.can_buy_apertura ? (
              <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-3 text-xs text-zinc-400">
                PREMIUM APERTURA se cierra después de la ronda {premiumConfig.apertura_last_sell_round}.
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section id="fixtures" className="mt-10 space-y-3">
        <h2 className="text-xl font-semibold text-white">Próximos partidos</h2>
        {roundsError ? (
          <div className="rounded-2xl border border-warning/40 bg-warning/10 p-4 text-xs text-warning">
            {roundsError}
          </div>
        ) : null}
        {!roundsError && !featuredRound ? (
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4 text-xs text-zinc-400">
            Aún no hay ronda pendiente publicada.
          </div>
        ) : null}
        {fixturesError ? (
          <div className="rounded-2xl border border-warning/40 bg-warning/10 p-4 text-xs text-warning">
            {fixturesError}
          </div>
        ) : null}
        {!fixturesError && nextRoundFixtures.length > 0 ? (
          <div className="space-y-3">
            {fixtureBlocks.map((block, blockIndex) => (
              <div
                key={`fixture-block-${blockIndex}`}
                className="grid grid-cols-1 gap-3 md:grid-cols-2"
              >
                {[block.slice(0, 5), block.slice(5, 10)].map((column, columnIndex) => (
                  <div
                    key={`fixture-col-${blockIndex}-${columnIndex}`}
                    className="rounded-2xl border border-white/10 bg-[#120910]/70 p-3"
                  >
                    <div className="space-y-2">
                      {column.map((fixture) => {
                        const homeTeamName = getTeamName(fixture.home_team_id);
                        const awayTeamName = getTeamName(fixture.away_team_id);
                        return (
                          <div
                            key={fixture.id}
                            className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-zinc-400"
                          >
                            <div className="flex items-center gap-2 text-sm font-semibold text-white">
                              <div className="flex min-w-0 items-center gap-2">
                                <TeamLogo teamId={fixture.home_team_id} teamName={homeTeamName} />
                                <span className="truncate">{homeTeamName}</span>
                              </div>
                              <span className="text-zinc-500">vs</span>
                              <div className="flex min-w-0 items-center gap-2">
                                <TeamLogo teamId={fixture.away_team_id} teamName={awayTeamName} />
                                <span className="truncate">{awayTeamName}</span>
                              </div>
                            </div>
                            <p className="mt-1">Ronda {fixture.round_number}</p>
                            <p>{formatKickoff(fixture.kickoff_at)}</p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : null}
        {!fixturesError && featuredRound && nextRoundFixtures.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4 text-xs text-zinc-400">
            Aún no hay partidos cargados para la ronda pendiente actual.
          </div>
        ) : null}
      </section>
      <section id="faq" className="mt-10 space-y-3">
        <h2 className="text-xl font-semibold text-white">FAQ</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4 text-sm text-zinc-300">
            <p className="font-semibold text-white">¿Es gratis jugar?</p>
            <p className="mt-2">
              Sí. Solo registra un correo y contraseña y podrás competir en el ranking general y ligas privadas con tus amigos.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4 text-sm text-zinc-300">
            <p className="font-semibold text-white">¿Cómo funciona el Mercado de jugadores?</p>
            <p className="mt-2">
              En Mercado eliges y compras tus 15 jugadores para la temporada, respetando el presupuesto inicial de 100 M y las reglas de composición del plantel.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4 text-sm text-zinc-300">
            <p className="font-semibold text-white">¿Cómo obtienen puntos los jugadores?</p>
            <p className="mt-2">
              El catálogo base se construyó con datos históricos de la temporada 2025 como goles, asistencias y minutos jugados. En 2026 se toman en cuenta datos reales por fecha y con eso se calculan los puntos de cada jugador (+4 por gol, +3 asistencia, +1/+2 por minutos jugados, +3 valla invicta para G/D/M, -3 amarilla, -5 roja). Con esos puntos también cambia su valor en el Mercado: cada jugador agrega +0.1 a su valor cada 3 puntos positivos y disminuye desde -0.2 con -0.1 adicional cada 2 puntos negativos.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4 text-sm text-zinc-300">
            <p className="font-semibold text-white">¿Cómo creo mi equipo?</p>
            <p className="mt-2">
              Primero completas tu Mercado con 15 jugadores. Luego, en tu equipo, eliges a los 11 titulares, defines capitán y vicecapitán, y dejas 4 suplentes para cerrar tu alineación de la fecha.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-[#120910]/70 p-4 text-sm text-zinc-300 md:col-span-2">
            <p className="font-semibold text-white">¿Cómo activo el Plan Premium?</p>
            <p className="mt-2">
              Próximamente habilitaremos la opción de pagar un plan Premium a cambio de la posibilidad de ganar premios en efectivo semana a semana en un Ranking Premium exclusivo.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

