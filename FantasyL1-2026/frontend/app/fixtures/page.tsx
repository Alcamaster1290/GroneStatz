"use client";

import { useEffect, useMemo, useState } from "react";

import AuthPanel from "@/components/AuthPanel";
import { getFixtures, getTeams } from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import { Fixture } from "@/lib/types";

export default function FixturesPage() {
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);

  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem("fantasy_token");
    if (!token && stored) {
      setToken(stored);
    }
  }, [token, setToken]);

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

  if (!token) return <AuthPanel />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Fixtures</h1>
        <p className="text-sm text-muted">Calendario por rondas</p>
      </div>

      {Object.entries(rounds)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([roundNumber, matches]) => (
          <div key={roundNumber} className="space-y-2">
            <h2 className="text-lg font-semibold">Ronda {roundNumber}</h2>
            {matches.map((match) => (
              <div key={match.id} className="glass flex items-center justify-between rounded-2xl p-4">
                <div>
                  <p className="text-sm text-ink">
                    {teamMap.get(match.home_team_id ?? 0) || "Home"} vs {" "}
                    {teamMap.get(match.away_team_id ?? 0) || "Away"}
                  </p>
                  <p className="text-xs text-muted">
                    {match.kickoff_at ? new Date(match.kickoff_at).toLocaleString() : "TBD"}
                  </p>
                </div>
                <span className="text-xs text-muted">#{match.match_id}</span>
              </div>
            ))}
          </div>
        ))}
    </div>
  );
}
