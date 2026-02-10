"use client";

import { useEffect, useMemo, useState } from "react";

import { getCatalogPlayers, getTeams } from "@/lib/api";

type TeamOption = {
  id: number;
  name: string;
};

type FavoriteTeamGateProps = {
  open: boolean;
  selectedTeamId: number | null;
  onSelect: (teamId: number) => void;
  onSave: () => void;
  onSkip?: () => void;
  onClose?: () => void;
  error?: string | null;
};

export default function FavoriteTeamGate({
  open,
  selectedTeamId,
  onSelect,
  onSave,
  onSkip,
  onClose,
  error: externalError
}: FavoriteTeamGateProps) {
  const [teams, setTeams] = useState<TeamOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let active = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [teamsResponse, playersPage0] = await Promise.all([
          getTeams(),
          getCatalogPlayers({ limit: 1000, offset: 0 })
        ]);
        const allPlayers = [...playersPage0];
        let offset = 1000;
        while (playersPage0.length === 1000) {
          const next = await getCatalogPlayers({ limit: 1000, offset });
          if (!next.length) break;
          allPlayers.push(...next);
          offset += 1000;
          if (next.length < 1000) break;
        }
        const counts = new Map<number, number>();
        allPlayers.forEach((player) => {
          counts.set(player.team_id, (counts.get(player.team_id) || 0) + 1);
        });
        const options = teamsResponse
          .filter((team) => (counts.get(team.id) || 0) > 1)
          .map((team) => ({
            id: team.id,
            name: team.name_short || team.name_full || `Equipo ${team.id}`
          }))
          .sort((a, b) => a.name.localeCompare(b.name));
        if (active) {
          setTeams(options);
        }
      } catch (err) {
        if (active) setError(String(err));
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [open]);

  const filteredTeams = useMemo(() => {
    if (!query.trim()) return teams;
    const q = query.trim().toLowerCase();
    return teams.filter((team) => team.name.toLowerCase().includes(q));
  }, [teams, query]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 px-4 py-6">
      <div className="glass w-full max-w-md space-y-4 rounded-3xl border border-white/10 p-5">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-ink">Elige tu equipo favorito</h2>
            <p className="text-xs text-muted">
              Selecciona el club que quieres seguir en la Liga 1 2026.
            </p>
          </div>
          {onClose ? (
            <button onClick={onClose} className="text-xs text-muted">
              X
            </button>
          ) : null}
        </div>

        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar equipo"
          className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
        />

        <div className="max-h-60 space-y-2 overflow-y-auto rounded-2xl border border-white/10 p-2">
          {loading ? (
            <div className="px-3 py-2 text-xs text-muted">Cargando equipos...</div>
          ) : null}
          {!loading && filteredTeams.length === 0 ? (
            <div className="px-3 py-2 text-xs text-muted">No hay equipos disponibles.</div>
          ) : null}
          {filteredTeams.map((team) => {
            const isSelected = selectedTeamId === team.id;
            return (
              <button
                key={team.id}
                type="button"
                onClick={() => onSelect(team.id)}
                className={
                  "flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left text-sm transition " +
                  (isSelected
                    ? "border-accent bg-accent/20 text-ink"
                    : "border-white/10 text-muted hover:border-white/20")
                }
              >
                <div className="h-9 w-9 rounded-full bg-surface2/60 p-1">
                  <img
                    src={`/images/teams/${team.id}.png`}
                    alt=""
                    className="h-full w-full object-contain"
                  />
                </div>
                <span className="flex-1">{team.name}</span>
                {isSelected ? (
                  <span className="text-xs font-semibold text-accent">Seleccionado</span>
                ) : null}
              </button>
            );
          })}
        </div>

        {externalError ? <p className="text-xs text-warning">{externalError}</p> : null}
        {!externalError && error ? <p className="text-xs text-warning">{error}</p> : null}

        <div className="flex gap-2">
          <button
            onClick={() => {
              if (onSkip) onSkip();
            }}
            className="w-1/3 rounded-xl border border-white/15 px-3 py-2 text-sm text-ink"
          >
            Elegir luego
          </button>
          <button
            onClick={onSave}
            disabled={!selectedTeamId}
            className="w-2/3 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black disabled:opacity-40"
          >
            Guardar equipo favorito
          </button>
        </div>
      </div>
    </div>
  );
}
