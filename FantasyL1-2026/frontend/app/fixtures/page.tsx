"use client";

import { useEffect, useMemo, useState } from "react";

import FavoriteTeamGate from "@/components/FavoriteTeamGate";
import PublicPageNav from "@/components/PublicPageNav";
import TeamNameGate from "@/components/TeamNameGate";
import WelcomeSlideshow from "@/components/WelcomeSlideshow";
import {
  createTeam,
  getFixtures,
  getMatchStats,
  getRounds,
  getTeam,
  getTeams,
  updateFavoriteTeam
} from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import { Fixture, MatchPlayerStat, RoundInfo } from "@/lib/types";

function TeamLogo({ teamId }: { teamId: number | null | undefined }) {
  const [hidden, setHidden] = useState(false);
  if (!teamId || hidden) {
    return <div className="h-6 w-6 rounded-full bg-surface2/60" />;
  }
  return (
    <div className="h-6 w-6 rounded-full bg-surface2/60 p-1">
      <img
        src={`/images/teams/${teamId}.png`}
        alt=""
        className="h-full w-full object-contain"
        onError={() => setHidden(true)}
      />
    </div>
  );
}

function formatKickoff(raw: string | null | undefined): string {
  if (!raw) return "TBD";
  const value = String(raw).trim();
  if (!value) return "TBD";
  const parts = value.split("T");
  const timePart = (parts.length > 1 ? parts[1] : value).split(" ")[0];
  if (timePart.length >= 5) {
    return timePart.slice(0, 5);
  }
  return timePart || "TBD";
}

function formatDateLabel(dateKey: string): string {
  if (!dateKey || dateKey === "TBD") return "Por confirmar";
  const [year, month, day] = dateKey.split("-").map((part) => Number(part));
  if (!year || !month || !day) return dateKey;
  const date = new Date(year, month - 1, day);
  const weekdays = [
    "Domingo",
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado"
  ];
  const months = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre"
  ];
  const weekday = weekdays[date.getDay()];
  const monthLabel = months[month - 1];
  if (!weekday || !monthLabel) return dateKey;
  return `${weekday} ${day} de ${monthLabel}`;
}

const positionLabels: Record<string, string> = {
  G: "Arquero",
  D: "Defensa",
  M: "Mediocampo",
  F: "Delantero"
};

export default function FixturesPage() {
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);
  const userEmail = useFantasyStore((state) => state.userEmail);

  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>([]);
  const [selectedRound, setSelectedRound] = useState<number | null>(null);
  const [roundsInfo, setRoundsInfo] = useState<RoundInfo[]>([]);
  const [roundStatus, setRoundStatus] = useState<string | null>(null);
  const [matchStatsOpen, setMatchStatsOpen] = useState(false);
  const [matchStatsLoading, setMatchStatsLoading] = useState(false);
  const [matchStatsError, setMatchStatsError] = useState<string | null>(null);
  const [matchStats, setMatchStats] = useState<MatchPlayerStat[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<Fixture | null>(null);
  const [teamName, setTeamName] = useState("");
  const [favoriteTeamId, setFavoriteTeamId] = useState<number | null>(null);
  const [needsTeamName, setNeedsTeamName] = useState(false);
  const [needsFavoriteTeam, setNeedsFavoriteTeam] = useState(false);
  const [teamLoaded, setTeamLoaded] = useState(false);
  const [isNewTeam, setIsNewTeam] = useState(false);
  const [nameGateOpen, setNameGateOpen] = useState(false);
  const [favoriteGateOpen, setFavoriteGateOpen] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [welcomeSeen, setWelcomeSeen] = useState(false);
  const [teamNameError, setTeamNameError] = useState<string | null>(null);
  const [favoriteError, setFavoriteError] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("fantasy_token");
    const storedEmail = localStorage.getItem("fantasy_email");
    if (!token && stored) {
      setToken(stored);
    }
    if (!userEmail && storedEmail) {
      setUserEmail(storedEmail);
    }
  }, [token, setToken, userEmail, setUserEmail]);

  useEffect(() => {
    if (!token) return;
    const deferredKey = `fantasy_favorite_deferred_${userEmail && userEmail.trim() ? userEmail.trim() : "anon"}`;
    getTeam(token)
      .then((team) => {
        setTeamName(team.name || "");
        const hasName = Boolean(team.name?.trim());
        const favoriteId =
          typeof team.favorite_team_id === "number" ? team.favorite_team_id : null;
        setFavoriteTeamId(favoriteId);
        const hasFavorite = Boolean(favoriteId);
        const deferredFavorite = localStorage.getItem(deferredKey) === "1";
        if (hasFavorite) {
          localStorage.removeItem(deferredKey);
        }
        setNeedsTeamName(!hasName);
        setNeedsFavoriteTeam(!hasFavorite && !deferredFavorite);
        setIsNewTeam(!hasName);
        setTeamLoaded(true);
      })
      .catch(() => {
        setNeedsTeamName(false);
        setNeedsFavoriteTeam(false);
        setIsNewTeam(false);
        setTeamLoaded(true);
      });
  }, [token, userEmail]);

  useEffect(() => {
    if (!teamLoaded) {
      setNameGateOpen(false);
      setFavoriteGateOpen(false);
      return;
    }
    if (needsFavoriteTeam) {
      setFavoriteGateOpen(true);
      setNameGateOpen(false);
      return;
    }
    const shouldShowWelcome = isNewTeam && needsTeamName && !welcomeSeen;
    if (shouldShowWelcome) {
      setNameGateOpen(false);
      setFavoriteGateOpen(false);
      return;
    }
    if (needsTeamName && welcomeSeen) {
      setNameGateOpen(true);
      setFavoriteGateOpen(false);
      return;
    }
    setNameGateOpen(false);
    setFavoriteGateOpen(false);
  }, [teamLoaded, isNewTeam, needsTeamName, needsFavoriteTeam, welcomeSeen]);

  const welcomeKey = useMemo(() => {
    const safeEmail = userEmail && userEmail.trim() ? userEmail.trim() : "anon";
    return `fantasy_welcome_seen_${safeEmail}`;
  }, [userEmail]);
  const favoriteDeferredKey = useMemo(() => {
    const safeEmail = userEmail && userEmail.trim() ? userEmail.trim() : "anon";
    return `fantasy_favorite_deferred_${safeEmail}`;
  }, [userEmail]);

  useEffect(() => {
    if (!token) return;
    const stored = localStorage.getItem(welcomeKey);
    setWelcomeSeen(stored === "1");
  }, [token, welcomeKey]);

  useEffect(() => {
    if (needsFavoriteTeam) {
      setWelcomeOpen(false);
      return;
    }
    if (isNewTeam && teamLoaded && needsTeamName && !welcomeSeen) {
      setWelcomeOpen(true);
    } else {
      setWelcomeOpen(false);
    }
  }, [teamLoaded, isNewTeam, needsTeamName, needsFavoriteTeam, welcomeSeen]);

  useEffect(() => {
    getFixtures().then(setFixtures).catch(() => undefined);
    getTeams().then(setTeams).catch(() => undefined);
    getRounds().then(setRoundsInfo).catch(() => setRoundsInfo([]));
  }, []);

  const roundNumbers = useMemo(() => {
    const unique = new Set(fixtures.map((fixture) => fixture.round_number));
    return Array.from(unique.values()).sort((a, b) => a - b);
  }, [fixtures]);

  useEffect(() => {
    if (!roundNumbers.length) {
      setSelectedRound(null);
      return;
    }
    if (selectedRound && roundNumbers.includes(selectedRound)) return;
    setSelectedRound(roundNumbers[0]);
  }, [roundNumbers, selectedRound]);

  useEffect(() => {
    if (!selectedRound) {
      setRoundStatus(null);
      return;
    }
    const info = roundsInfo.find((round) => round.round_number === selectedRound);
    if (info) {
      setRoundStatus(
        info.status ? info.status : info.is_closed ? "Cerrada" : "Pendiente"
      );
    } else {
      setRoundStatus(null);
    }
  }, [roundsInfo, selectedRound]);

  const teamMap = useMemo(() => {
    return new Map(
      teams.map((team) => [team.id, team.name_short || team.name_full || `Team ${team.id}`])
    );
  }, [teams]);

  const roundFixtures = useMemo(() => {
    if (selectedRound === null) return [];
    return fixtures.filter((fixture) => fixture.round_number === selectedRound);
  }, [fixtures, selectedRound]);

  const canShowMatchStats = (fixture: Fixture) => {
    return fixture.status === "Finalizado";
  };

  const handleMatchClick = async (fixture: Fixture) => {
    if (!canShowMatchStats(fixture)) return;
    setSelectedMatch(fixture);
    setMatchStatsOpen(true);
    setMatchStatsLoading(true);
    setMatchStatsError(null);
    try {
      const data = await getMatchStats(fixture.match_id);
      const sorted = data.slice().sort((a, b) => (b.points || 0) - (a.points || 0));
      setMatchStats(sorted);
    } catch (err) {
      setMatchStats([]);
      setMatchStatsError(String(err));
    } finally {
      setMatchStatsLoading(false);
    }
  };

  const roundsByDate = useMemo(() => {
    const toKey = (value: string | null | undefined) => {
      if (!value) return "TBD";
      const raw = String(value).trim();
      if (!raw) return "TBD";
      return raw.split("T")[0].split(" ")[0] || "TBD";
    };
    return roundFixtures.reduce((acc, fixture) => {
      const key = toKey(fixture.kickoff_at);
      if (!acc[key]) acc[key] = [];
      acc[key].push(fixture);
      return acc;
    }, {} as Record<string, Fixture[]>);
  }, [roundFixtures]);

  const sortedMatchStats = useMemo(() => {
    return [...matchStats].sort((a, b) => (b.points || 0) - (a.points || 0));
  }, [matchStats]);

  const roundIndex = selectedRound ? roundNumbers.indexOf(selectedRound) : -1;
  const canPrevRound = roundIndex > 0;
  const canNextRound = roundIndex >= 0 && roundIndex < roundNumbers.length - 1;

  return (
    <div className="space-y-5">
      <PublicPageNav />

      <div>
        <h1 className="text-xl font-semibold">Partidos</h1>
        <p className="text-sm text-muted">Calendario por rondas</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs">
          <button
            type="button"
            onClick={() => {
              if (canPrevRound && roundIndex > 0) {
                setSelectedRound(roundNumbers[roundIndex - 1]);
              }
            }}
            disabled={!canPrevRound}
            className="rounded-lg border border-white/10 px-2 py-1 text-ink disabled:opacity-40"
          >
            {"<"}
          </button>
          <span className="text-muted">Ronda {selectedRound ?? "-"}</span>
          {roundStatus ? (
            <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-muted">
              {roundStatus}
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => {
              if (canNextRound && roundIndex >= 0) {
                setSelectedRound(roundNumbers[roundIndex + 1]);
              }
            }}
            disabled={!canNextRound}
            className="rounded-lg border border-white/10 px-2 py-1 text-ink disabled:opacity-40"
          >
            {">"}
          </button>
        </div>
      </div>

      {selectedRound === null ? (
        <div className="glass rounded-2xl border border-white/10 p-4 text-sm text-muted">
          Sin partidos registrados.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">Ronda {selectedRound}</h2>
            {roundStatus ? (
              <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-muted">
                {roundStatus}
              </span>
            ) : null}
          </div>
          {Object.entries(roundsByDate)
            .sort(([a], [b]) => {
              if (a === "TBD") return 1;
              if (b === "TBD") return -1;
              return a.localeCompare(b);
            })
            .map(([dateKey, matches]) => (
              <div key={dateKey} className="space-y-2">
                <h3 className="text-base font-semibold">{formatDateLabel(dateKey)}</h3>
                {matches
                  .slice()
                  .sort((a, b) =>
                    formatKickoff(a.kickoff_at).localeCompare(formatKickoff(b.kickoff_at))
                  )
                  .map((match) => (
                    <button
                      key={match.id}
                      type="button"
                      onClick={() => handleMatchClick(match)}
                      disabled={!canShowMatchStats(match)}
                      className={
                        "glass flex w-full items-center justify-between rounded-2xl p-4 text-left transition " +
                        (canShowMatchStats(match)
                          ? "hover:border-white/20"
                          : "opacity-80")
                      }
                    >
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2 text-sm text-ink">
                          <TeamLogo teamId={match.home_team_id} />
                          <span>{teamMap.get(match.home_team_id ?? 0) || "Home"}</span>
                          <span className="text-xs text-muted">vs</span>
                          <TeamLogo teamId={match.away_team_id} />
                          <span>{teamMap.get(match.away_team_id ?? 0) || "Away"}</span>
                        </div>
                        <p className="text-xs text-muted">
                          {formatKickoff(match.kickoff_at)} - {match.status}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold text-ink">
                          {match.home_score != null && match.away_score != null
                            ? `${match.home_score} - ${match.away_score}`
                            : ""}
                        </p>
                        {canShowMatchStats(match) ? (
                          <p className="text-[10px] text-muted">Ver puntos</p>
                        ) : null}
                      </div>
                    </button>
                  ))}
              </div>
            ))}
        </div>
      )}

      {matchStatsOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6">
          <div className="glass max-h-[85vh] w-full max-w-2xl space-y-4 overflow-y-auto rounded-2xl p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-ink">Stats del partido</h3>
                <p className="text-xs text-muted">
                  {selectedMatch
                    ? `${teamMap.get(selectedMatch.home_team_id ?? 0) || "Home"} vs ${
                        teamMap.get(selectedMatch.away_team_id ?? 0) || "Away"
                      }`
                    : ""}
                </p>
              </div>
              <button
                onClick={() => setMatchStatsOpen(false)}
                className="rounded-full border border-white/10 px-3 py-1 text-xs text-ink"
              >
                Cerrar
              </button>
            </div>
            {matchStatsLoading ? (
              <p className="text-xs text-muted">Cargando puntos...</p>
            ) : null}
            {matchStatsError ? (
              <p className="text-xs text-warning">{matchStatsError}</p>
            ) : null}
            {!matchStatsLoading && !matchStatsError ? (
              sortedMatchStats.length ? (
                <div className="space-y-2">
                  {sortedMatchStats.map((row) => {
                    const pointsLabel = Math.trunc(row.points);
                    const statLine = [
                      `Min ${row.minutesplayed}`,
                      `G ${row.goals}`,
                      `A ${row.assists}`
                    ];
                    if (row.position === "G") {
                      statLine.push(`Atj ${row.saves}`);
                      statLine.push(`GC ${row.goals_conceded ?? 0}`);
                    } else if (row.position === "D") {
                      statLine.push(`GC ${row.goals_conceded ?? 0}`);
                    }
                    statLine.push(`TA ${row.yellow_cards}`, `TR ${row.red_cards}`);
                    if (row.clean_sheet != null) {
                      statLine.push(`CS ${row.clean_sheet}`);
                    }
                    return (
                      <div
                        key={`${row.match_id}-${row.player_id}`}
                        className="flex items-center justify-between rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <div className="relative h-9 w-9 overflow-hidden rounded-full bg-surface2/60 ring-1 ring-white/10">
                            <img
                              src={`/images/players/${row.player_id}.png`}
                              alt=""
                              className="h-full w-full object-cover"
                              onError={(event) => {
                                (event.currentTarget as HTMLImageElement).style.display = "none";
                              }}
                            />
                            <span className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-black/70">
                              <img
                                src={`/images/teams/${row.team_id}.png`}
                                alt=""
                                className="h-full w-full object-contain"
                              />
                            </span>
                          </div>
                          <div>
                            <p className="text-xs font-semibold text-ink">
                              {row.short_name || row.name}
                            </p>
                            <p className="text-[10px] text-muted">
                              {positionLabels[row.position] || row.position}
                            </p>
                            <p className="text-[10px] text-muted">{statLine.join(" · ")}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-[10px] text-muted">Puntos</p>
                          <p className="text-sm font-semibold text-ink">{pointsLabel}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-muted">Sin puntos registrados para este partido.</p>
              )
            ) : null}
          </div>
        </div>
      ) : null}

      <WelcomeSlideshow
        open={welcomeOpen}
        onComplete={() => {
          try {
            localStorage.setItem(welcomeKey, "1");
          } catch {
            // ignore storage quota errors
          }
          setWelcomeSeen(true);
          setWelcomeOpen(false);
          if (needsTeamName) {
            setNameGateOpen(true);
          }
        }}
      />

      <FavoriteTeamGate
        open={favoriteGateOpen}
        selectedTeamId={favoriteTeamId}
        onSelect={(teamId) => setFavoriteTeamId(teamId)}
        error={favoriteError}
        onClose={() => {
          if (!needsFavoriteTeam) {
            setFavoriteGateOpen(false);
          }
        }}
        onSkip={() => {
          try {
            localStorage.setItem(favoriteDeferredKey, "1");
          } catch {
            // ignore storage quota errors
          }
          setFavoriteTeamId(null);
          setNeedsFavoriteTeam(false);
          setFavoriteGateOpen(false);
        }}
        onSave={async () => {
          if (!token || !favoriteTeamId) return;
          setFavoriteError(null);
          try {
            await updateFavoriteTeam(token, favoriteTeamId);
            try {
              localStorage.removeItem(favoriteDeferredKey);
            } catch {
              // ignore storage quota errors
            }
            setNeedsFavoriteTeam(false);
            setFavoriteGateOpen(false);
          } catch {
            setFavoriteError("No se pudo guardar el equipo favorito.");
          }
        }}
      />

      <TeamNameGate
        open={nameGateOpen}
        teamName={teamName}
        onTeamNameChange={setTeamName}
        error={teamNameError}
        onClose={() => setNameGateOpen(false)}
        onSave={async () => {
          if (!token) return;
          const trimmedName = teamName.trim();
          if (!trimmedName) {
            setTeamNameError("Nombre requerido.");
            return;
          }
          setTeamNameError(null);
          try {
            await createTeam(token, trimmedName);
            setTeamName(trimmedName);
            setNeedsTeamName(false);
            setIsNewTeam(false);
            setNameGateOpen(false);
          } catch {
            setTeamNameError("No se pudo guardar el nombre.");
          }
        }}
      />
    </div>
  );
}
