"use client";

import { useEffect, useMemo, useState } from "react";

import AuthPanel from "@/components/AuthPanel";
import FavoriteTeamGate from "@/components/FavoriteTeamGate";
import TeamNameGate from "@/components/TeamNameGate";
import WelcomeSlideshow from "@/components/WelcomeSlideshow";
import { createTeam, getPlayerStats, getTeam, getTeams, updateFavoriteTeam } from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import { PlayerStatsEntry, Position } from "@/lib/types";

const positionLabels: Record<string, string> = {
  G: "Arquero",
  D: "Defensa",
  M: "Mediocampo",
  F: "Delantero"
};

const renderSparkline = (values: number[]) => {
  if (!values.length) return null;
  const width = 56;
  const height = 18;
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

export default function StatsPage() {
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);
  const userEmail = useFantasyStore((state) => state.userEmail);

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

  const [players, setPlayers] = useState<PlayerStatsEntry[]>([]);
  const [activeTeamIds, setActiveTeamIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>([]);

  const [query, setQuery] = useState("");
  const [position, setPosition] = useState<Position | "">("");
  const [teamId, setTeamId] = useState("");
  const [sortKey, setSortKey] = useState<
    "points" | "goals" | "assists" | "price" | "price_delta" | "selected"
  >("selected");

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
        const hasName = Boolean(team.name?.trim());
        const favoriteId =
          typeof team.favorite_team_id === "number" ? team.favorite_team_id : null;
        setFavoriteTeamId(favoriteId);
        const hasFavorite = Boolean(favoriteId);
        setNeedsTeamName(!hasName);
        setNeedsFavoriteTeam(hasName && !hasFavorite);
        setIsNewTeam(!hasName);
        setTeamLoaded(true);
      })
      .catch(() => {
        setNeedsTeamName(false);
        setNeedsFavoriteTeam(false);
        setIsNewTeam(false);
        setTeamLoaded(true);
      });
  }, [token]);

  useEffect(() => {
    getTeams().then(setTeams).catch(() => undefined);
  }, []);

  const activeTeams = useMemo(() => {
    if (activeTeamIds.size === 0) return teams;
    return teams.filter((team) => activeTeamIds.has(team.id));
  }, [teams, activeTeamIds]);

  useEffect(() => {
    if (!teamLoaded) {
      setNameGateOpen(false);
      setFavoriteGateOpen(false);
      return;
    }
    if (!welcomeSeen && isNewTeam && needsTeamName) {
      setNameGateOpen(false);
      setFavoriteGateOpen(false);
      return;
    }
    if (needsTeamName) {
      setNameGateOpen(true);
      setFavoriteGateOpen(false);
      return;
    }
    if (needsFavoriteTeam) {
      setFavoriteGateOpen(true);
      setNameGateOpen(false);
      return;
    }
    setNameGateOpen(false);
    setFavoriteGateOpen(false);
  }, [teamLoaded, isNewTeam, needsTeamName, needsFavoriteTeam, welcomeSeen]);

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
    if (isNewTeam && teamLoaded && needsTeamName && !welcomeSeen) {
      setWelcomeOpen(true);
    } else {
      setWelcomeOpen(false);
    }
  }, [teamLoaded, isNewTeam, needsTeamName, needsFavoriteTeam, welcomeSeen]);

  const fetchAllStats = async (params: {
    q?: string;
    position?: Position;
    team_id?: number;
  }) => {
    const limit = 200;
    const maxPages = 30;
    const all: PlayerStatsEntry[] = [];
    for (let page = 0; page < maxPages; page += 1) {
      const batch = await getPlayerStats({
        ...params,
        limit,
        offset: page * limit
      });
      all.push(...batch);
      if (batch.length < limit) break;
    }
    return all;
  };

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAllStats({
        q: query.trim() || undefined,
        position: position || undefined,
        team_id: teamId ? Number(teamId) : undefined
      });
      setPlayers(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleLoad().catch(() => undefined);
  }, []);

  useEffect(() => {
    fetchAllStats({})
      .then((data) => {
        setActiveTeamIds(new Set(data.map((player) => player.team_id)));
      })
      .catch(() => undefined);
  }, []);

  const sortedPlayers = useMemo(() => {
    const list = [...players];
    const getPointsTotal = (player: PlayerStatsEntry) =>
      (player.rounds || []).reduce((sum, round) => sum + (round.points || 0), 0);
    list.sort((a, b) => {
      switch (sortKey) {
        case "points":
          return getPointsTotal(b) - getPointsTotal(a);
        case "goals":
          return (b.goals || 0) - (a.goals || 0);
        case "assists":
          return (b.assists || 0) - (a.assists || 0);
        case "price":
          return (b.price_current || 0) - (a.price_current || 0);
        case "price_delta":
          return (b.price_delta || 0) - (a.price_delta || 0);
        case "selected":
        default:
          return (b.selected_count || 0) - (a.selected_count || 0);
      }
    });
    return list;
  }, [players, sortKey]);

  if (!token) {
    return <AuthPanel />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Estadisticas</h1>
        <p className="text-xs text-muted">Seleccion y totales por jugador.</p>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-xs text-muted">Busqueda de nombre</label>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
              placeholder="Ej: Paolo"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Posicion</label>
            <select
              value={position}
              onChange={(event) => setPosition(event.target.value as Position | "")}
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            >
              <option value="">Todas</option>
              <option value="G">Arquero</option>
              <option value="D">Defensa</option>
              <option value="M">Mediocampo</option>
              <option value="F">Delantero</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Equipo</label>
            <select
              value={teamId}
              onChange={(event) => setTeamId(event.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            >
              <option value="">Todos</option>
              {activeTeams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name_short || team.name_full || `Equipo ${team.id}`}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Ordenar por</label>
            <select
              value={sortKey}
              onChange={(event) =>
                setSortKey(
                  event.target.value as
                    | "points"
                    | "goals"
                    | "assists"
                    | "price"
                    | "price_delta"
                    | "selected"
                )
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            >
              <option value="selected">Veces elegido</option>
              <option value="points">Puntos</option>
              <option value="goals">Goles</option>
              <option value="assists">Asistencias</option>
              <option value="price">Precio</option>
              <option value="price_delta">Variacion de precio</option>
            </select>
          </div>
        </div>
        <button
          onClick={handleLoad}
          className="w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
        >
          Actualizar
        </button>
        {error ? <p className="text-xs text-warning">{error}</p> : null}
      </div>

      <div className="space-y-3">
        {loading ? <p className="text-xs text-muted">Cargando...</p> : null}
        {sortedPlayers.length === 0 && !loading ? (
          <p className="text-xs text-muted">Sin jugadores para mostrar.</p>
        ) : (
          sortedPlayers.map((player) => {
            const percent = Math.min(100, Math.max(0, player.selected_percent));
            const isKeeper = player.position === "G";
            const rounds = player.rounds ?? [];
            const roundPoints = rounds.map((round) => round.points);
            const priceDelta = typeof player.price_delta === "number" ? player.price_delta : 0;
            const deltaTone =
              priceDelta === 0
                ? "text-amber-300"
                : priceDelta > 0
                  ? "text-emerald-300"
                  : "text-red-300";
            const deltaSymbol =
              priceDelta === 0 ? "-" : priceDelta > 0 ? "\u25B2" : "\u25BC";
            const deltaValue = priceDelta === 0 ? "-" : priceDelta.toFixed(1);
            return (
              <div
                key={player.player_id}
                className="space-y-2 rounded-2xl border border-white/10 bg-black/20 px-3 py-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="relative h-12 w-12 overflow-hidden rounded-full bg-surface2/60">
                      <img
                        src={`/images/players/${player.player_id}.png`}
                        alt=""
                        className="h-full w-full object-cover"
                        onError={(event) => {
                          (event.currentTarget as HTMLImageElement).style.display = "none";
                        }}
                      />
                      <span className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-black/70 text-[9px] text-ink">
                        {player.position}
                      </span>
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-ink">
                          {player.short_name || player.name}
                        </span>
                        {player.is_injured ? (
                          <span className="rounded-full border border-red-400/40 bg-red-500/10 px-2 py-0.5 text-[10px] text-red-200">
                            Lesionado
                          </span>
                        ) : null}
                      </div>
                      <div className="flex items-center gap-2 text-[10px] text-muted">
                        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-black/40">
                          <img
                            src={`/images/teams/${player.team_id}.png`}
                            alt=""
                            className="h-full w-full object-contain"
                          />
                        </span>
                        <span>{positionLabels[player.position] || player.position}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-muted">
                        <span>Min {player.minutesplayed}</span>
                        {isKeeper ? (
                          <span>At {player.saves}</span>
                        ) : (
                          <>
                            <span>G {player.goals}</span>
                            <span>A {player.assists}</span>
                          </>
                        )}
                        <span>F {player.fouls}</span>
                        <span className="inline-flex items-center gap-1">
                          <span className="inline-block h-[12px] w-[8px] rounded-sm bg-yellow-400" />
                          {player.yellow_cards}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <span className="inline-block h-[12px] w-[8px] rounded-sm bg-red-500" />
                          {player.red_cards}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2 text-right">
                    <p className="text-sm font-semibold text-accent">
                      {player.price_current.toFixed(1)}
                    </p>
                    <div className="flex items-center gap-1 text-[10px] text-muted">
                      {renderSparkline(roundPoints)}
                      <span className={deltaTone}>{deltaSymbol} {deltaValue}</span>
                    </div>
                    <p className="text-xs font-semibold text-indigo-300">
                      {percent.toFixed(1)}%
                    </p>
                    <p className="text-[10px] text-muted">
                      En {player.selected_count} equipos
                    </p>
                    <div className="h-1 w-16 rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-yellow-400"
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 text-[10px] text-muted">
                  {rounds.length === 0 ? (
                    <span className="rounded-full border border-white/10 px-2 py-1">
                      Sin rondas
                    </span>
                  ) : (
                    rounds.map((round) => (
                      <span
                        key={`${player.player_id}-round-${round.round_number}`}
                        className="rounded-full border border-white/10 px-2 py-1"
                      >
                        R{round.round_number}: {round.points.toFixed(1)}
                      </span>
                    ))
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      <WelcomeSlideshow
        open={welcomeOpen}
        onComplete={() => {
          localStorage.setItem(welcomeKey, "1");
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
        onSave={async () => {
          if (!token || !favoriteTeamId) return;
          setFavoriteError(null);
          try {
            await updateFavoriteTeam(token, favoriteTeamId);
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
