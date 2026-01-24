"use client";

import { useEffect, useState } from "react";

import AuthPanel from "@/components/AuthPanel";
import { createTeam, getTeam } from "@/lib/api";
import { useFantasyStore } from "@/lib/store";

export default function SettingsPage() {
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const userEmail = useFantasyStore((state) => state.userEmail);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);
  const setMarketDraftSquad = useFantasyStore((state) => state.setMarketDraftSquad);
  const setMarketDraftBackup = useFantasyStore((state) => state.setMarketDraftBackup);
  const setMarketDraftLoaded = useFantasyStore((state) => state.setMarketDraftLoaded);
  const [teamName, setTeamName] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("fantasy_token");
    if (!token && stored) {
      setToken(stored);
    }
  }, [token, setToken]);

  useEffect(() => {
    if (!token) return;
    getTeam(token)
      .then((team) => setTeamName(team.name || ""))
      .catch(() => undefined);
  }, [token]);

  const handleSave = async () => {
    if (!token) return;
    setStatus(null);
    try {
      await createTeam(token, teamName);
      setStatus("ok");
    } catch {
      setStatus("error");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("fantasy_token");
    setToken(null);
    setUserEmail(null);
    setMarketDraftSquad([]);
    setMarketDraftBackup([]);
    setMarketDraftLoaded(false);
  };

  if (!token) return <AuthPanel />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Ajustes</h1>
        <p className="text-sm text-muted">Personaliza tu equipo</p>
      </div>

      <div className="glass rounded-2xl p-4">
        <p className="text-xs text-muted">Usuario</p>
        <p className="text-sm text-ink">{userEmail || "sin email"}</p>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <label className="text-sm text-muted">Nombre del equipo</label>
        <input
          value={teamName}
          onChange={(event) => setTeamName(event.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
        />
        <button
          onClick={handleSave}
          className="w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
        >
          Guardar
        </button>
        {status === "ok" ? <p className="text-xs text-accent2">Guardado</p> : null}
        {status === "error" ? <p className="text-xs text-warning">Error</p> : null}
      </div>

      <button
        onClick={handleLogout}
        className="w-full rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
      >
        Logout
      </button>
    </div>
  );
}
