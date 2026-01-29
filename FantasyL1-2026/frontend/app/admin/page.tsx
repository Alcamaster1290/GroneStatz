"use client";

import { useEffect, useMemo, useState } from "react";

import PlayerCard from "@/components/PlayerCard";
import {
  createAdminFixture,
  closeAdminRound,
  deleteAdminUser,
  getAdminLeagues,
  getAdminLogs,
  getAdminPriceMovements,
  getAdminRounds,
  getAdminFixtures,
  getAdminTeams,
  rebuildAdminCatalog,
  getCatalogPlayers,
  getTeams,
  getAdminPlayers,
  openAdminRound,
  updateAdminFixture,
  upsertAdminPlayerStats,
  updateAdminPlayerInjury
} from "@/lib/api";
import {
  AdminActionLog,
  AdminLeague,
  AdminRound,
  AdminFixture,
  AdminPriceMovement,
  AdminTeam,
  FixtureStatus
} from "@/lib/types";
import type { AdminPlayerListItem } from "@/lib/api";

const ADMIN_TOKEN_KEY = "fantasy_admin_token";

export default function AdminTeamsPage() {
  const [adminToken, setAdminToken] = useState("");
  const [seasonYear, setSeasonYear] = useState("");
  const [teams, setTeams] = useState<AdminTeam[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedTeamId, setExpandedTeamId] = useState<number | null>(null);
  const [fixtureRound, setFixtureRound] = useState("");
  const [fixtures, setFixtures] = useState<AdminFixture[]>([]);
  const [fixtureLoading, setFixtureLoading] = useState(false);
  const [fixtureError, setFixtureError] = useState<string | null>(null);
  const [teamsCatalog, setTeamsCatalog] = useState<
    { id: number; name_short?: string | null; name_full?: string | null }[]
  >([]);

  const [newFixture, setNewFixture] = useState({
    round_number: "",
    match_id: "",
    home_team_id: "",
    away_team_id: "",
    kickoff_at: "",
    stadium: "",
    city: "",
    status: "Programado" as FixtureStatus,
    home_score: "",
    away_score: ""
  });

  const [fixtureEdits, setFixtureEdits] = useState<
    Record<
      number,
      {
        round_number: string;
        match_id: string;
        home_team_id: string;
        away_team_id: string;
        kickoff_at: string;
        stadium: string;
        city: string;
        status: string;
        home_score: string;
        away_score: string;
      }
    >
  >({});

  const statusOptions: FixtureStatus[] = ["Programado", "Postergado", "Finalizado"];

  const [statsRound, setStatsRound] = useState("");
  const [statsInput, setStatsInput] = useState("");
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsMessage, setStatsMessage] = useState<string | null>(null);
  const [injuryPlayerId, setInjuryPlayerId] = useState("");
  const [injuryStatus, setInjuryStatus] = useState(false);
  const [injuryLoading, setInjuryLoading] = useState(false);
  const [injuryMessage, setInjuryMessage] = useState<string | null>(null);
  const [adminPlayers, setAdminPlayers] = useState<AdminPlayerListItem[]>([]);
  const [adminPlayersLoading, setAdminPlayersLoading] = useState(false);
  const [adminPlayersError, setAdminPlayersError] = useState<string | null>(null);
  const [adminPlayersSummary, setAdminPlayersSummary] = useState({
    total: 0,
    injured: 0,
    unselected: 0
  });
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogMessage, setCatalogMessage] = useState<string | null>(null);
  const [playerSearch, setPlayerSearch] = useState("");
  const [playerResults, setPlayerResults] = useState<
    { player_id: number; name: string; short_name?: string | null; is_injured?: boolean }[]
  >([]);
  const [playerSearchLoading, setPlayerSearchLoading] = useState(false);
  const [priceRound, setPriceRound] = useState("");
  const [priceMovements, setPriceMovements] = useState<AdminPriceMovement[]>([]);
  const [priceLoading, setPriceLoading] = useState(false);
  const [priceError, setPriceError] = useState<string | null>(null);
  const [rounds, setRounds] = useState<AdminRound[]>([]);
  const [roundsLoading, setRoundsLoading] = useState(false);
  const [roundsError, setRoundsError] = useState<string | null>(null);
  const [closeRoundNumber, setCloseRoundNumber] = useState("");
  const [openRoundNumber, setOpenRoundNumber] = useState("");
  const [roundActionMessage, setRoundActionMessage] = useState<string | null>(null);
  const [leagues, setLeagues] = useState<AdminLeague[]>([]);
  const [leaguesLoading, setLeaguesLoading] = useState(false);
  const [leaguesError, setLeaguesError] = useState<string | null>(null);
  const [logs, setLogs] = useState<AdminActionLog[]>([]);
  const [logCategory, setLogCategory] = useState("league");
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);

  useEffect(() => {
    const storedAdmin = localStorage.getItem(ADMIN_TOKEN_KEY);
    if (storedAdmin) {
      setAdminToken(storedAdmin);
    }
  }, []);

  useEffect(() => {
    if (!adminToken) return;
    setAdminPlayersLoading(true);
    setAdminPlayersError(null);
    getAdminPlayers(adminToken)
      .then((data) => {
        setAdminPlayers(data.items || []);
        setAdminPlayersSummary({
          total: data.total || 0,
          injured: data.injured || 0,
          unselected: data.unselected || 0
        });
      })
      .catch((err) => setAdminPlayersError(String(err)))
      .finally(() => setAdminPlayersLoading(false));
  }, [adminToken]);

  useEffect(() => {
    getTeams().then(setTeamsCatalog).catch(() => undefined);
  }, []);

  const teamMap = useMemo(() => {
    return new Map(
      teamsCatalog.map((team) => [
        team.id,
        team.name_short || team.name_full || `Team ${team.id}`
      ])
    );
  }, [teamsCatalog]);

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

  const toDraft = (fixture: AdminFixture) => ({
    round_number: String(fixture.round_number),
    match_id: String(fixture.match_id),
    home_team_id: fixture.home_team_id != null ? String(fixture.home_team_id) : "",
    away_team_id: fixture.away_team_id != null ? String(fixture.away_team_id) : "",
    kickoff_at: fixture.kickoff_at
      ? new Date(fixture.kickoff_at).toISOString().slice(0, 16)
      : "",
    stadium: fixture.stadium ?? "",
    city: fixture.city ?? "",
    status: fixture.status,
    home_score: fixture.home_score != null ? String(fixture.home_score) : "",
    away_score: fixture.away_score != null ? String(fixture.away_score) : ""
  });

  const parseNumber = (value: string) => {
    if (!value.trim()) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const handleLoadFixtures = async (roundOverride?: string) => {
    if (!adminToken) {
      setFixtureError("admin_token_required");
      return;
    }
    setFixtureError(null);
    setFixtureLoading(true);
    try {
      const roundValue = roundOverride ?? fixtureRound;
      const data = await getAdminFixtures(
        adminToken,
        roundValue ? Number(roundValue) : undefined
      );
      setFixtures(data);
      const draftMap: Record<number, ReturnType<typeof toDraft>> = {};
      data.forEach((fixture) => {
        draftMap[fixture.id] = toDraft(fixture);
      });
      setFixtureEdits(draftMap);
      localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
    } catch (err) {
      setFixtureError(String(err));
    } finally {
      setFixtureLoading(false);
    }
  };

  const handleCreateFixture = async () => {
    if (!adminToken) {
      setFixtureError("admin_token_required");
      return;
    }
    if (!newFixture.round_number || !newFixture.match_id) {
      setFixtureError("round_and_match_required");
      return;
    }
    setFixtureError(null);
    setFixtureLoading(true);
    try {
      await createAdminFixture(adminToken, {
        round_number: Number(newFixture.round_number),
        match_id: Number(newFixture.match_id),
        home_team_id: parseNumber(newFixture.home_team_id),
        away_team_id: parseNumber(newFixture.away_team_id),
        kickoff_at: newFixture.kickoff_at || null,
        stadium: newFixture.stadium || null,
        city: newFixture.city || null,
        status: newFixture.status,
        home_score: parseNumber(newFixture.home_score),
        away_score: parseNumber(newFixture.away_score)
      });
      setNewFixture((prev) => ({
        ...prev,
        match_id: "",
        home_team_id: "",
        away_team_id: "",
        kickoff_at: "",
        stadium: "",
        city: "",
        home_score: "",
        away_score: ""
      }));
      setFixtureRound(newFixture.round_number);
      await handleLoadFixtures(newFixture.round_number);
    } catch (err) {
      setFixtureError(String(err));
    } finally {
      setFixtureLoading(false);
    }
  };

  const handleUpdateFixture = async (fixtureId: number) => {
    if (!adminToken) {
      setFixtureError("admin_token_required");
      return;
    }
    const draft = fixtureEdits[fixtureId];
    if (!draft || !draft.round_number || !draft.match_id) {
      setFixtureError("round_and_match_required");
      return;
    }
    setFixtureError(null);
    setFixtureLoading(true);
    try {
      await updateAdminFixture(adminToken, fixtureId, {
        round_number: Number(draft.round_number),
        match_id: Number(draft.match_id),
        home_team_id: parseNumber(draft.home_team_id),
        away_team_id: parseNumber(draft.away_team_id),
        kickoff_at: draft.kickoff_at || null,
        stadium: draft.stadium || null,
        city: draft.city || null,
        status: draft.status,
        home_score: parseNumber(draft.home_score),
        away_score: parseNumber(draft.away_score)
      });
      await handleLoadFixtures();
    } catch (err) {
      setFixtureError(String(err));
    } finally {
      setFixtureLoading(false);
    }
  };

  const updateFixtureDraft = (
    fixtureId: number,
    field:
      | "round_number"
      | "match_id"
      | "home_team_id"
      | "away_team_id"
      | "kickoff_at"
      | "stadium"
      | "city"
      | "status"
      | "home_score"
      | "away_score",
    value: string
  ) => {
    setFixtureEdits((prev) => {
      const fallback = fixtures.find((fixture) => fixture.id === fixtureId);
      const base = prev[fixtureId] || (fallback ? toDraft(fallback) : undefined);
      if (!base) return prev;
      return {
        ...prev,
        [fixtureId]: {
          ...base,
          [field]: value
        }
      };
    });
  };

  const handleUploadStats = async () => {
    if (!adminToken) {
      setStatsMessage("admin_token_required");
      return;
    }
    if (!statsRound.trim()) {
      setStatsMessage("round_required");
      return;
    }
    const roundNumber = Number(statsRound);
    if (!Number.isFinite(roundNumber) || roundNumber < 1) {
      setStatsMessage("round_invalid");
      return;
    }

    const lines = statsInput
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    if (lines.length === 0) {
      setStatsMessage("no_stats");
      return;
    }

    const items: {
      player_id: number;
      match_id: number;
      goals?: number;
      assists?: number;
      minutesplayed?: number;
      saves?: number;
      fouls?: number;
      yellow_cards?: number;
      red_cards?: number;
      clean_sheet?: number;
      goals_conceded?: number;
    }[] = [];

    for (const line of lines) {
      const parts = line.split(/[,\t;]/).map((part) => part.trim());
      if (parts.length < 2) continue;
      const playerId = Number(parts[0]);
      const matchId = Number(parts[1]);
      if (!Number.isFinite(playerId) || !Number.isFinite(matchId)) {
        continue;
      }
      const goals = parts[2] ? Number(parts[2]) : 0;
      const assists = parts[3] ? Number(parts[3]) : 0;
      const minutesplayed = parts[4] ? Number(parts[4]) : 0;
      const saves = parts[5] ? Number(parts[5]) : 0;
      const fouls = parts[6] ? Number(parts[6]) : 0;
      const yellow_cards = parts[7] ? Number(parts[7]) : 0;
      const red_cards = parts[8] ? Number(parts[8]) : 0;
      const clean_sheet = parts[9] ? Number(parts[9]) : undefined;
      const goals_conceded = parts[10] ? Number(parts[10]) : undefined;
      items.push({
        player_id: playerId,
        match_id: matchId,
        goals: Number.isFinite(goals) ? goals : 0,
        assists: Number.isFinite(assists) ? assists : 0,
        minutesplayed: Number.isFinite(minutesplayed) ? minutesplayed : 0,
        saves: Number.isFinite(saves) ? saves : 0,
        fouls: Number.isFinite(fouls) ? fouls : 0,
        yellow_cards: Number.isFinite(yellow_cards) ? yellow_cards : 0,
        red_cards: Number.isFinite(red_cards) ? red_cards : 0,
        clean_sheet: Number.isFinite(clean_sheet as number)
          ? (clean_sheet as number)
          : undefined,
        goals_conceded: Number.isFinite(goals_conceded as number)
          ? (goals_conceded as number)
          : undefined
      });
    }

    if (items.length === 0) {
      setStatsMessage("no_valid_rows");
      return;
    }

    setStatsLoading(true);
    setStatsMessage(null);
    try {
      const result = await upsertAdminPlayerStats(adminToken, {
        round_number: roundNumber,
        items
      });
      setStatsMessage(`ok_${result.count}`);
    } catch (err) {
      setStatsMessage(String(err));
    } finally {
      setStatsLoading(false);
    }
  };

  const handleUpdateInjury = async () => {
    if (!adminToken) {
      setInjuryMessage("admin_token_required");
      return;
    }
    if (!injuryPlayerId.trim()) {
      setInjuryMessage("player_id_required");
      return;
    }
    const playerId = Number(injuryPlayerId);
    if (!Number.isFinite(playerId) || playerId < 1) {
      setInjuryMessage("player_id_invalid");
      return;
    }
    setInjuryMessage(null);
    setInjuryLoading(true);
    try {
      await updateAdminPlayerInjury(adminToken, playerId, injuryStatus);
      const refreshed = await getAdminPlayers(adminToken);
      setAdminPlayers(refreshed.items || []);
      setAdminPlayersSummary({
        total: refreshed.total || 0,
        injured: refreshed.injured || 0,
        unselected: refreshed.unselected || 0
      });
      setInjuryMessage(injuryStatus ? "lesionado_ok" : "recuperado_ok");
    } catch (err) {
      setInjuryMessage(String(err));
    } finally {
      setInjuryLoading(false);
    }
  };

  const handleSearchPlayers = async () => {
    const query = playerSearch.trim();
    if (!query) {
      setPlayerResults([]);
      return;
    }
    setPlayerSearchLoading(true);
    try {
      const results = await getCatalogPlayers({ q: query, limit: 50, offset: 0 });
      setPlayerResults(
        results.map((player) => ({
          player_id: player.player_id,
          name: player.name,
          short_name: player.short_name || player.shortName || null,
          is_injured: player.is_injured
        }))
      );
    } catch (err) {
      setPlayerResults([]);
      setInjuryMessage(String(err));
    } finally {
      setPlayerSearchLoading(false);
    }
  };

  const handleLoadPriceMovements = async () => {
    if (!adminToken) {
      setPriceError("admin_token_required");
      return;
    }
    setPriceError(null);
    setPriceLoading(true);
    try {
      const roundValue = priceRound ? Number(priceRound) : undefined;
      const data = await getAdminPriceMovements(adminToken, roundValue);
      setPriceMovements(data);
      localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
    } catch (err) {
      setPriceError(String(err));
    } finally {
      setPriceLoading(false);
    }
  };

  const handleRebuildCatalog = async () => {
    if (!adminToken) {
      setCatalogMessage("admin_token_required");
      return;
    }
    setCatalogLoading(true);
    setCatalogMessage(null);
    try {
      await rebuildAdminCatalog(adminToken);
      const refreshed = await getAdminPlayers(adminToken);
      setAdminPlayers(refreshed.items || []);
      setAdminPlayersSummary({
        total: refreshed.total || 0,
        injured: refreshed.injured || 0,
        unselected: refreshed.unselected || 0
      });
      setCatalogMessage("catalog_ok");
    } catch (err) {
      setCatalogMessage(String(err));
    } finally {
      setCatalogLoading(false);
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!adminToken) {
      setError("admin_token_required");
      return;
    }
    if (!confirm("Seguro que deseas borrar este usuario y su equipo?")) {
      return;
    }
    setError(null);
    try {
      await deleteAdminUser(adminToken, userId);
      setTeams((prev) => prev.filter((team) => team.user_id !== userId));
    } catch (err) {
      setError(String(err));
    }
  };

  const handleLoadRounds = async () => {
    if (!adminToken) {
      setRoundsError("admin_token_required");
      return;
    }
    setRoundsError(null);
    setRoundsLoading(true);
    try {
      const data = await getAdminRounds(adminToken);
      setRounds(data);
      localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
    } catch (err) {
      setRoundsError(String(err));
    } finally {
      setRoundsLoading(false);
    }
  };

  const handleCloseRound = async () => {
    if (!adminToken) {
      setRoundActionMessage("admin_token_required");
      return;
    }
    if (!closeRoundNumber.trim()) {
      setRoundActionMessage("round_required");
      return;
    }
    const roundNumber = Number(closeRoundNumber);
    if (!Number.isFinite(roundNumber) || roundNumber < 1) {
      setRoundActionMessage("round_invalid");
      return;
    }
    setRoundActionMessage(null);
    try {
      await closeAdminRound(adminToken, roundNumber);
      await handleLoadRounds();
      setRoundActionMessage("round_closed");
    } catch (err) {
      setRoundActionMessage(String(err));
    }
  };

  const handleOpenRound = async () => {
    if (!adminToken) {
      setRoundActionMessage("admin_token_required");
      return;
    }
    if (!openRoundNumber.trim()) {
      setRoundActionMessage("round_required");
      return;
    }
    const roundNumber = Number(openRoundNumber);
    if (!Number.isFinite(roundNumber) || roundNumber < 1) {
      setRoundActionMessage("round_invalid");
      return;
    }
    setRoundActionMessage(null);
    try {
      await openAdminRound(adminToken, roundNumber);
      await handleLoadRounds();
      setRoundActionMessage("round_opened");
    } catch (err) {
      setRoundActionMessage(String(err));
    }
  };

  const handleLoadLeagues = async () => {
    if (!adminToken) {
      setLeaguesError("admin_token_required");
      return;
    }
    setLeaguesError(null);
    setLeaguesLoading(true);
    try {
      const data = await getAdminLeagues(adminToken);
      setLeagues(data);
      localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
    } catch (err) {
      setLeaguesError(String(err));
    } finally {
      setLeaguesLoading(false);
    }
  };

  const handleLoadLogs = async () => {
    if (!adminToken) {
      setLogsError("admin_token_required");
      return;
    }
    setLogsError(null);
    setLogsLoading(true);
    try {
      const data = await getAdminLogs(adminToken, {
        category: logCategory || undefined,
        limit: 200
      });
      setLogs(data);
      localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
    } catch (err) {
      setLogsError(String(err));
    } finally {
      setLogsLoading(false);
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

      <div className="space-y-2 pt-2">
        <h2 className="text-lg font-semibold">Cierre de rondas</h2>
        <p className="text-sm text-muted">Marca rondas como cerradas.</p>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-wrap gap-2">
            <input
              type="number"
              value={openRoundNumber}
              onChange={(event) => setOpenRoundNumber(event.target.value)}
              placeholder="Ronda a abrir"
              className="flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
            <button
              onClick={handleOpenRound}
              className="rounded-xl border border-white/10 px-4 py-2 text-sm text-ink"
            >
              Activar ronda
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            <input
              type="number"
              value={closeRoundNumber}
              onChange={(event) => setCloseRoundNumber(event.target.value)}
              placeholder="Ronda a cerrar"
              className="flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
            <button
              onClick={handleCloseRound}
              className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
            >
              Cerrar ronda
            </button>
          </div>
        </div>
        <button
          onClick={handleLoadRounds}
          className="w-full rounded-xl border border-white/10 px-4 py-2 text-sm text-ink"
        >
          Ver rondas
        </button>
        {roundActionMessage ? <p className="text-xs text-muted">{roundActionMessage}</p> : null}
        {roundsError ? <p className="text-xs text-warning">{roundsError}</p> : null}
        {roundsLoading ? <p className="text-xs text-muted">Cargando...</p> : null}
        {rounds.length > 0 ? (
          <div className="space-y-2">
            {rounds.map((round) => (
              <div
                key={round.id}
                className="flex items-center justify-between rounded-2xl border border-white/10 px-3 py-2 text-xs"
              >
                <div>
                  <p className="text-ink">Ronda {round.round_number}</p>
                  <p className="text-muted">
                    {round.is_closed ? "Cerrada" : "Abierta"}
                  </p>
                </div>
                <span
                  className={
                    round.is_closed ? "text-emerald-300" : "text-amber-300"
                  }
                >
                  {round.is_closed ? "OK" : "Pendiente"}
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      <div className="space-y-2 pt-2">
        <h2 className="text-lg font-semibold">Ligas privadas</h2>
        <p className="text-sm text-muted">Ver ligas y miembros.</p>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <button
          onClick={handleLoadLeagues}
          className="w-full rounded-xl border border-white/10 px-4 py-2 text-sm text-ink"
        >
          Cargar ligas
        </button>
        {leaguesError ? <p className="text-xs text-warning">{leaguesError}</p> : null}
        {leaguesLoading ? <p className="text-xs text-muted">Cargando...</p> : null}
        {leagues.length === 0 && !leaguesLoading ? (
          <p className="text-xs text-muted">Sin ligas registradas.</p>
        ) : (
          <div className="space-y-3">
            {leagues.map((league) => (
              <div key={league.id} className="rounded-2xl border border-white/10 p-3">
                <div className="flex items-center justify-between text-sm">
                  <div>
                    <p className="font-semibold text-ink">{league.name}</p>
                    <p className="text-xs text-muted">Codigo: {league.code}</p>
                  </div>
                  <span className="text-xs text-muted">
                    Admin #{league.owner_fantasy_team_id}
                  </span>
                </div>
                <div className="mt-2 space-y-1">
                  {league.members.map((member) => (
                    <div
                      key={member.fantasy_team_id}
                      className="flex items-center justify-between text-xs text-muted"
                    >
                      <span>{member.team_name || `Equipo ${member.fantasy_team_id}`}</span>
                      <span>{member.user_email}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-2 pt-2">
        <h2 className="text-lg font-semibold">Logs (ligas / stats)</h2>
        <p className="text-sm text-muted">Acciones recientes del sistema.</p>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <div className="flex flex-wrap gap-2">
          <select
            value={logCategory}
            onChange={(event) => setLogCategory(event.target.value)}
            className="flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
          >
            <option value="">Todos</option>
            <option value="league">Ligas</option>
            <option value="stats">Stats</option>
            <option value="round">Rondas</option>
            <option value="admin">Admin</option>
          </select>
          <button
            onClick={handleLoadLogs}
            className="rounded-xl border border-white/10 px-4 py-2 text-sm text-ink"
          >
            Cargar logs
          </button>
        </div>
        {logsError ? <p className="text-xs text-warning">{logsError}</p> : null}
        {logsLoading ? <p className="text-xs text-muted">Cargando...</p> : null}
        {logs.length === 0 && !logsLoading ? (
          <p className="text-xs text-muted">Sin logs.</p>
        ) : (
          <div className="space-y-2">
            {logs.map((log) => (
              <div key={log.id} className="rounded-2xl border border-white/10 px-3 py-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-muted">{log.category}</span>
                  <span className="text-muted">{new Date(log.created_at).toLocaleString()}</span>
                </div>
                <p className="text-ink">{log.action}</p>
                <p className="text-muted">
                  {log.actor_email ? `Actor: ${log.actor_email}` : ""}
                  {log.league_id ? ` | Liga ${log.league_id}` : ""}
                  {log.fantasy_team_id ? ` | Team ${log.fantasy_team_id}` : ""}
                </p>
                {log.details ? <p className="text-muted">{log.details}</p> : null}
              </div>
            ))}
          </div>
        )}
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
            <button
              onClick={() => handleDeleteUser(team.user_id)}
              className="w-full rounded-xl border border-red-400/40 px-4 py-2 text-sm text-red-200"
            >
              Eliminar usuario y equipo
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

      <div className="space-y-2 pt-2">
        <h2 className="text-lg font-semibold">Rondas y partidos</h2>
        <p className="text-sm text-muted">
          Inserta partidos por ronda y actualiza resultados/estado.
        </p>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <p className="text-sm font-semibold text-ink">Nuevo partido</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-xs text-muted">Ronda</label>
            <input
              type="number"
              value={newFixture.round_number}
              onChange={(event) =>
                setNewFixture((prev) => ({ ...prev, round_number: event.target.value }))
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Match ID</label>
            <input
              type="number"
              value={newFixture.match_id}
              onChange={(event) =>
                setNewFixture((prev) => ({ ...prev, match_id: event.target.value }))
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Home team</label>
            <select
              value={newFixture.home_team_id}
              onChange={(event) =>
                setNewFixture((prev) => ({ ...prev, home_team_id: event.target.value }))
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            >
              <option value="">Selecciona equipo</option>
              {teamsCatalog.map((team) => (
                <option key={team.id} value={team.id}>
                  {teamMap.get(team.id) || `Team ${team.id}`}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Away team</label>
            <select
              value={newFixture.away_team_id}
              onChange={(event) =>
                setNewFixture((prev) => ({ ...prev, away_team_id: event.target.value }))
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            >
              <option value="">Selecciona equipo</option>
              {teamsCatalog.map((team) => (
                <option key={team.id} value={team.id}>
                  {teamMap.get(team.id) || `Team ${team.id}`}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Kickoff</label>
            <input
              type="datetime-local"
              value={newFixture.kickoff_at}
              onChange={(event) =>
                setNewFixture((prev) => ({ ...prev, kickoff_at: event.target.value }))
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Estado</label>
            <select
              value={newFixture.status}
              onChange={(event) =>
                setNewFixture((prev) => ({
                  ...prev,
                  status: event.target.value as FixtureStatus
                }))
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            >
              {statusOptions.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Estadio</label>
            <input
              value={newFixture.stadium}
              onChange={(event) =>
                setNewFixture((prev) => ({ ...prev, stadium: event.target.value }))
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Ciudad</label>
            <input
              value={newFixture.city}
              onChange={(event) =>
                setNewFixture((prev) => ({ ...prev, city: event.target.value }))
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Home score</label>
            <input
              type="number"
              value={newFixture.home_score}
              onChange={(event) =>
                setNewFixture((prev) => ({ ...prev, home_score: event.target.value }))
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">Away score</label>
            <input
              type="number"
              value={newFixture.away_score}
              onChange={(event) =>
                setNewFixture((prev) => ({ ...prev, away_score: event.target.value }))
              }
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
          </div>
        </div>
        <button
          onClick={handleCreateFixture}
          className="w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
        >
          Guardar partido
        </button>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <p className="text-sm font-semibold text-ink">Partidos por ronda</p>
        <div className="flex flex-wrap gap-2">
          <input
            type="number"
            value={fixtureRound}
            onChange={(event) => setFixtureRound(event.target.value)}
            placeholder="Ronda (opcional)"
            className="flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
          />
          <button
            onClick={() => handleLoadFixtures()}
            className="rounded-xl border border-white/10 px-4 py-2 text-sm text-ink"
          >
            Cargar partidos
          </button>
        </div>
        {fixtureError ? <p className="text-xs text-warning">{fixtureError}</p> : null}
        {fixtureLoading ? <p className="text-xs text-muted">Cargando...</p> : null}

        {fixtures.length === 0 ? (
          <p className="text-xs text-muted">Sin partidos cargados.</p>
        ) : (
          fixtures.map((fixture) => {
            const draft = fixtureEdits[fixture.id] || toDraft(fixture);
            return (
              <div key={fixture.id} className="space-y-3 rounded-2xl border border-white/10 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-xs text-muted">Match #{fixture.match_id}</p>
                    <p className="text-sm text-ink">
                      {teamMap.get(fixture.home_team_id ?? 0) || "Home"} vs{" "}
                      {teamMap.get(fixture.away_team_id ?? 0) || "Away"}
                    </p>
                  </div>
                  <span className="text-xs text-muted">{fixture.status}</span>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs text-muted">Ronda</label>
                    <input
                      type="number"
                      value={draft.round_number}
                      onChange={(event) =>
                        updateFixtureDraft(fixture.id, "round_number", event.target.value)
                      }
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted">Match ID</label>
                    <input
                      type="number"
                      value={draft.match_id}
                      onChange={(event) =>
                        updateFixtureDraft(fixture.id, "match_id", event.target.value)
                      }
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted">Home team</label>
                    <select
                      value={draft.home_team_id}
                      onChange={(event) =>
                        updateFixtureDraft(fixture.id, "home_team_id", event.target.value)
                      }
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                    >
                      <option value="">Selecciona equipo</option>
                      {teamsCatalog.map((team) => (
                        <option key={team.id} value={team.id}>
                          {teamMap.get(team.id) || `Team ${team.id}`}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted">Away team</label>
                    <select
                      value={draft.away_team_id}
                      onChange={(event) =>
                        updateFixtureDraft(fixture.id, "away_team_id", event.target.value)
                      }
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                    >
                      <option value="">Selecciona equipo</option>
                      {teamsCatalog.map((team) => (
                        <option key={team.id} value={team.id}>
                          {teamMap.get(team.id) || `Team ${team.id}`}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted">Kickoff</label>
                    <input
                      type="datetime-local"
                      value={draft.kickoff_at}
                      onChange={(event) =>
                        updateFixtureDraft(fixture.id, "kickoff_at", event.target.value)
                      }
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted">Estado</label>
                    <select
                      value={draft.status}
                      onChange={(event) =>
                        updateFixtureDraft(fixture.id, "status", event.target.value)
                      }
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                    >
                      {statusOptions.map((status) => (
                        <option key={status} value={status}>
                          {status}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted">Estadio</label>
                    <input
                      value={draft.stadium}
                      onChange={(event) =>
                        updateFixtureDraft(fixture.id, "stadium", event.target.value)
                      }
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted">Ciudad</label>
                    <input
                      value={draft.city}
                      onChange={(event) =>
                        updateFixtureDraft(fixture.id, "city", event.target.value)
                      }
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted">Home score</label>
                    <input
                      type="number"
                      value={draft.home_score}
                      onChange={(event) =>
                        updateFixtureDraft(fixture.id, "home_score", event.target.value)
                      }
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted">Away score</label>
                    <input
                      type="number"
                      value={draft.away_score}
                      onChange={(event) =>
                        updateFixtureDraft(fixture.id, "away_score", event.target.value)
                      }
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
                    />
                  </div>
                </div>

                <button
                  onClick={() => handleUpdateFixture(fixture.id)}
                  className="w-full rounded-xl bg-white/10 px-4 py-2 text-sm text-ink"
                >
                  Guardar cambios
                </button>
              </div>
            );
          })
        )}
      </div>

        <div className="space-y-2 pt-2">
          <h2 className="text-lg font-semibold">Stats por jornada</h2>
          <p className="text-sm text-muted">
            Basado en player_match.parquet. Formato: player_id, match_id, goles, asistencias,
            minutos, saves, fouls, amarillas, rojas, clean_sheet, goles_recibidos.
          </p>
        </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <div className="space-y-1">
          <label className="text-xs text-muted">Ronda</label>
          <input
            type="number"
            value={statsRound}
            onChange={(event) => setStatsRound(event.target.value)}
            className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted">Datos</label>
          <textarea
            value={statsInput}
            onChange={(event) => setStatsInput(event.target.value)}
            rows={6}
            className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-xs"
            placeholder="player_id,match_id,goals,assists,minutes,saves,fouls,yellow,red,clean_sheet,goals_conceded"
            />
        </div>
        <button
          onClick={handleUploadStats}
          className="w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
          disabled={statsLoading}
        >
          {statsLoading ? "Cargando..." : "Cargar stats"}
        </button>
        {statsMessage ? <p className="text-xs text-muted">{statsMessage}</p> : null}
      </div>

      <div className="space-y-2 pt-2">
        <h2 className="text-lg font-semibold">Estado de lesiones</h2>
        <p className="text-sm text-muted">Marca jugadores lesionados desde admin.</p>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <div className="rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-muted">
          <div className="flex flex-wrap items-center gap-2">
            <span>Total: <span className="font-semibold text-ink">{adminPlayersSummary.total}</span></span>
            <span>Lesionados: <span className="font-semibold text-ink">{adminPlayersSummary.injured}</span></span>
            <span>Sin elegir: <span className="font-semibold text-ink">{adminPlayersSummary.unselected}</span></span>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2">
          <span className="text-xs text-muted">Catalogo de jugadores</span>
          <button
            onClick={handleRebuildCatalog}
            disabled={catalogLoading}
            className="rounded-xl border border-white/10 px-3 py-1 text-xs text-ink"
          >
            {catalogLoading ? "Actualizando..." : "Actualizar catalogo"}
          </button>
        </div>
        {catalogMessage ? <p className="text-xs text-muted">{catalogMessage}</p> : null}
        {adminPlayersError ? (
          <p className="text-xs text-warning">No se pudo cargar la lista de jugadores: {adminPlayersError}</p>
        ) : null}
        <div className="space-y-1">
          <label className="text-xs text-muted">Listado de jugadores</label>
          <select
            value={injuryPlayerId}
            onChange={(event) => {
              const nextId = event.target.value;
              setInjuryPlayerId(nextId);
              const selected = adminPlayers.find(
                (player) => String(player.player_id) === nextId
              );
              if (selected) {
                setInjuryStatus(Boolean(selected.is_injured));
              }
            }}
            className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
          >
            <option value="">Selecciona un jugador</option>
            {adminPlayers.map((player) => (
              <option key={player.player_id} value={String(player.player_id)}>
                {player.short_name || player.name} (#{player.player_id})
              </option>
            ))}
          </select>
          {adminPlayersLoading ? (
            <p className="text-[11px] text-muted">Cargando jugadores...</p>
          ) : null}
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted">Buscar jugador</label>
          <div className="flex gap-2">
            <input
              value={playerSearch}
              onChange={(event) => setPlayerSearch(event.target.value)}
              placeholder="Nombre o apodo"
              className="flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
            />
            <button
              onClick={handleSearchPlayers}
              className="rounded-xl border border-white/10 px-4 py-2 text-sm text-ink"
              disabled={playerSearchLoading}
            >
              {playerSearchLoading ? "Buscando..." : "Buscar"}
            </button>
          </div>
        </div>
        {playerResults.length ? (
          <div className="max-h-48 space-y-2 overflow-y-auto rounded-xl border border-white/10 bg-black/20 p-2 text-xs">
            {playerResults.map((player) => (
              <button
                key={player.player_id}
                onClick={() => {
                  setInjuryPlayerId(String(player.player_id));
                  setInjuryStatus(Boolean(player.is_injured));
                }}
                className="flex w-full items-center justify-between rounded-lg px-2 py-1 text-left hover:bg-white/5"
              >
                <span className="text-ink">
                  {player.short_name || player.name} (#{player.player_id})
                </span>
                {player.is_injured ? (
                  <span className="text-red-200">Lesionado</span>
                ) : (
                  <span className="text-muted">OK</span>
                )}
              </button>
            ))}
          </div>
        ) : null}
        <div className="space-y-1">
          <label className="text-xs text-muted">Player ID</label>
          <input
            type="number"
            value={injuryPlayerId}
            onChange={(event) => setInjuryPlayerId(event.target.value)}
            className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={injuryStatus}
            onChange={(event) => setInjuryStatus(event.target.checked)}
            className="h-4 w-4 rounded border border-white/10 bg-black/40"
          />
          Lesionado
        </label>
        <button
          onClick={handleUpdateInjury}
          className="w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
          disabled={injuryLoading}
        >
          {injuryLoading ? "Guardando..." : "Guardar estado"}
        </button>
        {injuryMessage ? <p className="text-xs text-muted">{injuryMessage}</p> : null}
      </div>

      <div className="space-y-2 pt-2">
        <h2 className="text-lg font-semibold">Movimientos de precio</h2>
        <p className="text-sm text-muted">
          Variacion por ronda segun puntos calculados.
        </p>
      </div>

      <div className="glass space-y-3 rounded-2xl p-4">
        <div className="flex flex-wrap gap-2">
          <input
            type="number"
            value={priceRound}
            onChange={(event) => setPriceRound(event.target.value)}
            placeholder="Ronda (opcional)"
            className="flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm"
          />
          <button
            onClick={handleLoadPriceMovements}
            className="rounded-xl border border-white/10 px-4 py-2 text-sm text-ink"
          >
            Cargar movimientos
          </button>
        </div>
        {priceError ? <p className="text-xs text-warning">{priceError}</p> : null}
        {priceLoading ? <p className="text-xs text-muted">Cargando...</p> : null}
        {priceMovements.length === 0 && !priceLoading ? (
          <p className="text-xs text-muted">Sin movimientos registrados.</p>
        ) : (
          <div className="space-y-2">
            {priceMovements.map((movement) => (
              <div
                key={`${movement.round_number}-${movement.player_id}`}
                className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 px-3 py-2"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-surface2/60">
                    <img
                      src={`/images/players/${movement.player_id}.png`}
                      alt=""
                      className="h-full w-full object-cover"
                      onError={(event) => {
                        (event.currentTarget as HTMLImageElement).style.display = "none";
                      }}
                    />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-ink">{movement.name}</p>
                    <div className="flex items-center gap-2 text-[11px] text-muted">
                      <span>{movement.position}</span>
                      <span>Pts {movement.points.toFixed(1)}</span>
                    </div>
                  </div>
                </div>
                <div className="text-right text-xs">
                  <p className="text-muted">Precio</p>
                  <p className="text-sm font-semibold text-accent">
                    {movement.price_current.toFixed(1)}
                  </p>
                  <p
                    className={
                      movement.delta >= 0
                        ? "text-emerald-300"
                        : "text-red-300"
                    }
                  >
                    {movement.delta >= 0 ? "+" : ""}
                    {movement.delta.toFixed(1)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
