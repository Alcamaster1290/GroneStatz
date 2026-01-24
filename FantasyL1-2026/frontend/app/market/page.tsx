"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useMemo, useRef, useState } from "react";

import AuthPanel from "@/components/AuthPanel";
import BottomSheet from "@/components/BottomSheet";
import MarketFilters from "@/components/MarketFilters";
import PlayerCard from "@/components/PlayerCard";
import { createTeam, getCatalogPlayers, getHealth, getTeam, getTeams, updateSquad } from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import { Player } from "@/lib/types";
import { validateSquad } from "@/lib/validation";

function PlayerFace({ playerId }: { playerId: number }) {
  const sources = [
    `/images/players/${playerId}.png`,
    `/images/players/${playerId}.jpg`,
    `/images/players/${playerId}.jpeg`,
    `/images/players/${playerId}.webp`
  ];
  const [srcIndex, setSrcIndex] = useState(0);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    setSrcIndex(0);
    setHidden(false);
  }, [playerId]);

  const handleError = () => {
    setSrcIndex((prev) => {
      const next = prev + 1;
      if (next >= sources.length) {
        setHidden(true);
        return prev;
      }
      return next;
    });
  };

  if (hidden) {
    return (
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-surface2/80 ring-1 ring-white/10" />
    );
  }

  return (
    <div className="h-12 w-12 overflow-hidden rounded-full ring-1 ring-white/10">
      <img
        src={sources[srcIndex]}
        alt=""
        className="h-full w-full object-cover"
        onError={handleError}
      />
    </div>
  );
}

function TeamBadge({ teamId }: { teamId: number }) {
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;
  return (
    <span className="absolute -bottom-1 -right-1 flex h-[20px] w-[20px] items-center justify-center rounded-full">
      <img
        src={`/images/teams/${teamId}.png`}
        alt=""
        className="h-full w-full object-contain"
        onError={() => setHidden(true)}
      />
    </span>
  );
}

function PitchPlayer({
  player,
  onSelect,
  onRemove,
  isSelected
}: {
  player: Player;
  onSelect: (player: Player) => void;
  onRemove: (playerId: number) => void;
  isSelected: boolean;
}) {
  const displayName = player.short_name || player.shortName || player.name;

  return (
    <div
      onClick={() => onSelect(player)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(player);
        }
      }}
      role="button"
      tabIndex={0}
      className={
        "flex flex-col items-center gap-1 rounded-2xl px-2 py-2 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent " +
        (isSelected ? " bg-white/5" : "")
      }
    >
      <div className="relative">
        <PlayerFace playerId={player.player_id} />
        <TeamBadge teamId={player.team_id} />
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onRemove(player.player_id);
          }}
          className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-black/70 text-[10px] text-ink ring-1 ring-white/20"
          aria-label={`Quitar ${displayName}`}
        >
          X
        </button>
      </div>
      <div className="flex flex-col items-center">
        <span className="max-w-[72px] truncate text-[10px] text-ink">{displayName}</span>
        <span className="text-[9px] text-muted">{player.price_current.toFixed(1)}</span>
      </div>
    </div>
  );
}

function PitchRow({
  label,
  players,
  onSelect,
  onRemove,
  selectedOutId
}: {
  label: string;
  players: Player[];
  onSelect: (player: Player) => void;
  onRemove: (playerId: number) => void;
  selectedOutId: number | null;
}) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">{label}</p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {players.length > 0 ? (
          players.map((player) => (
            <PitchPlayer
              key={player.player_id}
              player={player}
              onSelect={onSelect}
              onRemove={onRemove}
              isSelected={selectedOutId === player.player_id}
            />
          ))
        ) : (
          <div className="h-12 w-12 rounded-full bg-surface2/30" />
        )}
      </div>
    </div>
  );
}

export default function MarketPage() {
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const squad = useFantasyStore((state) => state.squad);
  const setSquad = useFantasyStore((state) => state.setSquad);
  const draftSquadState = useFantasyStore((state) => state.marketDraftSquad);
  const setDraftSquad = useFantasyStore((state) => state.setMarketDraftSquad);
  const setDraftBackup = useFantasyStore((state) => state.setMarketDraftBackup);
  const draftLoaded = useFantasyStore((state) => state.marketDraftLoaded);
  const setDraftLoaded = useFantasyStore((state) => state.setMarketDraftLoaded);
  const draftSquad = Array.isArray(draftSquadState) ? draftSquadState : [];

  const [players, setPlayers] = useState<Player[]>([]);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>([]);
  const filters = useFantasyStore((state) => state.marketFilters);
  const setFilters = useFantasyStore((state) => state.setMarketFilters);
  const [outPlayerId, setOutPlayerId] = useState<number | null>(null);
  const [inPlayerId, setInPlayerId] = useState<number | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [loadingPlayers, setLoadingPlayers] = useState(false);
  const [errorPopup, setErrorPopup] = useState<string[] | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [teamName, setTeamName] = useState("");
  const [teamNameError, setTeamNameError] = useState<string | null>(null);
  const [appEnv, setAppEnv] = useState<string>("local");
  const [teamLoaded, setTeamLoaded] = useState(false);
  const [nameGateOpen, setNameGateOpen] = useState(false);

  const parentRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const stored = localStorage.getItem("fantasy_token");
    if (!token && stored) {
      setToken(stored);
    }
  }, [token, setToken]);

  useEffect(() => {
    if (!Array.isArray(draftSquadState)) {
      setDraftSquad([]);
    }
  }, [draftSquadState, setDraftSquad]);

  useEffect(() => {
    if (!token) return;
    const load = async () => {
      const team = await getTeam(token);
      setSquad(team.squad || []);
      if (!draftLoaded) {
        if (draftSquad.length === 0) {
          setDraftSquad(team.squad || []);
        }
        setDraftLoaded(true);
      }
      if (team.name) {
        setTeamName(team.name);
      }
      setTeamLoaded(true);
    };
    load().catch(() => undefined);
  }, [token, setSquad, setDraftSquad, draftSquad.length, draftLoaded, setDraftLoaded]);

  useEffect(() => {
    getHealth()
      .then((data) => setAppEnv(data.env || "local"))
      .catch(() => setAppEnv("local"));
  }, []);

  useEffect(() => {
    const requiresTeamName = ["test", "prod"].includes(appEnv);
    if (requiresTeamName && teamLoaded && !teamName.trim()) {
      setNameGateOpen(true);
    } else {
      setNameGateOpen(false);
    }
  }, [appEnv, teamLoaded, teamName]);

  useEffect(() => {
    getTeams().then(setTeams).catch(() => undefined);
  }, []);

  useEffect(() => {
    const fetchPlayers = async () => {
      setFetchError(null);
      setLoadingPlayers(true);
      const limit = 200;
      const maxPages = 10;
      const all: Player[] = [];

      for (let page = 0; page < maxPages; page += 1) {
        const result = await getCatalogPlayers({
          position: filters.position || undefined,
          team_id: filters.teamId ? Number(filters.teamId) : undefined,
          min_price: filters.minPrice ? Number(filters.minPrice) : undefined,
          max_price: filters.maxPrice ? Number(filters.maxPrice) : undefined,
          q: filters.query || undefined,
          limit,
          offset: page * limit
        });
        all.push(...result);
        if (result.length < limit) break;
      }

      const sorted = [...all].sort((a, b) => b.price_current - a.price_current);
      setPlayers(sorted);
      setLoadingPlayers(false);
    };

    const timeout = setTimeout(() => {
      fetchPlayers().catch((err) => {
        setPlayers([]);
        setFetchError(String(err));
        setLoadingPlayers(false);
      });
    }, 250);

    return () => clearTimeout(timeout);
  }, [filters]);

  const rowVirtualizer = useVirtualizer({
    count: players.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 6
  });

  const outPlayer = useMemo(
    () => draftSquad.find((player) => player.player_id === outPlayerId),
    [draftSquad, outPlayerId]
  );

  const inPlayer = useMemo(
    () => players.find((player) => player.player_id === inPlayerId),
    [players, inPlayerId]
  );

  const playersByPosition = useMemo(() => {
    return {
      G: draftSquad.filter((player) => player.position === "G"),
      D: draftSquad.filter((player) => player.position === "D"),
      M: draftSquad.filter((player) => player.position === "M"),
      F: draftSquad.filter((player) => player.position === "F")
    };
  }, [draftSquad]);

  const draftBudget = useMemo(
    () => draftSquad.reduce((sum, player) => sum + player.price_current, 0),
    [draftSquad]
  );
  const budgetLeft = 100 - draftBudget;

  const handleConfirmPlayer = () => {
    if (nameGateOpen) return;
    if (!inPlayerId) return;
    const incoming = players.find((player) => player.player_id === inPlayerId);
    if (!incoming) return;

    setActionError(null);

    const alreadyInTeam = draftSquad.some((player) => player.player_id === incoming.player_id);
    if (!outPlayerId && draftSquad.length >= 15 && !alreadyInTeam) {
      setActionError("equipo_lleno");
      return;
    }

    setDraftSquad((prev) => {
      let next = prev;
      if (outPlayerId) {
        next = prev.filter((player) => player.player_id !== outPlayerId);
      }
      if (!next.some((player) => player.player_id === incoming.player_id)) {
        next = [...next, incoming];
      }
      return next;
    });

    setSheetOpen(false);
    setInPlayerId(null);
    setOutPlayerId(null);
  };

  const handleGenerateRandomTeam = () => {
    if (nameGateOpen) return;
    setSaveMessage(null);
    setErrorPopup(null);

    if (players.length === 0) {
      setErrorPopup([fetchError || "no_players_available"]);
      return;
    }

    const pickRandom = (items: Player[], count: number) => {
      if (items.length < count) return null;
      const shuffled = [...items];
      for (let i = shuffled.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
      }
      return shuffled.slice(0, count);
    };

    const gk = pickRandom(players.filter((player) => player.position === "G"), 2);
    const defenders = pickRandom(players.filter((player) => player.position === "D"), 5);
    const mids = pickRandom(players.filter((player) => player.position === "M"), 5);
    const forwards = pickRandom(players.filter((player) => player.position === "F"), 3);

    const missing: string[] = [];
    if (!gk) missing.push("not_enough_goalkeepers");
    if (!defenders) missing.push("not_enough_defenders");
    if (!mids) missing.push("not_enough_midfielders");
    if (!forwards) missing.push("not_enough_forwards");

    if (missing.length > 0) {
      setErrorPopup(missing);
      return;
    }

    setDraftSquad([...(gk || []), ...(defenders || []), ...(mids || []), ...(forwards || [])]);
    setOutPlayerId(null);
    setInPlayerId(null);
    setSheetOpen(false);
  };

  const handleRemoveFromDraft = (playerId: number) => {
    if (nameGateOpen) return;
    setDraftSquad((prev) => prev.filter((player) => player.player_id !== playerId));
    if (outPlayerId === playerId) {
      setOutPlayerId(null);
    }
  };

  const handleClearTeam = () => {
    if (nameGateOpen) return;
    setDraftBackup(draftSquad);
    setDraftSquad([]);
    setOutPlayerId(null);
    setInPlayerId(null);
    setSheetOpen(false);
    setErrorPopup(null);
    setSaveMessage(null);
  };

  const handleSaveTeam = () => {
    if (nameGateOpen) return;
    if (!token) return;
    setErrorPopup(null);
    setSaveMessage(null);
    setTeamNameError(null);
    setConfirmOpen(true);
  };

  const handleConfirmSaveTeam = async () => {
    if (nameGateOpen) return;
    if (!token) return;
    const trimmedName = teamName.trim();
    if (!trimmedName) {
      setTeamNameError("Nombre requerido.");
      return;
    }
    setErrorPopup(null);
    setSaveMessage(null);
    setSaving(true);
    setConfirmOpen(false);
    const validationErrors = validateSquad(draftSquad);
    if (validationErrors.length > 0) {
      setErrorPopup(validationErrors);
      setSaving(false);
      return;
    }
    try {
      await createTeam(token, trimmedName);
      await updateSquad(
        token,
        draftSquad.map((player) => player.player_id)
      );
      const team = await getTeam(token);
      setSquad(team.squad || []);
      setDraftSquad(team.squad || []);
      setSaveMessage("Equipo guardado");
    } catch (err) {
      const message = String(err);
      setErrorPopup([
        message.includes("network_error")
          ? "No se puede conectar con el backend. Verifica que el servidor este activo."
          : message
      ]);
    } finally {
      setSaving(false);
    }
  };

  if (!token) return <AuthPanel />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Mercado</h1>
        <p className="text-sm text-muted">
          Elige 15 jugadores de la Liga 1 con un presupuesto de 100 M.
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="rounded-full border border-white/10 px-3 py-1 text-muted">
            Max 3 jugadores del mismo club
          </span>
        </div>
      </div>

      <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-emerald-900/40 via-emerald-950/40 to-black/30 p-4">
          <div className="pointer-events-none absolute inset-4 rounded-2xl border border-white/10" />
          <div className="pointer-events-none absolute left-4 right-4 top-1/2 h-px bg-white/10" />
          <div className="pointer-events-none absolute left-1/2 top-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/10" />
          <div className="relative z-10 flex min-h-[520px] flex-col justify-between gap-6 py-3">
            <PitchRow
              label="Ataque"
              players={playersByPosition.F}
              onSelect={(player) => {
                setOutPlayerId(player.player_id);
                if (inPlayerId) setSheetOpen(true);
              }}
              onRemove={handleRemoveFromDraft}
              selectedOutId={outPlayerId}
            />
            <PitchRow
              label="Medio"
              players={playersByPosition.M}
              onSelect={(player) => {
                setOutPlayerId(player.player_id);
                if (inPlayerId) setSheetOpen(true);
              }}
              onRemove={handleRemoveFromDraft}
              selectedOutId={outPlayerId}
            />
            <PitchRow
              label="Defensa"
              players={playersByPosition.D}
              onSelect={(player) => {
                setOutPlayerId(player.player_id);
                if (inPlayerId) setSheetOpen(true);
              }}
              onRemove={handleRemoveFromDraft}
              selectedOutId={outPlayerId}
            />
            <PitchRow
              label="Arquero"
              players={playersByPosition.G}
              onSelect={(player) => {
                setOutPlayerId(player.player_id);
                if (inPlayerId) setSheetOpen(true);
              }}
              onRemove={handleRemoveFromDraft}
              selectedOutId={outPlayerId}
            />
          </div>
      </div>

        <div className="glass rounded-2xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted">Seleccionados</p>
              <p className="text-lg font-semibold text-ink">{draftSquad.length}/15</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-muted">Presupuesto</p>
              <p className="text-lg font-semibold text-accent">{draftBudget.toFixed(1)}</p>
              <p className="text-xs text-muted">Restante {budgetLeft.toFixed(1)}</p>
            </div>
          </div>
          {saveMessage ? <p className="mt-2 text-xs text-accent2">{saveMessage}</p> : null}
          <button
            onClick={handleGenerateRandomTeam}
            className="mt-3 w-full rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-ink"
          >
            Generar equipo aleatorio
          </button>
          <button
            onClick={handleSaveTeam}
            disabled={draftSquad.length !== 15 || saving}
            className={
              "mt-2 w-full rounded-xl px-4 py-2 text-sm font-semibold " +
              (draftSquad.length === 15
                ? "bg-accent text-black"
                : "border border-white/10 text-muted")
            }
          >
            Guardar Equipo
          </button>
          <button
            onClick={handleClearTeam}
            className="mt-2 w-full rounded-xl bg-red-500/80 px-4 py-2 text-sm font-semibold text-white"
          >
            Limpiar Equipo
          </button>
        </div>

        <MarketFilters teams={teams} value={filters} onChange={setFilters} />
        {fetchError ? (
          <p className="text-xs text-warning">Error cargando jugadores: {fetchError}</p>
        ) : null}
        {!fetchError && loadingPlayers ? (
          <p className="text-xs text-muted">Cargando jugadores...</p>
        ) : null}
        {!fetchError && !loadingPlayers && players.length === 0 ? (
          <p className="text-xs text-muted">Sin resultados con los filtros actuales.</p>
        ) : null}

        <div ref={parentRef} className="scrollbar-hide h-[50vh] overflow-auto">
          <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: "relative" }}>
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const player = players[virtualRow.index];
              if (!player) return null;
              return (
                <div
                  key={player.player_id}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    transform: `translateY(${virtualRow.start}px)`
                  }}
                >
                  <PlayerCard
                    player={player}
                    compact
                    onClick={() => {
                      if (nameGateOpen) return;
                      setInPlayerId(player.player_id);
                      setSheetOpen(true);
                    }}
                  />
                </div>
              );
            })}
          </div>
        </div>

      <BottomSheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Confirmar jugador">
        <div className="space-y-4">
          <div>
            <p className="text-xs uppercase text-muted">Sale</p>
            {outPlayer ? (
              <PlayerCard player={outPlayer} compact />
            ) : (
              <p className="text-xs text-muted">Sin reemplazo</p>
            )}
          </div>
          <div>
            <p className="text-xs uppercase text-muted">Entra</p>
            {inPlayer ? (
              <PlayerCard player={inPlayer} compact />
            ) : (
              <p className="text-xs text-muted">Selecciona en mercado</p>
            )}
          </div>
          {actionError ? <p className="text-xs text-warning">{actionError}</p> : null}
          <button
            onClick={handleConfirmPlayer}
            disabled={!inPlayerId}
            className={
              "w-full rounded-xl px-4 py-2 text-sm font-semibold " +
              (inPlayerId ? "bg-accent text-black" : "border border-white/10 text-muted")
            }
          >
            Confirmar en equipo
          </button>
        </div>
      </BottomSheet>

      {errorPopup ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
          <div className="glass w-full max-w-sm rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-ink">Error</p>
              <button
                onClick={() => setErrorPopup(null)}
                className="text-xs text-muted"
                aria-label="Cerrar"
              >
                X
              </button>
            </div>
            <div className="mt-3 space-y-2 text-xs text-warning">
              {errorPopup.map((error) => (
                <p key={error}>{error}</p>
              ))}
            </div>
            <button
              onClick={() => setErrorPopup(null)}
              className="mt-4 w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
            >
              Entendido
            </button>
          </div>
        </div>
      ) : null}

      {confirmOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
          <div className="glass w-full max-w-sm space-y-4 rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-ink">Confirmar guardado</p>
              <button
                onClick={() => setConfirmOpen(false)}
                className="text-xs text-muted"
                aria-label="Cerrar"
              >
                X
              </button>
            </div>
            <p className="text-xs text-muted">
              ¿Estás seguro que quieres guardar este equipo?
            </p>
            <div className="space-y-2">
              <label className="text-xs text-muted">Nombre oficial del equipo</label>
              <input
                value={teamName}
                onChange={(event) => setTeamName(event.target.value)}
                className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
              />
              {teamNameError ? (
                <p className="text-xs text-warning">Ingresa un nombre para continuar.</p>
              ) : null}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setConfirmOpen(false)}
                className="flex-1 rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirmSaveTeam}
                disabled={!teamName.trim() || saving}
                className={
                  "flex-1 rounded-xl px-4 py-2 text-sm font-semibold " +
                  (teamName.trim() ? "bg-accent text-black" : "border border-white/10 text-muted")
                }
              >
                Guardar
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {nameGateOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
          <div className="glass w-full max-w-sm space-y-4 rounded-2xl border border-white/10 p-5">
            <div>
              <p className="text-sm font-semibold text-ink">Nombre del equipo</p>
              <p className="mt-1 text-xs text-muted">
                En produccion necesitas nombrar tu equipo antes de usar el mercado.
              </p>
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted">Nombre oficial</label>
              <input
                value={teamName}
                onChange={(event) => setTeamName(event.target.value)}
                className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                placeholder="Ej: Los Grones"
              />
              {teamNameError ? (
                <p className="text-xs text-warning">{teamNameError}</p>
              ) : null}
            </div>
            <button
              onClick={async () => {
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
              className="w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
            >
              Guardar nombre
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
