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
  getRankingMarket,
  getRounds,
  getTeam,
  getTeams,
  joinLeague,
  leaveLeague,
  removeLeagueMember,
  updateFavoriteTeam
} from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import {
  League,
  PublicLineup,
  PublicLineupSlot,
  PublicMarket,
  PublicMarketPlayer,
  RankingResponse,
  RoundInfo
} from "@/lib/types";

const positionLabels: Record<string, string> = {
  G: "Arquero",
  D: "Defensa",
  M: "Mediocampo",
  F: "Delantero"
};

type TopRankStyle = {
  medal: string;
  color: string;
  borderClass: string;
  backgroundClass: string;
};

const TOP_RANK_STYLES: Record<number, TopRankStyle> = {
  1: {
    medal: "Oro",
    color: "#F6C453",
    borderClass: "border-[#F6C453]/45",
    backgroundClass: "bg-gradient-to-r from-[#3A2A08]/45 via-[#5B3E0E]/30 to-transparent"
  },
  2: {
    medal: "Plata",
    color: "#D5DBE4",
    borderClass: "border-[#D5DBE4]/45",
    backgroundClass: "bg-gradient-to-r from-[#2B323C]/45 via-[#485360]/30 to-transparent"
  },
  3: {
    medal: "Bronce",
    color: "#CD7F32",
    borderClass: "border-[#CD7F32]/45",
    backgroundClass: "bg-gradient-to-r from-[#3A2110]/45 via-[#5A3520]/30 to-transparent"
  },
  4: {
    medal: "Cobre",
    color: "#B87333",
    borderClass: "border-[#B87333]/40",
    backgroundClass: "bg-gradient-to-r from-[#3A1E11]/40 via-[#4A2C1E]/28 to-transparent"
  },
  5: {
    medal: "Estano",
    color: "#A8B1B9",
    borderClass: "border-[#A8B1B9]/35",
    backgroundClass: "bg-gradient-to-r from-[#2D3338]/40 via-[#414B54]/25 to-transparent"
  }
};

const RELIEF_TEXT_SHADOW =
  "0 1px 0 rgba(255,255,255,0.35), 0 2px 0 rgba(0,0,0,0.5), 0 6px 10px rgba(0,0,0,0.35)";

function RankingTable({
  title,
  data,
  onSelectTeam,
  pendingRoundNumber
}: {
  title: string;
  data: RankingResponse | null;
  onSelectTeam?: (fantasyTeamId: number, teamName: string) => void;
  pendingRoundNumber: number | null;
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
        {data.entries.map((entry, index) => {
          const rank = index + 1;
          const topStyle = TOP_RANK_STYLES[rank];
          const isTopFive = Boolean(topStyle);
          return (
            <div
              key={entry.fantasy_team_id}
              className={
                "flex flex-col gap-2 rounded-2xl border px-3 py-2 transition " +
                (isTopFive
                  ? `${topStyle.backgroundClass} ${topStyle.borderClass} shadow-[inset_0_1px_0_rgba(255,255,255,0.12),inset_0_-1px_0_rgba(0,0,0,0.35),0_10px_22px_rgba(0,0,0,0.28)]`
                  : "border-white/10")
              }
            >
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span
                  className={"text-xs font-bold " + (isTopFive ? "" : "text-muted")}
                  style={
                    isTopFive
                      ? {
                          color: topStyle.color,
                          textShadow: RELIEF_TEXT_SHADOW
                        }
                      : undefined
                  }
                >
                  #{rank}
                </span>
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
                  style={
                    isTopFive
                      ? {
                          color: topStyle.color,
                          textShadow: RELIEF_TEXT_SHADOW
                        }
                      : undefined
                  }
                >
                  {entry.team_name}
                </button>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={"text-sm font-semibold " + (isTopFive ? "" : "text-accent")}
                  style={
                    isTopFive
                      ? {
                          color: topStyle.color,
                          textShadow: RELIEF_TEXT_SHADOW
                        }
                      : undefined
                  }
                >
                  {Math.round(entry.total_points)}
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
                    R{round.round_number}: {Math.round(round.points)}
                    {pendingRoundNumber === round.round_number && typeof round.price_delta === "number" ? ` · Δ ${round.price_delta > 0 ? "+" : ""}${round.price_delta.toFixed(1)}` : ""}
                  </span>
                ))
              )}
            </div>
          </div>
          );
        })}
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
  const [isNewTeam, setIsNewTeam] = useState(false);
  const [nameGateOpen, setNameGateOpen] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [welcomeSeen, setWelcomeSeen] = useState(false);
  const [teamNameError, setTeamNameError] = useState<string | null>(null);

  const [league, setLeague] = useState<League | null>(null);
  const [leagueError, setLeagueError] = useState<string | null>(null);
  const [leagueLoading, setLeagueLoading] = useState(false);

  const [leagueRanking, setLeagueRanking] = useState<RankingResponse | null>(null);
  const [generalRanking, setGeneralRanking] = useState<RankingResponse | null>(null);
  const [showAllGeneral, setShowAllGeneral] = useState(false);
  const [rankingError, setRankingError] = useState<string | null>(null);

  const [createName, setCreateName] = useState("");
  const [joinCode, setJoinCode] = useState("");

  const [lineupOpen, setLineupOpen] = useState(false);
  const [lineupLoading, setLineupLoading] = useState(false);
  const [lineupError, setLineupError] = useState<string | null>(null);
  const [lineupData, setLineupData] = useState<PublicLineup | null>(null);
  const [lineupTeamName, setLineupTeamName] = useState("");
  const [lineupTeamId, setLineupTeamId] = useState<number | null>(null);
  const [lineupRoundNumber, setLineupRoundNumber] = useState<number | null>(null);
  const [marketData, setMarketData] = useState<PublicMarket | null>(null);
  const [roundsInfo, setRoundsInfo] = useState<RoundInfo[]>([]);
  const pendingRoundNumber = useMemo(
    () => roundsInfo.find((round) => !round.is_closed)?.round_number ?? null,
    [roundsInfo]
  );
  const normalizeErrorCode = (value: string | null) =>
    value ? value.replace(/^Error:\s*/i, "").trim() : "";

  const toFriendlyError = (value: string | null) => {
    const code = normalizeErrorCode(value);
    if (!code) return null;
    if (code.includes("offline_write_blocked")) {
      return "Sin conexion, solo lectura.";
    }
    if (code === "market_complete_without_lineup") {
      return "Mercado completo, sin equipo guardado";
    }
    return code;
  };

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
        setTeamId(team.id ?? null);
        setFavoriteTeamId(team.favorite_team_id ?? null);
        const hasName = Boolean(team.name?.trim());
        const hasFavorite = Boolean(team.favorite_team_id);
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
    getRounds().then(setRoundsInfo).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!teamLoaded) {
      setFavoriteGateOpen(false);
      setNameGateOpen(false);
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

  const availableRounds = useMemo(() => {
    if (generalRanking?.round_numbers?.length) {
      return generalRanking.round_numbers.slice();
    }
    if (leagueRanking?.round_numbers?.length) {
      return leagueRanking.round_numbers.slice();
    }
    return [];
  }, [generalRanking, leagueRanking]);

  const loadLineup = async (
    fantasyTeamId: number,
    teamName: string,
    roundNumber?: number | null
  ) => {
    if (!token) return;
    setLineupLoading(true);
    setLineupError(null);
    setLineupData(null);
    if (roundNumber) {
      setLineupRoundNumber(roundNumber);
    }
    try {
      const data = await getRankingLineup(
        token,
        fantasyTeamId,
        roundNumber ?? undefined
      );
      setLineupData(data);
      setLineupTeamName(data.team_name || teamName);
      setLineupRoundNumber(data.round_number ?? roundNumber ?? null);
    } catch (err) {
      setLineupError(String(err));
    } finally {
      setLineupLoading(false);
    }
  };

  const handleViewLineup = async (fantasyTeamId: number, teamName: string) => {
    if (!token) return;
    setLineupTeamName(teamName);
    setLineupTeamId(fantasyTeamId);
    setLineupOpen(true);
    setLineupLoading(true);
    setLineupError(null);
    setLineupData(null);
    setMarketData(null);
    const initialRound =
      availableRounds.length > 0 ? availableRounds[availableRounds.length - 1] : null;
    if (fantasyTeamId) {
      loadMarket(fantasyTeamId, teamName);
    }
    await loadLineup(fantasyTeamId, teamName, initialRound);
  };

  const loadMarket = async (fantasyTeamId: number, teamName: string) => {
    if (!token) return;
    try {
      const data = await getRankingMarket(token, fantasyTeamId);
      setMarketData(data);
      setLineupTeamName(data.team_name || teamName);
    } catch (err) {
      console.error(err);
    }
  };

  const leagueSubtitle = useMemo(() => {
    if (league) return `Codigo: ${league.code}`;
    return "Crea o unete con un codigo.";
  }, [league]);

  const generalVisibleEntries = useMemo(() => {
    if (!generalRanking?.entries?.length) return [];
    return showAllGeneral ? generalRanking.entries : generalRanking.entries.slice(0, 30);
  }, [generalRanking, showAllGeneral]);

  const generalHiddenCount = useMemo(() => {
    if (!generalRanking?.entries?.length) return 0;
    return Math.max(generalRanking.entries.length - generalVisibleEntries.length, 0);
  }, [generalRanking, generalVisibleEntries.length]);

  const generalRankingVisible = useMemo(() => {
    if (!generalRanking) return null;
    return {
      ...generalRanking,
      entries: generalVisibleEntries
    };
  }, [generalRanking, generalVisibleEntries]);

  const isAdmin = league?.is_admin ?? false;

  useEffect(() => {
    setShowAllGeneral(false);
  }, [generalRanking?.entries?.length]);

  const starters = useMemo(() => {
    return lineupData?.slots.filter((slot) => slot.is_starter) ?? [];
  }, [lineupData]);

  const bench = useMemo(() => {
    return lineupData?.slots.filter((slot) => !slot.is_starter) ?? [];
  }, [lineupData]);

  const marketPriceByPlayerId = useMemo(() => {
    const map = new Map<number, number>();
    marketData?.players.forEach((player) => {
      map.set(player.player_id, player.price_current ?? 0);
    });
    return map;
  }, [marketData]);

  const lineupRoundIndex = useMemo(() => {
    if (!lineupRoundNumber) return -1;
    return availableRounds.indexOf(lineupRoundNumber);
  }, [availableRounds, lineupRoundNumber]);
  const canPrevLineupRound = lineupRoundIndex > 0;
  const canNextLineupRound =
    lineupRoundIndex >= 0 && lineupRoundIndex < availableRounds.length - 1;

  const teamNameById = useMemo(() => {
    return new Map(
      teams.map((team) => [team.id, team.name_short || team.name_full || `Equipo ${team.id}`])
    );
  }, [teams]);

  const roundInfoByNumber = useMemo(() => {
    return new Map(roundsInfo.map((round) => [round.round_number, round]));
  }, [roundsInfo]);

  const lineupRoundInfo = useMemo(() => {
    if (!lineupRoundNumber) return null;
    return roundInfoByNumber.get(lineupRoundNumber) ?? null;
  }, [lineupRoundNumber, roundInfoByNumber]);
  const lineupErrorCode = normalizeErrorCode(lineupError);
  const isMarketOnlyError = lineupErrorCode === "market_complete_without_lineup";
  const isMissingLineupError =
    lineupErrorCode === "market_complete_without_lineup" ||
    lineupErrorCode === "lineup_not_found";

  const lineupIsPending = useMemo(() => {
    if (!lineupRoundInfo) return false;
    if (lineupRoundInfo.status) {
      return lineupRoundInfo.status === "Pendiente";
    }
    return !lineupRoundInfo.is_closed;
  }, [lineupRoundInfo]);

  const bonusPlayerId = useMemo(() => {
    if (!lineupData) return null;
    const captainId = lineupData.captain_player_id ?? null;
    const viceId = lineupData.vice_captain_player_id ?? null;
    if (lineupIsPending) return null;

    const findSlot = (playerId: number | null) =>
      lineupData.slots.find((slot) => slot.player_id === playerId);

    const captainSlot = findSlot(captainId);
    const captainPoints = captainSlot?.points ?? 0;
    const captainInjured = captainSlot?.player?.is_injured ?? false;
    if (captainSlot?.is_starter && captainPoints !== 0 && !captainInjured) {
      return captainId;
    }

    const viceSlot = findSlot(viceId);
    const vicePoints = viceSlot?.points ?? 0;
    const viceInjured = viceSlot?.player?.is_injured ?? false;
    if (viceSlot?.is_starter && vicePoints !== 0 && !viceInjured) {
      return viceId;
    }

    return null;
  }, [lineupData, lineupIsPending]);

  const renderSlot = (slot: PublicLineupSlot) => {
    const player = slot.player ?? null;
    const isCaptain = player && lineupData?.captain_player_id === player.player_id;
    const isVice =
      player && lineupData?.vice_captain_player_id === player.player_id;
    const positionLabel = player
      ? positionLabels[player.position] || player.position
      : positionLabels[slot.role] || slot.role;
    const points = slot.points ?? 0;
    const price = player ? marketPriceByPlayerId.get(player.player_id) ?? 0 : 0;
    const displayValue =
      lineupIsPending
        ? price
        : slot.player_id && slot.player_id === bonusPlayerId
          ? points * 3
          : points;

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
        <div className="flex items-center gap-2">
          {player ? (
            <span className="text-xs font-semibold text-ink">
              {lineupIsPending ? displayValue.toFixed(1) : Math.round(displayValue)}
            </span>
          ) : null}
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

  const renderMarketPlayer = (
    player: PublicMarketPlayer,
    options: { showPoints?: boolean } = {}
  ) => {
    const showPoints = options.showPoints ?? true;
    const positionLabel = positionLabels[player.position] || player.position;
    return (
      <div
        key={`market-${player.player_id}`}
        className={`flex items-center rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs ${
          showPoints ? "justify-between" : "justify-start"
        }`}
      >
        <div className="flex items-center gap-2">
          <div className="relative h-9 w-9 overflow-hidden rounded-full bg-surface2/60 ring-1 ring-white/10">
            <img
              src={`/images/players/${player.player_id}.png`}
              alt=""
              className="h-full w-full object-cover"
              onError={(event) => {
                (event.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
            <span className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-black/70">
              <img
                src={`/images/teams/${player.team_id}.png`}
                alt=""
                className="h-full w-full object-contain"
              />
            </span>
          </div>
          <div>
            <p className="text-xs font-semibold text-ink">
              {player.short_name || player.name}
            </p>
            <p className="text-[10px] text-muted">{positionLabel}</p>
          </div>
        </div>
        {showPoints ? (
          <div className="text-right">
            <p className="text-[10px] text-muted">Pts totales</p>
            <p className="text-sm font-semibold text-ink">{player.points_total.toFixed(1)}</p>
          </div>
        ) : null}
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

      {rankingError ? (
        <div className="glass rounded-2xl p-3 text-xs text-warning">{toFriendlyError(rankingError)}</div>
      ) : null}

      <RankingTable
        title="Ranking general"
        data={generalRankingVisible}
        onSelectTeam={handleViewLineup}
        pendingRoundNumber={pendingRoundNumber}
      />

      {generalHiddenCount > 0 && !showAllGeneral ? (
        <div className="relative py-1">
          <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-white/10" />
          <div className="relative mx-auto flex w-fit items-center gap-3 rounded-full border border-white/15 bg-black/45 px-3 py-1.5">
            <span className="text-[11px] text-muted">
              {generalHiddenCount} equipos ocultos
            </span>
            <button
              type="button"
              onClick={() => setShowAllGeneral(true)}
              className="rounded-full bg-accent px-3 py-1 text-[11px] font-semibold text-black"
            >
              Mostrar más
            </button>
          </div>
        </div>
      ) : null}

      <div className="glass space-y-3 rounded-2xl p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-semibold text-ink">Liga privada</p>
            <p className="text-xs text-muted">{leagueSubtitle}</p>
          </div>
        </div>

        {leagueLoading ? <p className="text-xs text-muted">Cargando...</p> : null}
        {leagueError ? <p className="text-xs text-warning">{toFriendlyError(leagueError)}</p> : null}

        {league ? (
          <div className="space-y-3">
            <RankingTable
              title={`Tabla ${league.name}`}
              data={leagueRanking}
              onSelectTeam={handleViewLineup}
              pendingRoundNumber={pendingRoundNumber}
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

      {lineupOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6">
          <div className="glass max-h-[85vh] w-full max-w-xl space-y-4 overflow-y-auto rounded-2xl p-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-ink">
                {isMarketOnlyError ? "Mercado" : "XI titular"}
              </h3>
              <button
                onClick={() => setLineupOpen(false)}
                className="rounded-full border border-white/10 px-3 py-1 text-xs text-ink"
              >
                X
              </button>
            </div>
            {lineupRoundNumber ? (
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                <button
                  type="button"
                  onClick={() => {
                    if (canPrevLineupRound && lineupTeamId) {
                      const nextRound = availableRounds[lineupRoundIndex - 1];
                      loadLineup(lineupTeamId, lineupTeamName || "Equipo", nextRound);
                    }
                  }}
                  disabled={!canPrevLineupRound}
                  className="rounded-lg border border-white/10 px-2 py-1 text-ink disabled:opacity-40"
                >
                  {"<"}
                </button>
                <span>Ronda {lineupRoundNumber}</span>
                <button
                  type="button"
                  onClick={() => {
                    if (canNextLineupRound && lineupTeamId) {
                      const nextRound = availableRounds[lineupRoundIndex + 1];
                      loadLineup(lineupTeamId, lineupTeamName || "Equipo", nextRound);
                    }
                  }}
                  disabled={!canNextLineupRound}
                  className="rounded-lg border border-white/10 px-2 py-1 text-ink disabled:opacity-40"
                >
                  {">"}
                </button>
              </div>
            ) : null}

            {lineupLoading ? <p className="text-xs text-muted">Cargando...</p> : null}
            {lineupError && isMissingLineupError ? (
              <div className="rounded-xl border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
                <p className="font-semibold">
                  {lineupErrorCode === "lineup_not_found"
                    ? "Sin equipo guardado para esta ronda."
                    : "Mercado completo, sin equipo guardado."}
                </p>
                <p className="mt-1 text-[11px]">
                  {lineupErrorCode === "lineup_not_found"
                    ? "No hay XI disponible para mostrar en esta ronda."
                    : "Este equipo solo puede mostrar mercado para esta ronda."}
                </p>
              </div>
            ) : null}
            {lineupError && !isMissingLineupError ? (
              <p className="text-xs text-warning">
                {lineupErrorCode === "lineup_not_found"
                  ? "Este equipo aun no guardo su XI."
                  : toFriendlyError(lineupError)}
              </p>
            ) : null}

            {!lineupLoading && lineupData && !isMarketOnlyError ? (
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

            {!lineupLoading && isMarketOnlyError ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-muted">
                  <span>Mercado</span>
                  <span>{marketData?.players.length ?? 0} jugadores</span>
                </div>
                {marketData?.players.length ? (
                  <div className="space-y-2">
                    {marketData.players.map((player) =>
                      renderMarketPlayer(player, { showPoints: false })
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-muted">No hay jugadores de mercado para mostrar.</p>
                )}
              </div>
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
          } catch (err) {
            setFavoriteError(String(err));
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



