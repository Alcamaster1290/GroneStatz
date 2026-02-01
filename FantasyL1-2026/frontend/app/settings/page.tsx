"use client";

import { useEffect, useMemo, useState } from "react";

import AuthPanel from "@/components/AuthPanel";
import FavoriteTeamGate from "@/components/FavoriteTeamGate";
import TeamNameGate from "@/components/TeamNameGate";
import WelcomeSlideshow from "@/components/WelcomeSlideshow";
import { createTeam, getTeam, getTeams, updateFavoriteTeam } from "@/lib/api";
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
  const [favoriteTeamId, setFavoriteTeamId] = useState<number | null>(null);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>([]);
  const [needsTeamName, setNeedsTeamName] = useState(false);
  const [needsFavoriteTeam, setNeedsFavoriteTeam] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [teamLoaded, setTeamLoaded] = useState(false);
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
    getTeam(token)
      .then((team) => {
        setTeamName(team.name || "");
        setNeedsTeamName(!team.name?.trim());
        const favoriteId =
          typeof team.favorite_team_id === "number" ? team.favorite_team_id : null;
        setFavoriteTeamId(favoriteId);
        setNeedsFavoriteTeam(!favoriteId);
        setTeamLoaded(true);
      })
      .catch(() => {
        setNeedsTeamName(true);
        setTeamLoaded(true);
      });
  }, [token]);

  useEffect(() => {
    if (!teamLoaded) {
      setNameGateOpen(false);
      setFavoriteGateOpen(false);
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

  const welcomeKey = `fantasy_welcome_seen_${userEmail && userEmail.trim() ? userEmail.trim() : "anon"}`;

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

  useEffect(() => {
    getTeams().then(setTeams).catch(() => undefined);
  }, []);

  const teamMap = useMemo(() => {
    return new Map(
      teams.map((team) => [team.id, team.name_short || team.name_full || `Team ${team.id}`])
    );
  }, [teams]);

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
    localStorage.removeItem("fantasy_email");
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

      <div className="glass space-y-3 rounded-2xl p-4">
        <p className="text-sm text-muted">Equipo favorito</p>
        <div className="flex items-center gap-3">
          {favoriteTeamId ? (
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-surface2/60">
              <img
                src={`/images/teams/${favoriteTeamId}.png`}
                alt=""
                className="h-8 w-8 object-contain"
                onError={(event) => {
                  (event.currentTarget as HTMLImageElement).style.display = "none";
                }}
              />
            </span>
          ) : (
            <span className="h-10 w-10 rounded-full bg-surface2/60" />
          )}
          <div>
            <p className="text-sm text-ink">
              {favoriteTeamId ? teamMap.get(favoriteTeamId) || "Equipo" : "Sin equipo"}
            </p>
            <p className="text-xs text-muted">Puedes cambiarlo cuando quieras.</p>
          </div>
        </div>
        <button
          onClick={() => setFavoriteGateOpen(true)}
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-ink"
        >
          Cambiar equipo favorito
        </button>
        {favoriteError ? <p className="text-xs text-warning">{favoriteError}</p> : null}
      </div>

      <button
        onClick={handleLogout}
        className="w-full rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
      >
        Logout
      </button>

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
            if (needsTeamName) {
              setNameGateOpen(true);
            }
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
