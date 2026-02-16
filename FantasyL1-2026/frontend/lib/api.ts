import {
  AdminFixture,
  AdminActionLog,
  AdminLeague,
  AdminRoundLineupRecoveryResult,
  AdminRound,
  AdminRoundReminderRunResult,
  AdminRoundWindowUpdate,
  AdminPriceMovement,
  AdminRoundTopPlayer,
  AdminTeam,
  AdminTeamLineup,
  AdminPlayerInjury,
  AdminMatchPlayer,
  AdminTransfer,
  AdminTransferRestoreResult,
  AdminTransferRevertResult,
  FantasyTeam,
  Fixture,
  LineupSlot,
  LineupOut,
  League,
  Player,
  PlayerPriceHistoryPoint,
  PlayerStatsEntry,
  PublicLineup,
  PublicMarket,
  RankingResponse,
  RoundInfo,
  MatchPlayerStat,
  NotificationDevice,
  NotificationDevicePlatform,
  PlayerMatch,
  TransferCount
} from "./types";
import {
  getOfflineSnapshot,
  isCacheableGetPath,
  isOnline,
  setOfflineSnapshot
} from "./offline/cache";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

const getFallbackBase = (base: string) => {
  if (base.startsWith("/")) {
    return null;
  }
  if (base.startsWith("http://localhost:")) {
    return base.replace("http://localhost:", "http://127.0.0.1:");
  }
  if (base.startsWith("http://127.0.0.1:")) {
    return base.replace("http://127.0.0.1:", "http://localhost:");
  }
  return null;
};

function formatValidationErrors(errors: any[]): string[] {
  const messages: string[] = [];
  errors.forEach((error) => {
    const loc = Array.isArray(error.loc) ? error.loc.join(".") : "";
    const type = typeof error.type === "string" ? error.type : "";
    const hasMinLength =
      type.includes("min_length") ||
      type.includes("too_short") ||
      (error && typeof error.ctx?.min_length === "number");
    if (loc.includes("email")) {
      messages.push("email_invalid");
      return;
    }
    if (loc.includes("password")) {
      if (hasMinLength) {
        messages.push("password_min_length");
        return;
      }
      messages.push("password_invalid");
      return;
    }
    messages.push("validation_error");
  });

  return messages.length ? Array.from(new Set(messages)) : ["validation_error"];
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const isGet = method === "GET";
  const cacheableGet = isGet && isCacheableGetPath(path);
  const cacheIdentity = token ? `auth:${token.slice(-24)}` : "public";
  if (!isGet && !isOnline()) {
    throw new Error("offline_write_blocked");
  }

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const attemptFetch = (base: string) =>
    fetch(`${base}${path}`, {
      ...options,
      headers
    });

  const fallbackBases: string[] = [];
  const hostnameFallback = getFallbackBase(API_URL);
  if (hostnameFallback) fallbackBases.push(hostnameFallback);
  if (API_URL !== "/api") fallbackBases.push("/api");

  const cacheBases = [API_URL, ...fallbackBases];
  const readCachedData = (allowStale: boolean): T | null => {
    if (!cacheableGet) return null;
    for (const base of cacheBases) {
      const scopedCached = getOfflineSnapshot(`${base}${path}`, {
        allowStale,
        identity: cacheIdentity
      });
      if (scopedCached !== null) {
        return scopedCached as T;
      }
      const cached = getOfflineSnapshot(`${base}${path}`, {
        allowStale
      });
      if (cached !== null) {
        return cached as T;
      }
    }
    return null;
  };

  let res: Response | undefined;
  try {
    res = await attemptFetch(API_URL);
  } catch {
    let lastError: unknown = null;
    for (const base of fallbackBases) {
      try {
        res = await attemptFetch(base);
        lastError = null;
        break;
      } catch (err) {
        lastError = err;
      }
    }
    if (lastError || !res) {
      const cached = readCachedData(!isOnline());
      if (cached) {
        return cached;
      }
      if (!isGet && !isOnline()) {
        throw new Error("offline_write_blocked");
      }
      throw new Error("network_error");
    }
  }
  if (!res) {
    const cached = readCachedData(!isOnline());
    if (cached) {
      return cached;
    }
    throw new Error("network_error");
  }

  if (!res.ok) {
    if (
      cacheableGet &&
      (res.status === 502 || res.status === 503 || res.status === 504)
    ) {
      const cached = readCachedData(!isOnline());
      if (cached) {
        return cached;
      }
    }
    const detail = await res.json().catch(() => ({}));
    if (res.status === 422 && Array.isArray(detail.detail)) {
      throw new Error(formatValidationErrors(detail.detail).join("|"));
    }
    if (Array.isArray(detail.detail) && detail.detail.length) {
      const parts = detail.detail
        .map((item: unknown) => (typeof item === "string" ? item : ""))
        .filter(Boolean);
      if (parts.length) {
        throw new Error(parts.join("|"));
      }
    }
    if (typeof detail.detail === "string" && detail.detail.trim() !== "") {
      throw new Error(detail.detail);
    }
    if (res.status === 401) {
      throw new Error("unauthorized");
    }
    if (res.status === 403) {
      throw new Error("forbidden");
    }
    if (res.status === 429) {
      throw new Error("rate_limited");
    }
    if (res.status === 404) {
      throw new Error("endpoint_not_found");
    }
    if (res.status === 502 || res.status === 503 || res.status === 504) {
      throw new Error("service_unavailable");
    }
    if (res.status >= 500) {
      throw new Error("server_error");
    }
    throw new Error("api_error");
  }
  const data = (await res.json()) as T;
  if (cacheableGet) {
    for (const base of cacheBases) {
      setOfflineSnapshot(`${base}${path}`, data);
      setOfflineSnapshot(`${base}${path}`, data, cacheIdentity);
    }
    if (res.url) {
      setOfflineSnapshot(res.url, data);
      setOfflineSnapshot(res.url, data, cacheIdentity);
    }
  }
  return data;
}

export async function register(email: string, password: string) {
  return apiFetch<{ access_token: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

export async function requestPasswordReset(email: string) {
  return apiFetch<{ ok: boolean; reset_code?: string | null }>(
    "/auth/reset/request",
    {
      method: "POST",
      body: JSON.stringify({ email })
    }
  );
}

export async function confirmPasswordReset(
  email: string,
  code: string,
  newPassword: string
) {
  return apiFetch<{ ok: boolean }>(
    "/auth/reset/confirm",
    {
      method: "POST",
      body: JSON.stringify({ email, code, new_password: newPassword })
    }
  );
}

export async function login(email: string, password: string) {
  return apiFetch<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

export async function getTeam(token: string, roundNumber?: number): Promise<FantasyTeam> {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  const team = await apiFetch<FantasyTeam>(`/fantasy/team${query}`, {}, token);
  if (!Array.isArray(team.squad)) {
    return { ...team, squad: [] };
  }
  const seen = new Set<number>();
  const squad = team.squad.filter((player) => {
    if (seen.has(player.player_id)) return false;
    seen.add(player.player_id);
    return true;
  }).slice(0, 15);
  return { ...team, squad };
}

export async function createTeam(token: string, name?: string) {
  return apiFetch(
    "/fantasy/team",
    {
      method: "POST",
      body: JSON.stringify({ name })
    },
    token
  );
}


export async function updateFavoriteTeam(token: string, teamId: number): Promise<FantasyTeam> {
  return apiFetch(
    "/fantasy/team/favorite",
    {
      method: "PUT",
      body: JSON.stringify({ team_id: teamId })
    },
    token
  );
}

export async function updateSquad(token: string, playerIds: number[]) {
  return apiFetch(
    "/fantasy/team/squad",
    {
      method: "PUT",
      body: JSON.stringify({ player_ids: playerIds })
    },
    token
  );
}

export async function getLineup(token: string, roundNumber?: number): Promise<LineupOut> {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  return apiFetch(`/fantasy/lineup${query}`, {}, token);
}

export async function saveLineup(
  token: string,
  slots: LineupSlot[],
  roundNumber?: number,
  captainPlayerId?: number | null,
  viceCaptainPlayerId?: number | null,
  reset?: boolean
): Promise<{ message?: string; errors?: string[] }> {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  return apiFetch<{ message?: string; errors?: string[] }>(
    `/fantasy/lineup${query}`,
    {
      method: "PUT",
      body: JSON.stringify({
        slots,
        captain_player_id: captainPlayerId ?? null,
        vice_captain_player_id: viceCaptainPlayerId ?? null,
        reset: Boolean(reset)
      })
    },
    token
  );
}

export async function transferPlayer(
  token: string,
  outPlayerId: number,
  inPlayerId: number,
  roundNumber?: number
) {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  return apiFetch(
    `/fantasy/transfer${query}`,
    {
      method: "POST",
      body: JSON.stringify({ out_player_id: outPlayerId, in_player_id: inPlayerId })
    },
    token
  );
}

export async function getTransferCount(token: string, roundNumber?: number): Promise<TransferCount> {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  return apiFetch(`/fantasy/transfers/count${query}`, {}, token);
}

export async function getCatalogPlayers(params: {
  position?: string;
  team_id?: number;
  q?: string;
  max_price?: number;
  min_price?: number;
  limit?: number;
  offset?: number;
}): Promise<Player[]> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.append(key, String(value));
    }
  });
  const query = search.toString();
  return apiFetch(`/catalog/players${query ? `?${query}` : ""}`);
}

export async function getPlayerPriceHistory(playerId: number): Promise<PlayerPriceHistoryPoint[]> {
  return apiFetch(`/catalog/players/${playerId}/price-history`);
}

export async function getTeams(): Promise<
  { id: number; name_short?: string; name_full?: string }[]
> {
  const teams = await apiFetch<
    { id: number; name_short?: string | null; name_full?: string | null }[]
  >("/catalog/teams");
  return teams.map((team) => ({
    ...team,
    name_short: team.name_short ?? undefined,
    name_full: team.name_full ?? undefined
  }));
}

export async function getFixtures(roundNumber?: number): Promise<Fixture[]> {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  return apiFetch(`/catalog/fixtures${query}`);
}

export async function getRounds(): Promise<RoundInfo[]> {
  return apiFetch("/catalog/rounds");
}

export async function getPlayerStats(params: {
  position?: string;
  team_id?: number;
  q?: string;
  max_price?: number;
  min_price?: number;
  limit?: number;
  offset?: number;
}): Promise<PlayerStatsEntry[]> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.append(key, String(value));
    }
  });
  const query = search.toString();
  return apiFetch(`/catalog/player-stats${query ? `?${query}` : ""}`);
}

export async function getAdminTeams(adminToken: string, seasonYear?: number): Promise<AdminTeam[]> {
  const query = seasonYear ? `?season_year=${seasonYear}` : "";
  return apiFetch(`/admin/teams${query}`, { headers: { "X-Admin-Token": adminToken } });
}

export async function getAdminLineups(
  adminToken: string,
  roundNumber?: number
): Promise<AdminTeamLineup[]> {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  return apiFetch(`/admin/lineups${query}`, {
    headers: { "X-Admin-Token": adminToken }
  });
}

export async function getAdminFixtures(
  adminToken: string,
  roundNumber?: number
): Promise<AdminFixture[]> {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  return apiFetch(`/admin/fixtures${query}`, { headers: { "X-Admin-Token": adminToken } });
}

export async function getAdminMatchStats(
  adminToken: string,
  matchId: number,
  roundNumber?: number
): Promise<AdminMatchPlayer[]> {
  const search = new URLSearchParams();
  search.append("match_id", String(matchId));
  if (roundNumber) {
    search.append("round_number", String(roundNumber));
  }
  const query = search.toString();
  return apiFetch(`/admin/match-stats?${query}`, { headers: { "X-Admin-Token": adminToken } });
}

export async function getAdminRoundTopPlayers(
  adminToken: string,
  roundNumber: number
): Promise<AdminRoundTopPlayer[]> {
  const search = new URLSearchParams({
    round_number: String(roundNumber)
  });
  return apiFetch(`/admin/rounds/top_players?${search.toString()}`, {
    headers: { "X-Admin-Token": adminToken }
  });
}

export async function getAdminPriceMovements(
  adminToken: string,
  roundNumber?: number
): Promise<AdminPriceMovement[]> {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  return apiFetch(`/admin/price-movements${query}`, {
    headers: { "X-Admin-Token": adminToken }
  });
}

export async function getAdminTransfers(
  adminToken: string,
  roundNumber?: number
): Promise<AdminTransfer[]> {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  return apiFetch(`/admin/transfers${query}`, {
    headers: { "X-Admin-Token": adminToken }
  });
}

export async function restoreAdminTransfers(
  adminToken: string,
  roundNumber?: number,
  revertSquad = true,
  reimburseFees = true,
  strict = true
): Promise<AdminTransferRestoreResult> {
  const search = new URLSearchParams();
  if (typeof roundNumber === "number" && Number.isFinite(roundNumber)) {
    search.append("round_number", String(roundNumber));
  }
  search.append("revert_squad", String(revertSquad));
  search.append("reimburse_fees", String(reimburseFees));
  search.append("strict", String(strict));
  return apiFetch(`/admin/transfers/restore?${search.toString()}`, {
    method: "POST",
    headers: { "X-Admin-Token": adminToken }
  });
}

export async function revertAdminTransfer(
  adminToken: string,
  transferId: number,
  strict = true,
  reimburseFees = true
): Promise<AdminTransferRevertResult> {
  const search = new URLSearchParams({
    strict: String(strict),
    reimburse_fees: String(reimburseFees)
  });
  return apiFetch(`/admin/transfers/${transferId}/revert?${search.toString()}`, {
    method: "POST",
    headers: { "X-Admin-Token": adminToken }
  });
}

export async function getAdminRounds(adminToken: string): Promise<AdminRound[]> {
  return apiFetch("/admin/rounds", { headers: { "X-Admin-Token": adminToken } });
}

export async function closeAdminRound(
  adminToken: string,
  roundNumber: number
): Promise<{ ok: boolean; round_number: number }> {
  return apiFetch(
    `/admin/rounds/close?round_number=${roundNumber}`,
    {
      method: "POST",
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export async function openAdminRound(
  adminToken: string,
  roundNumber: number
): Promise<{ ok: boolean; round_number: number }> {
  return apiFetch(
    `/admin/rounds/open?round_number=${roundNumber}`,
    {
      method: "POST",
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export async function recalcAdminRound(
  adminToken: string,
  roundNumber: number,
  applyPrices = false,
  writePriceHistory = false
): Promise<{ ok: boolean; round_number: number; points_rows?: number; prices_updated?: number }> {
  const search = new URLSearchParams({
    round_number: String(roundNumber),
    apply_prices: String(applyPrices),
    write_price_history: String(writePriceHistory)
  });
  return apiFetch(`/admin/recalc_round?${search.toString()}`, {
    method: "POST",
    headers: { "X-Admin-Token": adminToken }
  });
}

export async function recalcAdminMatch(
  adminToken: string,
  matchId: number,
  applyPrices = false,
  writePriceHistory = false
): Promise<{ ok: boolean; round_number: number; points_rows?: number; prices_updated?: number }> {
  const search = new URLSearchParams({
    match_id: String(matchId),
    apply_prices: String(applyPrices),
    write_price_history: String(writePriceHistory)
  });
  return apiFetch(`/admin/recalc_match?${search.toString()}`, {
    method: "POST",
    headers: { "X-Admin-Token": adminToken }
  });
}

export async function updateAdminRoundStatus(
  adminToken: string,
  roundNumber: number,
  statusValue: "Cerrada" | "Pendiente" | "Proximamente"
): Promise<{ ok: boolean; round_number: number; status: string }> {
  const search = new URLSearchParams({
    round_number: String(roundNumber),
    status: statusValue
  });
  return apiFetch(`/admin/rounds/status?${search.toString()}`, {
    method: "POST",
    headers: { "X-Admin-Token": adminToken }
  });
}

export async function updateAdminRoundWindow(
  adminToken: string,
  roundNumber: number,
  payload: AdminRoundWindowUpdate
): Promise<{ ok: boolean; round_number: number; starts_at?: string | null; ends_at?: string | null }> {
  return apiFetch(
    `/admin/rounds/${roundNumber}/window`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export async function runAdminRoundReminders(
  adminToken: string,
  dryRun = true
): Promise<AdminRoundReminderRunResult> {
  return apiFetch(
    `/admin/notifications/round-reminders/run?dry_run=${String(dryRun)}`,
    {
      method: "POST",
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export async function runAdminRoundLineupRecovery(
  adminToken: string,
  roundNumber: number,
  dryRun = true,
  recalcPlayerPoints = true
): Promise<AdminRoundLineupRecoveryResult> {
  const query = new URLSearchParams({
    dry_run: String(dryRun),
    recalc_player_points: String(recalcPlayerPoints)
  });
  return apiFetch(
    `/admin/rounds/${roundNumber}/recover-lineups?${query.toString()}`,
    {
      method: "POST",
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export async function getAdminLeagues(adminToken: string): Promise<AdminLeague[]> {
  return apiFetch("/admin/leagues", { headers: { "X-Admin-Token": adminToken } });
}

export async function getAdminLogs(
  adminToken: string,
  params?: { category?: string; limit?: number }
): Promise<AdminActionLog[]> {
  const search = new URLSearchParams();
  if (params?.category) search.append("category", params.category);
  if (params?.limit) search.append("limit", String(params.limit));
  const query = search.toString();
  return apiFetch(`/admin/logs${query ? `?${query}` : ""}`, {
    headers: { "X-Admin-Token": adminToken }
  });
}

export async function deleteAdminUser(
  adminToken: string,
  userId: number
): Promise<{ ok: boolean; user_id: number }> {
  return apiFetch(
    `/admin/users/${userId}`,
    {
      method: "DELETE",
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export async function createAdminFixture(
  adminToken: string,
  payload: {
    round_number: number;
    match_id: number;
    home_team_id?: number | null;
    away_team_id?: number | null;
    kickoff_at?: string | null;
    stadium?: string | null;
    city?: string | null;
    status?: string | null;
    home_score?: number | null;
    away_score?: number | null;
  }
): Promise<AdminFixture> {
  return apiFetch(
    "/admin/fixtures",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export async function updateAdminFixture(
  adminToken: string,
  fixtureId: number,
  payload: {
    round_number?: number;
    match_id?: number;
    home_team_id?: number | null;
    away_team_id?: number | null;
    kickoff_at?: string | null;
    stadium?: string | null;
    city?: string | null;
    status?: string | null;
    home_score?: number | null;
    away_score?: number | null;
  }
): Promise<AdminFixture> {
  return apiFetch(
    `/admin/fixtures/${fixtureId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export async function upsertAdminPlayerStats(
  adminToken: string,
  payload: {
    round_number: number;
    items: {
      player_id: number;
      match_id: number;
      minutesplayed?: number;
      goals?: number;
      assists?: number;
      saves?: number;
      fouls?: number;
      yellow_cards?: number;
      red_cards?: number;
      clean_sheet?: number;
      goals_conceded?: number;
    }[];
  }
): Promise<{ ok: boolean; count: number }> {
  return apiFetch(
    "/admin/player-stats",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export async function updateAdminPlayerInjury(
  adminToken: string,
  playerId: number,
  isInjured: boolean
): Promise<AdminPlayerInjury> {
  return apiFetch(
    `/admin/players/${playerId}/injury`,
    {
      method: "PUT",
      body: JSON.stringify({ is_injured: isInjured }),
      headers: { "X-Admin-Token": adminToken }
    }
  );
}

export async function rebuildAdminCatalog(
  adminToken: string
): Promise<{ ok: boolean }> {
  return apiFetch(
    "/admin/rebuild_catalog",
    {
      method: "POST",
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export type AdminPlayerListItem = {
  player_id: number;
  name: string;
  short_name?: string | null;
  position: string;
  team_id?: number | null;
  is_injured: boolean;
};

export type AdminPlayerListResponse = {
  total: number;
  injured: number;
  unselected: number;
  items: AdminPlayerListItem[];
};

export async function getAdminPlayers(
  adminToken: string
): Promise<AdminPlayerListResponse> {
  return apiFetch(
    "/admin/players",
    {
      headers: { "X-Admin-Token": adminToken }
    },
    undefined
  );
}

export async function getHealth(): Promise<{ ok: boolean; env?: string }> {
  return apiFetch("/health");
}

export async function registerNotificationDevice(
  token: string,
  payload: {
    token: string;
    platform: NotificationDevicePlatform;
    device_id: string;
    timezone?: string;
    app_channel: string;
    app_version?: string;
  }
): Promise<{ ok: boolean; device: NotificationDevice }> {
  return apiFetch(
    "/notifications/devices/register",
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    token
  );
}

export async function unregisterNotificationDevice(
  token: string,
  deviceId: string
): Promise<{ ok: boolean; device_id: string }> {
  return apiFetch(
    `/notifications/devices/${encodeURIComponent(deviceId)}`,
    {
      method: "DELETE"
    },
    token
  );
}

export async function getNotificationDevices(token: string): Promise<NotificationDevice[]> {
  return apiFetch("/notifications/devices", {}, token);
}

export async function createLeague(token: string, name: string): Promise<League> {
  return apiFetch(
    "/leagues",
    {
      method: "POST",
      body: JSON.stringify({ name })
    },
    token
  );
}

export async function joinLeague(token: string, code: string): Promise<League> {
  return apiFetch(
    "/leagues/join",
    {
      method: "POST",
      body: JSON.stringify({ code })
    },
    token
  );
}

export async function getMyLeague(token: string): Promise<League> {
  return apiFetch("/leagues/me", {}, token);
}

export async function leaveLeague(token: string): Promise<{ ok: boolean; league_deleted: boolean }> {
  return apiFetch(
    "/leagues/leave",
    {
      method: "POST"
    },
    token
  );
}

export async function removeLeagueMember(
  token: string,
  fantasyTeamId: number
): Promise<{ ok: boolean }> {
  return apiFetch(
    `/leagues/members/${fantasyTeamId}`,
    {
      method: "DELETE"
    },
    token
  );
}

export async function getRankingGeneral(token?: string): Promise<RankingResponse> {
  return apiFetch("/ranking/general", {}, token);
}

export async function getRankingLeague(token: string): Promise<RankingResponse> {
  return apiFetch("/ranking/league", {}, token);
}

export async function getRankingLineup(
  token: string | undefined,
  fantasyTeamId: number,
  roundNumber?: number
): Promise<PublicLineup> {
  const query = roundNumber ? `?round_number=${roundNumber}` : "";
  return apiFetch(`/ranking/team/${fantasyTeamId}/lineup${query}`, {}, token);
}

export async function getRankingMarket(
  token: string | undefined,
  fantasyTeamId: number
): Promise<PublicMarket> {
  return apiFetch(`/ranking/team/${fantasyTeamId}/market`, {}, token);
}

export async function getMatchStats(matchId: number): Promise<MatchPlayerStat[]> {
  return apiFetch(`/catalog/match-stats?match_id=${matchId}`);
}

export async function getPlayerMatches(playerId: number): Promise<PlayerMatch[]> {
  return apiFetch(`/catalog/player-matches?player_id=${playerId}`);
}
