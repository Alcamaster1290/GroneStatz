"use client";

import { useEffect, useMemo, useState } from "react";

import AuthPanel from "@/components/AuthPanel";
import FavoriteTeamGate from "@/components/FavoriteTeamGate";
import TeamNameGate from "@/components/TeamNameGate";
import WelcomeSlideshow from "@/components/WelcomeSlideshow";
import {
  createLeague,
  createTeam,
  getMyLeague,
  getRankingGeneral,
  getRankingLeague,
  getRankingLineup,
  getTeam,
  getTeams,
  joinLeague,
  leaveLeague,
  removeLeagueMember,
  updateFavoriteTeam
} from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import { League, PublicLineup, PublicLineupSlot, RankingResponse } from "@/lib/types";

const positionLabels: Record<string, string> = {
  G: "Arquero",
  D: "Defensa",
  M: "Mediocampo",
  F: "Delantero"
};

function RankingTable({
  title,
  data,
  onSelectTeam
}: {
  title: string;
  data: RankingResponse | null;
  onSelectTeam?: (fantasyTeamId: number, teamName: string) => void;
}) {
  const renderSparkline = (values: number[]) => {
    if (!values.length) return null;
    const width = 64;
    const height = 20;
    const min = Math.min(...values, 0);
    const max = Math.max(...values, 0);
    const range = max - min || 1;
    const points = values
      .map((value, index) => {
        const x = (index / Math.max(values.length - 1, 1)) * width;
        const y = height - ((value - min) / range) * height;
        return `${x},${y}`;
      })
      .join(" ");
    const trend = values[values.length - 1] - values[0];
    const stroke = trend >= 0 ? "#34d399" : "#f87171";
    return (
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <polyline
          fill="none"
          stroke={stroke}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
      </svg>
    );
  };
  if (!data || data.entries.length === 0) {
    return (
      <div className="glass rounded-2xl p-4 text-xs text-muted">
        {title}: Sin equipos registrados.
      </div>
    );
  }

  return (
    <div className="glass space-y-3 rounded-2xl p-4">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <div className="space-y-3">
        {data.entries.map((entry, index) => (
          <div
            key={entry.fantasy_team_id}
            className="flex flex-col gap-2 rounded-2xl border border-white/10 px-3 py-2"
          >
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted">#{index + 1}</span>
                {entry.captain_player_id ? (
                  <span className="relative flex h-6 w-6 items-center justify-center rounded-full bg-surface2/60">
                    <img
                      src={`/images/players/${entry.captain_player_id}.png`}
                      alt=""
                      className="h-full w-full rounded-full object-cover"
                      onError={(event) => {
                        (event.currentTarget as HTMLImageElement).style.display = "none";
                      }}
                    />
                    <span className="absolute -bottom-1 -right-1 flex h-3 w-3 items-center justify-center rounded-full bg-yellow-300 text-[8px] font-bold text-black">
                      C
                    </span>
                  </span>
                ) : null}
                <img
                  src={
                    entry.favorite_team_id
                      ? `/images/teams/${entry.favorite_team_id}.png`
                      : "/favicon.png"
                  }
                  alt=""
                  className="h-6 w-6 object-contain"
                  onError={(event) => {
                    const img = event.currentTarget as HTMLImageElement;
                    if (img.src.includes("/favicon.png")) {
                      img.style.display = "none";
                    } else {
                      img.src = "/favicon.png";
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={() => onSelectTeam?.(entry.fantasy_team_id, entry.team_name)}
                  className="text-left font-semibold text-ink transition hover:text-accent"
                >
                  {entry.team_name}
                </button>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 text-xs text-muted">
                  {renderSparkline(entry.rounds.map((round) => round.price_delta || 0))}
                  <span>
                    Δ{" "}
                    {entry.rounds.length
                      ? entry.rounds[entry.rounds.length - 1].price_delta?.toFixed(1) ?? "0.0"
                      : "0.0"}
                  </span>
                </div>
                <span className="text-sm font-semibold text-accent">
                  {entry.total_points.toFixed(1)}
                </span>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 text-[10px] text-muted">
              {entry.rounds.length === 0 ? (
                <span className="rounded-full border border-white/10 px-2 py-1">
                  Sin rondas
                </span>
              ) : (
                entry.rounds.map((round) => (
                  <span
                    key={`${entry.fantasy_team_id}-${round.round_number}`}
                    className="rounded-full border border-white/10 px-2 py-1"
                  >
                    R{round.round_number}: {round.cumulative.toFixed(1)}{" "}
                    <span
                      className={
                        (round.price_delta || 0) >= 0
                          ? "text-emerald-300"
                          : "text-red-300"
                      }
                    >
                      {(round.price_delta || 0) >= 0 ? "▲" : "▼"}{" "}
                      {Math.abs(round.price_delta || 0).toFixed(1)}
                    </span>
                  </span>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function RankingPage() {
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);
  const userEmail = useFantasyStore((state) => state.userEmail);

  const [teamName, setTeamName] = useState("");
  const [needsTeamName, setNeedsTeamName] = useState(false);
  const [teamId, setTeamId] = useState<number | null>(null);
  const [favoriteTeamId, setFavoriteTeamId] = useState<number | null>(null);
  const [favoriteGateOpen, setFavoriteGateOpen] = useState(false);
  const [needsFavoriteTeam, setNeedsFavoriteTeam] = useState(false);
  const [favoriteError, setFavoriteError] = useState<string | null>(null);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>([]);
  const [teamLoaded, setTeamLoaded] = useState(false);
  const [nameGateOpen, setNameGateOpen] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [welcomeSeen, setWelcomeSeen] = useState(false);
  const [teamNameError, setTeamNameError] = useState<string | null>(null);

  const [league, setLeague] = useState<League | null>(null);
  const [leagueError, setLeagueError] = useState<string | null>(null);
  const [leagueLoading, setLeagueLoading] = useState(false);

  const [leagueRanking, setLeagueRanking] = useState<RankingResponse | null>(null);
  const [generalRanking, setGeneralRanking] = useState<RankingResponse | null>(null);
  const [rankingError, setRankingError] = useState<string | null>(null);

  const [createName, setCreateName] = useState("");
  const [joinCode, setJoinCode] = useState("");

  const [lineupOpen, setLineupOpen] = useState(false);
  const [lineupLoading, setLineupLoading] = useState(false);
  const [lineupError, setLineupError] = useState<string | null>(null);
  const [lineupData, setLineupData] = useState<PublicLineup | null>(null);
  const [lineupTeamName, setLineupTeamName] = useState("");

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
    getTeam(token)
      .then((team) => {
        setTeamName(team.name || "");
        setTeamId(team.id ?? null);
        setFavoriteTeamId(team.favorite_team_id ?? null);
        setNeedsFavoriteTeam(!team.favorite_team_id);
        setNeedsTeamName(!team.name?.trim());
        setTeamLoaded(true);
      })
      .catch(() => {
        setNeedsTeamName(true);
        setNeedsFavoriteTeam(true);
        setTeamLoaded(true);
      });
  }, [token]);

  useEffect(() => {
    if (!teamLoaded) {
      setFavoriteGateOpen(false);
      setNameGateOpen(false);
      return;
    }
    if (!welcomeSeen && (needsTeamName || needsFavoriteTeam)) {
      if (needsFavoriteTeam) {
        setFavoriteGateOpen(!welcomeOpen);
        setNameGateOpen(false);
      } else {
        setNameGateOpen(!welcomeOpen);
        setFavoriteGateOpen(false);
      }
      return;
    }
    setFavoriteGateOpen(false);
    if (needsTeamName) {
      setNameGateOpen(true);
    } else {
      setNameGateOpen(false);
    }
  }, [teamLoaded, needsTeamName, needsFavoriteTeam, welcomeOpen, welcomeSeen]);

  const welcomeKey = useMemo(() => {
    const safeEmail = userEmail && userEmail.trim() ? userEmail.trim() : "anon";
    return `fantasy_welcome_seen_${safeEmail}`;
  }, [userEmail]);

  useEffect(() => {
    if (!token) return;
    const stored = localStorage.getItem(welcomeKey);
    setWelcomeSeen(stored === "1");
  }, [token, welcomeKey]);

  useEffect(() => {
    if (teamLoaded && (needsTeamName || needsFavoriteTeam) && !welcomeSeen) {
      setWelcomeOpen(true);
    } else {
      setWelcomeOpen(false);
    }
  }, [teamLoaded, needsTeamName, needsFavoriteTeam, welcomeSeen]);

  const loadLeague = async () => {
    if (!token) return;
    setLeagueError(null);
    setLeagueLoading(true);
    try {
      const data = await getMyLeague(token);
      setLeague(data);
    } catch (err) {
      if (String(err).includes("league_not_found")) {
        setLeague(null);
      } else {
        setLeagueError(String(err));
      }
    } finally {
      setLeagueLoading(false);
    }
  };

  const loadRankings = async () => {
    if (!token) return;
    setRankingError(null);
    try {
      const [general, leagueData] = await Promise.all([
        getRankingGeneral(token),
        league ? getRankingLeague(token) : Promise.resolve(null)
      ]);
      setGeneralRanking(general);
      setLeagueRanking(leagueData);
    } catch (err) {
      setRankingError(String(err));
    }
  };

  useEffect(() => {
    if (!token) return;
    loadLeague().catch(() => undefined);
    getRankingGeneral(token)
      .then(setGeneralRanking)
      .catch((err) => setRankingError(String(err)));
    getTeams().then(setTeams).catch(() => setTeams([]));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    if (!league) {
      setLeagueRanking(null);
      return;
    }
    getRankingLeague(token)
      .then(setLeagueRanking)
      .catch((err) => setRankingError(String(err)));
  }, [league, token]);

  const handleCreateLeague = async () => {
    if (!token) return;
    if (!createName.trim()) {
      setLeagueError("name_required");
      return;
    }
    setLeagueError(null);
    try {
      const data = await createLeague(token, createName.trim());
      setLeague(data);
      setCreateName("");
      await loadRankings();
    } catch (err) {
      setLeagueError(String(err));
    }
  };

  const handleJoinLeague = async () => {
    if (!token) return;
    if (!joinCode.trim()) {
      setLeagueError("code_required");
      return;
    }
    setLeagueError(null);
    try {
      const data = await joinLeague(token, joinCode.trim().toUpperCase());
      setLeague(data);
      setJoinCode("");
      await loadRankings();
    } catch (err) {
      setLeagueError(String(err));
    }
  };

  const handleLeaveLeague = async () => {
    if (!token) return;
    setLeagueError(null);
    try {
      await leaveLeague(token);
      setLeague(null);
      setLeagueRanking(null);
      await loadRankings();
    } catch (err) {
      setLeagueError(String(err));
    }
  };

  const handleRemoveMember = async (fantasyTeamId: number) => {
    if (!token) return;
    if (!confirm("Seguro que deseas expulsar a este miembro?")) {
      return;
    }
    setLeagueError(null);
    try {
      await removeLeagueMember(token, fantasyTeamId);
      await loadRankings();
      await loadLeague();
    } catch (err) {
      setLeagueError(String(err));
    }
  };

  const handleViewLineup = async (fantasyTeamId: number, teamName: string) => {
    if (!token) return;
    setLineupTeamName(teamName);
    setLineupOpen(true);
    setLineupLoading(true);
    setLineupError(null);
    setLineupData(null);
    try {
      const data = await getRankingLineup(token, fantasyTeamId);
      setLineupData(data);
      setLineupTeamName(data.team_name || teamName);
    } catch (err) {
      setLineupError(String(err));
    } finally {
      setLineupLoading(false);
    }
  };

  const leagueSubtitle = useMemo(() => {
    if (league) return `Codigo: ${league.code}`;
    return "Crea o unete con un codigo.";
  }, [league]);

  const isAdmin = league?.is_admin ?? false;

  const starters = useMemo(() => {
    return lineupData?.slots.filter((slot) => slot.is_starter) ?? [];
  }, [lineupData]);

  const bench = useMemo(() => {
    return lineupData?.slots.filter((slot) => !slot.is_starter) ?? [];
  }, [lineupData]);

  const teamNameById = useMemo(() => {
    return new Map(
      teams.map((team) => [team.id, team.name_short || team.name_full || `Equipo ${team.id}`])
    );
  }, [teams]);

  const renderSlot = (slot: PublicLineupSlot) => {
    const player = slot.player ?? null;
    const isCaptain = player && lineupData?.captain_player_id === player.player_id;
    const isVice =
      player && lineupData?.vice_captain_player_id === player.player_id;
    const positionLabel = player
      ? positionLabels[player.position] || player.position
      : positionLabels[slot.role] || slot.role;

    return (
      <div
        key={`${slot.slot_index}-${slot.player_id ?? "empty"}`}
        className="flex items-center justify-between rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs"
      >
        <div className="flex items-center gap-2">
          <div className="relative h-9 w-9 overflow-hidden rounded-full bg-surface2/60 ring-1 ring-white/10">
            {player ? (
              <img
                src={`/images/players/${player.player_id}.png`}
                alt=""
                className="h-full w-full object-cover"
                onError={(event) => {
                  (event.currentTarget as HTMLImageElement).style.display = "none";
                }}
              />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-[10px] text-muted">
                -
              </span>
            )}
            {player ? (
              <span className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-black/70">
                <img
                  src={`/images/teams/${player.team_id}.png`}
                  alt=""
                  className="h-full w-full object-contain"
                />
              </span>
            ) : null}
          </div>
          <div>
            <p className="text-xs font-semibold text-ink">
              {player ? player.short_name || player.name : "Sin jugador"}
            </p>
            <p className="text-[10px] text-muted">{positionLabel}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {isCaptain ? (
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-yellow-300 text-[10px] font-bold text-black">
              C
            </span>
          ) : null}
          {isVice ? (
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-gray-300 text-[10px] font-bold text-black">
              V
            </span>
          ) : null}
        </div>
      </div>
    );
  };

  if (!token) return <AuthPanel />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Ranking</h1>
        <p className="text-sm text-muted">Ligas privadas y ranking general.</p>
        <div className="mt-3 flex items-center gap-2 text-xs text-muted">
          <span>Equipo favorito:</span>
          {favoriteTeamId ? (
            <span className="flex items-center gap-2 rounded-full border border-white/10 px-2 py-1">
              <img
                src={`/images/teams/${favoriteTeamId}.png`}
                alt=""
                className="h-5 w-5 object-contain"
              />
              <span className="text-ink">
                {teamNameById.get(favoriteTeamId) || `Equipo ${favoriteTeamId}`}
              </span>
            </span>
          ) : (
            <button
              onClick={() => setFavoriteGateOpen(true)}
              className="flex items-center gap-2 rounded-full border border-white/10 px-2 py-1 text-xs text-ink"
            >
              <img src="/favicon.png" alt="" className="h-5 w-5 object-contain" />
              <span>Sin equipo</span>
            </button>
          )}
        </div>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-semibold text-ink">Liga privada</p>
            <p className="text-xs text-muted">{leagueSubtitle}</p>
          </div>
        </div>

        {leagueLoading ? <p className="text-xs text-muted">Cargando...</p> : null}
        {leagueError ? <p className="text-xs text-warning">{leagueError}</p> : null}

        {league ? (
          <div className="space-y-3">
            <RankingTable
              title={`Tabla ${league.name}`}
              data={leagueRanking}
              onSelectTeam={handleViewLineup}
            />
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-muted">
                <span>Miembros</span>
                <button
                  onClick={handleLeaveLeague}
                  className="rounded-full border border-white/10 px-3 py-1 text-xs text-ink"
                >
                  Salir de la liga
                </button>
              </div>
              {leagueRanking?.entries.map((entry) => {
                const isOwner = entry.fantasy_team_id === league.owner_fantasy_team_id;
                const canRemove =
                  isAdmin && entry.fantasy_team_id !== teamId && teamId !== null;
                return (
                  <div
                    key={`member-${entry.fantasy_team_id}`}
                    className="flex items-center justify-between rounded-xl border border-white/10 px-3 py-2 text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          handleViewLineup(entry.fantasy_team_id, entry.team_name)
                        }
                        className="font-semibold text-ink transition hover:text-accent"
                      >
                        {entry.team_name}
                      </button>
                      {isOwner ? (
                        <span className="rounded-full bg-accent/20 px-2 py-0.5 text-[10px] text-accent">
                          Admin
                        </span>
                      ) : null}
                    </div>
                    {canRemove ? (
                      <button
                        onClick={() => handleRemoveMember(entry.fantasy_team_id)}
                        className="rounded-full border border-white/10 px-3 py-1 text-[10px] text-warning"
                      >
                        Quitar
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <p className="text-xs text-muted">Crear liga</p>
              <input
                value={createName}
                onChange={(event) => setCreateName(event.target.value)}
                placeholder="Nombre de la liga"
                className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
              />
              <button
                onClick={handleCreateLeague}
                className="w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
              >
                Crear liga
              </button>
            </div>
            <div className="space-y-2">
              <p className="text-xs text-muted">Unirse por codigo</p>
              <input
                value={joinCode}
                onChange={(event) => setJoinCode(event.target.value)}
                placeholder="ABC123"
                className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm uppercase"
              />
              <button
                onClick={handleJoinLeague}
                className="w-full rounded-xl border border-white/10 px-4 py-2 text-sm text-ink"
              >
                Unirse
              </button>
            </div>
          </div>
        )}
      </div>

      {rankingError ? (
        <div className="glass rounded-2xl p-3 text-xs text-warning">{rankingError}</div>
      ) : null}

      <RankingTable
        title="Ranking general"
        data={generalRanking}
        onSelectTeam={handleViewLineup}
      />

      {lineupOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6">
          <div className="glass max-h-[85vh] w-full max-w-xl space-y-4 overflow-y-auto rounded-2xl p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-ink">
                  {lineupData?.team_name || lineupTeamName || "Equipo"}
                </h3>
                <p className="text-xs text-muted">
                  {lineupData?.round_number
                    ? `Ronda ${lineupData.round_number}`
                    : "Sin ronda registrada"}
                </p>
              </div>
              <button
                onClick={() => setLineupOpen(false)}
                className="rounded-full border border-white/10 px-3 py-1 text-xs text-ink"
              >
                Cerrar
              </button>
            </div>

            {lineupLoading ? <p className="text-xs text-muted">Cargando...</p> : null}
            {lineupError ? (
              <p className="text-xs text-warning">
                {lineupError === "lineup_not_found"
                  ? "Este equipo aun no guardo su XI."
                  : lineupError}
              </p>
            ) : null}

            {!lineupLoading && lineupData ? (
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-muted">
                    <span>Titulares</span>
                    <span>{starters.length}/11</span>
                  </div>
                  <div className="space-y-2">{starters.map(renderSlot)}</div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-muted">
                    <span>Suplentes</span>
                    <span>{bench.length}/4</span>
                  </div>
                  <div className="space-y-2">{bench.map(renderSlot)}</div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      <WelcomeSlideshow
        open={welcomeOpen}
        onComplete={() => {
          localStorage.setItem(welcomeKey, "1");
          setWelcomeSeen(true);
          setWelcomeOpen(false);
          if (needsFavoriteTeam) {
            setFavoriteGateOpen(true);
          } else {
            setNameGateOpen(true);
          }
        }}
      />

      <FavoriteTeamGate
        open={favoriteGateOpen}
        selectedTeamId={favoriteTeamId}
        onSelect={(teamId) => setFavoriteTeamId(teamId)}
        onSave={async () => {
          if (!token || !favoriteTeamId) return;
          setFavoriteError(null);
          try {
            await updateFavoriteTeam(token, favoriteTeamId);
            setNeedsFavoriteTeam(false);
            setFavoriteGateOpen(false);
            setNameGateOpen(true);
          } catch (err) {
            setFavoriteError(String(err));
          }
        }}
        onClose={() => {
          if (!needsFavoriteTeam) {
            setFavoriteGateOpen(false);
          }
        }}
      />

      {favoriteError ? (
        <div className="glass rounded-2xl p-3 text-xs text-warning">{favoriteError}</div>
      ) : null}

      <TeamNameGate
        open={nameGateOpen}
        teamName={teamName}
        onTeamNameChange={setTeamName}
        error={teamNameError}
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
            setNameGateOpen(false);
          } catch {
            setTeamNameError("No se pudo guardar el nombre.");
          }
        }}
      />
    </div>
  );
}
