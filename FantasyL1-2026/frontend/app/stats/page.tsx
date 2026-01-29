"use client";

import { useEffect, useMemo, useState } from "react";

import AuthPanel from "@/components/AuthPanel";
import TeamNameGate from "@/components/TeamNameGate";
import WelcomeSlideshow from "@/components/WelcomeSlideshow";
import { createTeam, getPlayerStats, getTeam, getTeams } from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import { PlayerStatsEntry, Position } from "@/lib/types";

const positionLabels: Record<string, string> = {
  G: "Arquero",
  D: "Defensa",
  M: "Mediocampo",
  F: "Delantero"
};

export default function StatsPage() {
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const userEmail = useFantasyStore((state) => state.userEmail);

  const [teamName, setTeamName] = useState("");
  const [teamLoaded, setTeamLoaded] = useState(false);
  const [nameGateOpen, setNameGateOpen] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [welcomeSeen, setWelcomeSeen] = useState(false);
  const [teamNameError, setTeamNameError] = useState<string | null>(null);

  const [players, setPlayers] = useState<PlayerStatsEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>([]);

  const [query, setQuery] = useState("");
  const [position, setPosition] = useState<Position | "">("");
  const [teamId, setTeamId] = useState("");
  const [maxPrice, setMaxPrice] = useState("");

  useEffect(() => {
    const stored = localStorage.getItem("fantasy_token");
    if (!token && stored) {
      setToken(stored);
    }
  }, [token, setToken]);

  useEffect(() => {
    if (!token) return;
    getTeam(token)
      .then((team) => {
        setTeamName(team.name || "");
        setTeamLoaded(true);
      })
      .catch(() => setTeamLoaded(true));
  }, [token]);

  useEffect(() => {
    getTeams().then(setTeams).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (teamLoaded && !teamName.trim()) {
      setNameGateOpen(!welcomeOpen);
    } else {
      setNameGateOpen(false);
    }
  }, [teamLoaded, teamName, welcomeOpen]);

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
    if (teamLoaded && !teamName.trim() && !welcomeSeen) {
      setWelcomeOpen(true);
    } else {
      setWelcomeOpen(false);
    }
  }, [teamLoaded, teamName, welcomeSeen]);

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPlayerStats({
        q: query.trim() || undefined,
        position: position || undefined,
        team_id: teamId ? Number(teamId) : undefined,
        max_price: maxPrice ? Number(maxPrice) : undefined,
        limit: 200,
        offset: 0
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
              {teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name_short || team.name_full || `Equipo ${team.id}`}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Precio maximo</label>
            <input
              type="number"
              step="0.1"
              value={maxPrice}
              onChange={(event) => setMaxPrice(event.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
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
        {players.length === 0 && !loading ? (
          <p className="text-xs text-muted">Sin jugadores para mostrar.</p>
        ) : (
          players.map((player) => {
            const percent = Math.min(100, Math.max(0, player.selected_percent));
            const isKeeper = player.position === "G";
            return (
              <div
                key={player.player_id}
                className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-black/20 px-3 py-3"
              >
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
                      <span>Am {player.yellow_cards}</span>
                      <span>Ro {player.red_cards}</span>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2 text-right">
                  <p className="text-sm font-semibold text-accent">
                    {player.price_current.toFixed(1)}
                  </p>
                  <p className="text-xs font-semibold text-indigo-300">
                    {percent.toFixed(1)}%
                  </p>
                  <div className="h-1 w-16 rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-yellow-400"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
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
            setNameGateOpen(false);
          } catch {
            setTeamNameError("No se pudo guardar el nombre.");
          }
        }}
      />
    </div>
  );
}
