"use client";

import { useEffect, useState } from "react";

import PlayerCard from "@/components/PlayerCard";
import { getAdminTeams } from "@/lib/api";
import { AdminTeam } from "@/lib/types";

const ADMIN_TOKEN_KEY = "fantasy_admin_token";

export default function AdminTeamsPage() {
  const [adminToken, setAdminToken] = useState("");
  const [seasonYear, setSeasonYear] = useState("");
  const [teams, setTeams] = useState<AdminTeam[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedTeamId, setExpandedTeamId] = useState<number | null>(null);

  useEffect(() => {
    const storedAdmin = localStorage.getItem(ADMIN_TOKEN_KEY);
    if (storedAdmin) {
      setAdminToken(storedAdmin);
    }
  }, []);

  const handleLoad = async () => {
    if (!adminToken) {
      setError("admin_token_required");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const data = await getAdminTeams(
        adminToken,
        seasonYear ? Number(seasonYear) : undefined
      );
      setTeams(data);
      localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted">Equipos guardados por usuario.</p>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <label className="text-xs text-muted">Admin Token</label>
        <input
          value={adminToken}
          onChange={(event) => setAdminToken(event.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
        />
        <p className="text-xs text-muted">Usa el valor de `ADMIN_TOKEN` en `FantasyL1-2026/.env`.</p>
        <label className="text-xs text-muted">Season year (opcional)</label>
        <input
          value={seasonYear}
          onChange={(event) => setSeasonYear(event.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
        />
        <button
          onClick={handleLoad}
          className="w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
        >
          Cargar equipos
        </button>
        {error ? <p className="text-xs text-warning">{error}</p> : null}
      </div>

      <div className="glass rounded-2xl p-4">
        <p className="text-xs text-muted">Equipos encontrados</p>
        <p className="text-lg font-semibold text-ink">{teams.length}</p>
      </div>

      {loading ? <p className="text-xs text-muted">Cargando...</p> : null}

      {teams.map((team) => {
        const isOpen = expandedTeamId === team.fantasy_team_id;
        return (
          <div key={team.fantasy_team_id} className="glass space-y-3 rounded-2xl p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs text-muted">Usuario</p>
                <p className="text-sm font-semibold text-ink">{team.user_email}</p>
                <p className="text-xs text-muted">Equipo</p>
                <p className="text-sm text-ink">{team.name || "Sin nombre"}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted">Presupuesto</p>
                <p className="text-sm font-semibold text-accent">
                  {team.budget_used.toFixed(1)}
                </p>
                <p className="text-xs text-muted">Restante {team.budget_left.toFixed(1)}</p>
              </div>
            </div>

            <button
              onClick={() =>
                setExpandedTeamId(isOpen ? null : team.fantasy_team_id)
              }
              className="w-full rounded-xl border border-white/10 px-4 py-2 text-sm text-ink"
            >
              {isOpen ? "Ocultar plantel" : "Ver plantel"}
            </button>

            {isOpen ? (
              team.squad.length > 0 ? (
                <div className="space-y-2">
                  {team.squad.map((player) => (
                    <PlayerCard key={player.player_id} player={player} compact />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted">Sin jugadores guardados.</p>
              )
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
