"use client";

import { useEffect, useMemo, useState } from "react";

import AuthPanel from "@/components/AuthPanel";
import FavoriteTeamGate from "@/components/FavoriteTeamGate";
import TeamNameGate from "@/components/TeamNameGate";
import WelcomeSlideshow from "@/components/WelcomeSlideshow";
import {
  createTeam,
  getNotificationDevices,
  getTeam,
  getTeams,
  registerNotificationDevice,
  unregisterNotificationDevice,
  updateFavoriteTeam
} from "@/lib/api";
import {
  getNativeDeviceId,
  isNativeMobilePlatform,
  registerNativePush
} from "@/lib/mobile/push";
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
  const [isNewTeam, setIsNewTeam] = useState(false);
  const [nameGateOpen, setNameGateOpen] = useState(false);
  const [favoriteGateOpen, setFavoriteGateOpen] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [welcomeSeen, setWelcomeSeen] = useState(false);
  const [teamNameError, setTeamNameError] = useState<string | null>(null);
  const [favoriteError, setFavoriteError] = useState<string | null>(null);
  const [pushLoading, setPushLoading] = useState(false);
  const [pushMessage, setPushMessage] = useState<string | null>(null);
  const [pushError, setPushError] = useState<string | null>(null);
  const [pushEnabled, setPushEnabled] = useState(false);

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

  const welcomeKey = `fantasy_welcome_seen_${userEmail && userEmail.trim() ? userEmail.trim() : "anon"}`;
  const appChannel = process.env.NEXT_PUBLIC_APP_CHANNEL || "web";
  const appVersion = process.env.NEXT_PUBLIC_APP_VERSION || "dev";
  const pushSectionVisible = isNativeMobilePlatform() && appChannel !== "web";

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

  useEffect(() => {
    getTeams().then(setTeams).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!token || !isNativeMobilePlatform()) {
      setPushEnabled(false);
      return;
    }
    let cancelled = false;
    const loadPushStatus = async () => {
      try {
        const [devices, deviceId] = await Promise.all([
          getNotificationDevices(token),
          getNativeDeviceId()
        ]);
        if (cancelled) return;
        if (!deviceId) {
          setPushEnabled(false);
          return;
        }
        const current = devices.find((item) => item.device_id === deviceId);
        setPushEnabled(Boolean(current?.is_active));
      } catch {
        if (!cancelled) {
          setPushEnabled(false);
        }
      }
    };
    loadPushStatus().catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [token]);

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
    } catch (err) {
      if (String(err).includes("offline_write_blocked")) {
        setStatus("offline");
      } else {
        setStatus("error");
      }
    }
  };

  const handleEnablePush = async () => {
    if (!token) return;
    if (!isNativeMobilePlatform()) {
      setPushError("Disponible solo en app movil instalada.");
      return;
    }
    setPushLoading(true);
    setPushMessage(null);
    setPushError(null);
    try {
      const native = await registerNativePush();
      await registerNotificationDevice(token, {
        token: native.token,
        platform: native.platform,
        device_id: native.device_id,
        timezone: native.timezone,
        app_channel: appChannel,
        app_version: appVersion
      });
      setPushEnabled(true);
      setPushMessage("Notificaciones activadas.");
    } catch (err) {
      setPushError(String(err));
    } finally {
      setPushLoading(false);
    }
  };

  const handleDisablePush = async () => {
    if (!token) return;
    if (!isNativeMobilePlatform()) {
      setPushError("Disponible solo en app movil instalada.");
      return;
    }
    setPushLoading(true);
    setPushMessage(null);
    setPushError(null);
    try {
      const deviceId = await getNativeDeviceId();
      if (!deviceId) {
        throw new Error("device_id_unavailable");
      }
      await unregisterNotificationDevice(token, deviceId);
      setPushEnabled(false);
      setPushMessage("Notificaciones desactivadas.");
    } catch (err) {
      setPushError(String(err));
    } finally {
      setPushLoading(false);
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
  const nativePushAvailable = isNativeMobilePlatform();

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
        {status === "offline" ? <p className="text-xs text-warning">Sin conexion, solo lectura.</p> : null}
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

      {pushSectionVisible ? (
        <div className="glass space-y-3 rounded-2xl p-4">
          <p className="text-sm text-muted">Notificaciones moviles</p>
          <p className="text-xs text-muted">
            {nativePushAvailable
              ? "Recibe alertas 24h antes de cerrar cada ronda."
              : "Activalas desde la app movil instalada (Capacitor)."}
          </p>
          <button
            onClick={pushEnabled ? handleDisablePush : handleEnablePush}
            disabled={pushLoading || !nativePushAvailable}
            className={
              "w-full rounded-xl px-4 py-2 text-sm font-semibold " +
              (pushEnabled ? "border border-white/10 text-ink" : "bg-accent text-black")
            }
          >
            {pushLoading
              ? "Procesando..."
              : pushEnabled
                ? "Desactivar notificaciones"
                : "Activar notificaciones"}
          </button>
          {pushMessage ? <p className="text-xs text-accent2">{pushMessage}</p> : null}
          {pushError ? <p className="text-xs text-warning">{pushError}</p> : null}
        </div>
      ) : null}

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
