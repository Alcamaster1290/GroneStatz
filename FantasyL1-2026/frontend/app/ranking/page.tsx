"use client";

import { useEffect, useMemo, useState } from "react";

import AuthPanel from "@/components/AuthPanel";
import TeamNameGate from "@/components/TeamNameGate";
import WelcomeSlideshow from "@/components/WelcomeSlideshow";
import {
  createLeague,
  createTeam,
  getMyLeague,
  getRankingGeneral,
  getRankingLeague,
  getTeam,
  joinLeague,
  leaveLeague,
  removeLeagueMember
} from "../../lib/api";
import { useFantasyStore } from "../../lib/store";
import { League, RankingResponse } from "../../lib/types";

function RankingTable({
  title,
  data
}: {
  title: string;
  data: RankingResponse | null;
}) {
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
                <span className="font-semibold text-ink">{entry.team_name}</span>
              </div>
              <span className="text-sm font-semibold text-accent">
                {entry.total_points.toFixed(1)}
              </span>
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
                    R{round.round_number}: {round.cumulative.toFixed(1)}
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
        setNeedsTeamName(!team.name?.trim());
        setTeamLoaded(true);
      })
      .catch(() => {
        setNeedsTeamName(true);
        setTeamLoaded(true);
      });
  }, [token]);

  useEffect(() => {
    if (teamLoaded && needsTeamName) {
      setNameGateOpen(!welcomeOpen);
    } else {
      setNameGateOpen(false);
    }
  }, [teamLoaded, needsTeamName, welcomeOpen]);

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
    if (teamLoaded && needsTeamName && !welcomeSeen) {
      setWelcomeOpen(true);
    } else {
      setWelcomeOpen(false);
    }
  }, [teamLoaded, needsTeamName, welcomeSeen]);

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

  const leagueSubtitle = useMemo(() => {
    if (league) return `Codigo: ${league.code}`;
    return "Crea o unete con un codigo.";
  }, [league]);

  const isAdmin = league?.is_admin ?? false;

  if (!token) return <AuthPanel />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Ranking</h1>
        <p className="text-sm text-muted">Ligas privadas y ranking general.</p>
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
            <RankingTable title={`Tabla ${league.name}`} data={leagueRanking} />
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
                      <span className="font-semibold text-ink">{entry.team_name}</span>
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

      <RankingTable title="Ranking general" data={generalRanking} />

      <WelcomeSlideshow
        open={welcomeOpen}
        onComplete={() => {
          localStorage.setItem(welcomeKey, "1");
          setWelcomeSeen(true);
          setWelcomeOpen(false);
          setNameGateOpen(true);
        }}
      />

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
