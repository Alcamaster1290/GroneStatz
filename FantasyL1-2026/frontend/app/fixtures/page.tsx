"use client";

import { useEffect, useMemo, useState } from "react";

import AuthPanel from "@/components/AuthPanel";
import TeamNameGate from "@/components/TeamNameGate";
import WelcomeSlideshow from "@/components/WelcomeSlideshow";
import { createTeam, getFixtures, getTeam, getTeams } from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import { Fixture } from "@/lib/types";

function TeamLogo({ teamId }: { teamId: number | null | undefined }) {
  const [hidden, setHidden] = useState(false);
  if (!teamId || hidden) {
    return <div className="h-6 w-6 rounded-full bg-surface2/60" />;
  }
  return (
    <div className="h-6 w-6 rounded-full bg-surface2/60 p-1">
      <img
        src={`/images/teams/${teamId}.png`}
        alt=""
        className="h-full w-full object-contain"
        onError={() => setHidden(true)}
      />
    </div>
  );
}

function formatKickoff(raw: string | null | undefined): string {
  if (!raw) return "TBD";
  const value = String(raw).trim();
  if (!value) return "TBD";
  const parts = value.split("T");
  const timePart = (parts.length > 1 ? parts[1] : value).split(" ")[0];
  if (timePart.length >= 5) {
    return timePart.slice(0, 5);
  }
  return timePart || "TBD";
}

function formatDateLabel(dateKey: string): string {
  if (!dateKey || dateKey === "TBD") return "Por confirmar";
  const [year, month, day] = dateKey.split("-").map((part) => Number(part));
  if (!year || !month || !day) return dateKey;
  const date = new Date(year, month - 1, day);
  const weekdays = [
    "Domingo",
    "Lunes",
    "Martes",
    "Miercoles",
    "Jueves",
    "Viernes",
    "Sabado"
  ];
  const months = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre"
  ];
  const weekday = weekdays[date.getDay()];
  const monthLabel = months[month - 1];
  if (!weekday || !monthLabel) return dateKey;
  return `${weekday} ${day} de ${monthLabel}`;
}

export default function FixturesPage() {
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);
  const userEmail = useFantasyStore((state) => state.userEmail);

  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>([]);
  const [teamName, setTeamName] = useState("");
  const [needsTeamName, setNeedsTeamName] = useState(false);
  const [teamLoaded, setTeamLoaded] = useState(false);
  const [nameGateOpen, setNameGateOpen] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [welcomeSeen, setWelcomeSeen] = useState(false);
  const [teamNameError, setTeamNameError] = useState<string | null>(null);

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

  useEffect(() => {
    getFixtures().then(setFixtures).catch(() => undefined);
    getTeams().then(setTeams).catch(() => undefined);
  }, []);

  const teamMap = useMemo(() => {
    return new Map(
      teams.map((team) => [team.id, team.name_short || team.name_full || `Team ${team.id}`])
    );
  }, [teams]);

  const rounds = useMemo(() => {
    return fixtures.reduce((acc, fixture) => {
      const key = fixture.round_number;
      if (!acc[key]) acc[key] = [];
      acc[key].push(fixture);
      return acc;
    }, {} as Record<number, Fixture[]>);
  }, [fixtures]);

  const roundsByDate = useMemo(() => {
    const toKey = (value: string | null | undefined) => {
      if (!value) return "TBD";
      const raw = String(value).trim();
      if (!raw) return "TBD";
      return raw.split("T")[0].split(" ")[0] || "TBD";
    };
    return fixtures.reduce((acc, fixture) => {
      const key = toKey(fixture.kickoff_at);
      if (!acc[key]) acc[key] = [];
      acc[key].push(fixture);
      return acc;
    }, {} as Record<string, Fixture[]>);
  }, [fixtures]);

  if (!token) return <AuthPanel />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Fixtures</h1>
        <p className="text-sm text-muted">Calendario por rondas</p>
      </div>

      {Object.entries(roundsByDate)
        .sort(([a], [b]) => {
          if (a === "TBD") return 1;
          if (b === "TBD") return -1;
          return a.localeCompare(b);
        })
        .map(([dateKey, matches]) => (
          <div key={dateKey} className="space-y-2">
            <h2 className="text-lg font-semibold">{formatDateLabel(dateKey)}</h2>
            {matches
              .slice()
              .sort((a, b) => formatKickoff(a.kickoff_at).localeCompare(formatKickoff(b.kickoff_at)))
              .map((match) => (
                <div key={match.id} className="glass flex items-center justify-between rounded-2xl p-4">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2 text-sm text-ink">
                      <TeamLogo teamId={match.home_team_id} />
                      <span>{teamMap.get(match.home_team_id ?? 0) || "Home"}</span>
                      <span className="text-xs text-muted">vs</span>
                      <TeamLogo teamId={match.away_team_id} />
                      <span>{teamMap.get(match.away_team_id ?? 0) || "Away"}</span>
                    </div>
                    <p className="text-xs text-muted">
                      {formatKickoff(match.kickoff_at)} - {match.status}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-ink">
                      {match.home_score != null && match.away_score != null
                        ? `${match.home_score} - ${match.away_score}`
                        : ""}
                    </p>
                  </div>
                </div>
              ))}
          </div>
        ))}

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
