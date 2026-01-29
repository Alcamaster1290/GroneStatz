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
  fouls?: number;
  yellow_cards?: number;
  red_cards?: number;
  points_round?: number;
  clean_sheets?: number;
  goals_conceded?: number;
  bought_price?: number;
};

export type MarketFiltersState = {
  positions: Position[];
  minPrice: string;
  maxPrice: string;
  query: string;
};

export type LineupSlot = {
  slot_index: number;
  is_starter: boolean;
  role: Position;
  player_id: number | null;
};

export type LineupOut = {
  lineup_id: number;
  round_number: number;
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
  club_counts: Record<number, number>;
  squad: AdminTeamPlayer[];
};

export type FantasyTeam = {
  id: number;
  name?: string | null;
  budget_cap: number;
  budget_used: number;
  budget_left: number;
  club_counts: Record<number, number>;
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

export type AdminRound = {
  id: number;
  round_number: number;
  is_closed: boolean;
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
};

export type RankingEntry = {
  fantasy_team_id: number;
  team_name: string;
  total_points: number;
  captain_player_id?: number | null;
  rounds: RankingRound[];
};

export type RankingResponse = {
  round_numbers: number[];
  entries: RankingEntry[];
};

export type TransferCount = {
  round_number: number;
  transfers_used: number;
  next_fee: number;
};
