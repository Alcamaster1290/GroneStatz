export type Position = "G" | "D" | "M" | "F";

export type Player = {
  player_id: number;
  name: string;
  short_name?: string | null;
  shortName?: string | null;
  position: Position;
  team_id: number;
  price_current: number;
  is_injured?: boolean;
  goals?: number;
  assists?: number;
  saves?: number;
  goals_round?: number | null;
  assists_round?: number | null;
  saves_round?: number | null;
  fouls?: number;
  yellow_cards?: number;
  red_cards?: number;
  points_round?: number;
  points_total?: number;
  clean_sheets?: number;
  goals_conceded?: number;
  bought_price?: number;
};

export type MarketFiltersState = {
  positions: Position[];
  minPrice: string;
  maxPrice: string;
  query: string;
  teamId: string;
};

export type LineupSlot = {
  slot_index: number;
  is_starter: boolean;
  role: Position;
  player_id: number | null;
  player?: Player | null;
};

export type LineupOut = {
  lineup_id: number;
  round_number: number;
  is_closed: boolean;
  captain_player_id?: number | null;
  vice_captain_player_id?: number | null;
  slots: LineupSlot[];
};

export type Fixture = {
  id: number;
  round_number: number;
  match_id: number;
  home_team_id: number | null;
  away_team_id: number | null;
  kickoff_at: string | null;
  stadium?: string | null;
  city?: string | null;
  status: "Programado" | "Postergado" | "Finalizado";
  home_score?: number | null;
  away_score?: number | null;
};

export type RoundInfo = {
  round_number: number;
  is_closed: boolean;
  status?: string | null;
  starts_at?: string | null;
  ends_at?: string | null;
};

export type MatchPlayerStat = {
  match_id: number;
  player_id: number;
  name: string;
  short_name?: string | null;
  position: Position;
  team_id: number;
  minutesplayed: number;
  goals: number;
  assists: number;
  saves: number;
  fouls: number;
  yellow_cards: number;
  red_cards: number;
  clean_sheet?: number | null;
  goals_conceded?: number | null;
  points: number;
};

export type PlayerMatch = {
  match_id: number;
  round_number: number;
  kickoff_at?: string | null;
  status: string;
  home_team_id?: number | null;
  away_team_id?: number | null;
  home_score?: number | null;
  away_score?: number | null;
  minutesplayed?: number | null;
  goals?: number | null;
  assists?: number | null;
  saves?: number | null;
  fouls?: number | null;
  yellow_cards?: number | null;
  red_cards?: number | null;
  clean_sheet?: number | null;
  goals_conceded?: number | null;
  points?: number | null;
};

export type PlayerStatsEntry = {
  player_id: number;
  name: string;
  short_name?: string | null;
  position: Position;
  team_id: number;
  price_current: number;
  is_injured?: boolean;
  selected_count: number;
  selected_percent: number;
  goals: number;
  assists: number;
  minutesplayed: number;
  saves: number;
  fouls: number;
  yellow_cards: number;
  red_cards: number;
  rounds?: { round_number: number; points: number }[];
};

export type AdminTeamPlayer = {
  player_id: number;
  name: string;
  short_name?: string | null;
  shortName?: string | null;
  position: Position;
  team_id: number;
  price_current: number;
  bought_price: number;
  is_injured?: boolean;
};

export type AdminTeam = {
  fantasy_team_id: number;
  user_id: number;
  user_email: string;
  season_id: number;
  name?: string | null;
  budget_cap: number;
  budget_used: number;
  budget_left: number;
  club_counts: Record<number, number>
  favorite_team_id?: number | null;
  squad: AdminTeamPlayer[];
};

export type AdminLineupPlayer = {
  player_id?: number | null;
  name?: string | null;
  short_name?: string | null;
  position?: Position | string | null;
  team_id?: number | null;
  is_injured?: boolean | null;
};

export type AdminLineupSlot = {
  slot_index: number;
  is_starter: boolean;
  role: Position | string;
  player_id?: number | null;
  player?: AdminLineupPlayer | null;
};

export type AdminTeamLineup = {
  fantasy_team_id: number;
  team_name?: string | null;
  user_email: string;
  round_number: number;
  lineup_id: number;
  created_at: string;
  captain_player_id?: number | null;
  vice_captain_player_id?: number | null;
  slots: AdminLineupSlot[];
};

export type FantasyTeam = {
  id: number;
  name?: string | null;
  budget_cap: number;
  budget_used: number;
  budget_left: number;
  club_counts: Record<number, number>
  favorite_team_id?: number | null;
  squad: Player[];
};

export type FixtureStatus = "Programado" | "Postergado" | "Finalizado";

export type AdminFixture = {
  id: number;
  round_number: number;
  match_id: number;
  home_team_id: number | null;
  away_team_id: number | null;
  kickoff_at: string | null;
  stadium?: string | null;
  city?: string | null;
  status: FixtureStatus;
  home_score?: number | null;
  away_score?: number | null;
};

export type AdminMatchPlayer = {
  match_id: number;
  player_id: number;
  name: string;
  short_name?: string | null;
  position?: Position | string | null;
  team_id?: number | null;
  minutesplayed: number;
  goals: number;
  assists: number;
  saves: number;
  fouls: number;
  yellow_cards: number;
  red_cards: number;
  clean_sheet?: number | null;
  goals_conceded?: number | null;
  points: number;
};

export type AdminRoundTopPlayer = {
  player_id: number;
  name: string;
  short_name?: string | null;
  position?: Position | string | null;
  team_id?: number | null;
  points: number;
};

export type AdminPriceMovement = {
  round_number: number;
  player_id: number;
  name: string;
  short_name?: string | null;
  position: Position;
  team_id: number;
  price_current: number;
  points: number;
  delta: number;
};

export type AdminTransferPlayer = {
  player_id: number;
  name: string;
  short_name?: string | null;
  position: Position | string;
  team_id: number;
};

export type AdminTransfer = {
  id: number;
  fantasy_team_id: number;
  team_name?: string | null;
  user_email: string;
  round_number: number;
  created_at: string;
  out_player?: AdminTransferPlayer | null;
  in_player?: AdminTransferPlayer | null;
  out_price: number;
  in_price: number;
  out_price_current: number;
  in_price_current: number;
  transfer_fee: number;
  budget_after: number;
};

export type AdminRound = {
  id: number;
  round_number: number;
  is_closed: boolean;
  status?: string | null;
  starts_at?: string | null;
  ends_at?: string | null;
};

export type AdminLeagueMember = {
  fantasy_team_id: number;
  team_name?: string | null;
  user_email: string;
  joined_at: string;
};

export type AdminLeague = {
  id: number;
  code: string;
  name: string;
  owner_fantasy_team_id: number;
  created_at: string;
  members: AdminLeagueMember[];
};

export type AdminActionLog = {
  id: number;
  category: string;
  action: string;
  created_at: string;
  actor_user_id?: number | null;
  actor_email?: string | null;
  league_id?: number | null;
  fantasy_team_id?: number | null;
  target_user_id?: number | null;
  target_fantasy_team_id?: number | null;
  details?: string | null;
};

export type AdminPlayerInjury = {
  player_id: number;
  is_injured: boolean;
};

export type League = {
  id: number;
  code: string;
  name: string;
  owner_fantasy_team_id: number;
  is_admin: boolean;
};

export type RankingRound = {
  round_number: number;
  points: number;
  cumulative: number;
  price_delta?: number;
};

export type RankingEntry = {
  fantasy_team_id: number;
  team_name: string;
  total_points: number;
  captain_player_id?: number | null;
  favorite_team_id?: number | null;
  rounds: RankingRound[];
};

export type RankingResponse = {
  round_numbers: number[];
  entries: RankingEntry[];
};

export type PublicLineupPlayer = {
  player_id: number;
  name: string;
  short_name?: string | null;
  position: Position;
  team_id: number;
  is_injured: boolean;
};

export type PublicLineupSlot = {
  slot_index: number;
  is_starter: boolean;
  role: Position;
  player_id?: number | null;
  player?: PublicLineupPlayer | null;
  points?: number | null;
};

export type PublicLineup = {
  fantasy_team_id: number;
  team_name: string;
  round_number: number;
  captain_player_id?: number | null;
  vice_captain_player_id?: number | null;
  slots: PublicLineupSlot[];
};

export type PublicMarketPlayer = {
  player_id: number;
  name: string;
  short_name?: string | null;
  position: Position;
  team_id: number;
  is_injured: boolean;
  price_current: number;
  bought_price: number;
  points_total: number;
};

export type PublicMarket = {
  fantasy_team_id: number;
  team_name: string;
  players: PublicMarketPlayer[];
};

export type TransferCount = {
  round_number: number;
  transfers_used: number;
  next_fee: number;
};
