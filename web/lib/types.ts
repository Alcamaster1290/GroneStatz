/** Forma de las respuestas de la API (`gronestats/api/queries.py`). Un dato ausente llega como `null`, nunca como cero. */

export interface Team {
  team_id: number;
  name: string;
  full_name: string | null;
  color: string | null;
  level: string | null;
  stadium: string | null;
  department: string | null;
  region: string | null;
  crest: string | null;
}

export interface ReleaseInfo {
  release_id: string;
  schema_version: string;
  built_at: string | null;
  data_as_of: string | null;
  seasons: number[];
  models: Record<string, string>;
}

export interface SeasonInfo {
  season: number;
  tournaments: string[];
  rounds: Record<string, number>;
}

export interface StandingRow extends Partial<Team> {
  pos: number;
  team_id: number;
  pj: number;
  pg: number;
  pe: number;
  pp: number;
  gf: number;
  gc: number;
  dg: number;
  pts: number;
}

export interface Standings {
  release_id: string;
  season: number;
  tournament: string;
  round_number: number;
  rounds: number;
  rows: StandingRow[];
}

export interface Importance {
  band: number | null;
  band_name: string | null;
  lives: number | null;
  threshold_used: number;
  matches_before: number;
  matches_remaining: number;
  points_before: number;
  points_needed: number;
}

export interface StripMatch {
  match_id: number;
  tournament: string;
  round_number: number | null;
  date: string | null;
  status: string | null;
  is_home: boolean;
  rival: Team | null;
  estadio: string | null;
  ciudad: string | null;
  altitude_m: number | null;
  altitude_diff_m: number | null;
  goals_for: number | null;
  goals_against: number | null;
  result: "G" | "E" | "P" | null;
  xg_for: number | null;
  xg_against: number | null;
  yellow_for: number | null;
  yellow_against: number | null;
  red_for: number | null;
  red_against: number | null;
  formation: string | null;
  defenders_ok: boolean | null;
  importance: Importance | null;
  p_title_before: number | null;
  p_title_after: number | null;
}

export interface TeamMatches {
  release_id: string;
  team: Team;
  season: number;
  base_altitude_m?: number | null;
  tournaments: Record<string, StripMatch[]>;
  missing_reason?: string;
}

export interface TitlePoint {
  k: number;
  p_title: number;
  points: number | null;
  match_id: number | null;
}

export interface TitleSeries {
  team_id: number;
  name: string;
  color: string | null;
  crest: string | null;
  final_points: number | null;
  series: TitlePoint[];
}

export interface TitleRace {
  release_id: string;
  season: number;
  tournament: string | null;
  team: Team;
  teams: TitleSeries[];
  missing_reason?: string;
}

export interface TeamPlayer {
  player_id: number;
  name: string;
  short_name: string | null;
  position: string | null;
  photo: string | null;
  matches: number;
  minutes: number | null;
  goals: number | null;
  assists: number | null;
  rating: number | null;
  shots: number;
  xg: number;
}

export interface TeamPlayers {
  release_id: string;
  team: Team;
  season: number;
  players: TeamPlayer[];
  missing_reason: string | null;
}

export interface Shot {
  shot_id: number;
  player_id: number | null;
  player_name: string | null;
  team_id: number;
  is_home: boolean;
  minute: number | null;
  x: number | null;
  y: number | null;
  xg: number | null;
  is_goal: boolean;
  situation: string | null;
  body_part: string | null;
  shot_type: string | null;
}

export interface MatchSide {
  team: Team | null;
  score: number | null;
  formation: string | null;
  defenders_ok: boolean | null;
  xg: number | null;
  importance: Importance | null;
  p_title_after: number | null;
}

export interface MatchPlayer {
  player_id: number;
  name: string;
  photo: string | null;
  team_id: number;
  position: string | null;
  minutesplayed: number | null;
  goals: number | null;
  assists: number | null;
  rating: number | null;
}

export interface MatchDetail {
  release_id: string;
  match: {
    match_id: number;
    season: number;
    tournament: string;
    round_number: number | null;
    date: string | null;
    status: string | null;
    estadio: string | null;
    ciudad: string | null;
    arbitro: string | null;
    altitude_m: number | null;
    home: MatchSide;
    away: MatchSide;
  };
  shots: Shot[];
  players: MatchPlayer[];
}

export interface PlayerSeason {
  season: number;
  team_id: number | null;
  team: Team | null;
  matches: number;
  minutes: number | null;
  goals: number | null;
  assists: number | null;
  yellow: number | null;
  red: number | null;
  rating: number | null;
  shots: number;
  xg: number;
  goals_minus_xg: number;
}

export interface PlayerProfile {
  release_id: string;
  player: { player_id: number; name: string; short_name: string | null; position: string | null; team: Team | null; photo: string | null };
  seasons: PlayerSeason[];
  selected_season: number | null;
  season_stats: PlayerSeason | null;
  missing_reason: string | null;
}

export interface PlayerShot {
  match_id: number;
  season: number;
  minute: number | null;
  x: number | null;
  y: number | null;
  xg: number | null;
  is_goal: boolean;
  situation: string | null;
  body_part: string | null;
  shot_type: string | null;
  date: string | null;
  rival: string | null;
}

export interface PlayerShots {
  release_id: string;
  player_id: number;
  season: number | null;
  shots: PlayerShot[];
  missing_reason: string | null;
}

export interface Heatmap {
  release_id: string;
  player_id: number;
  season: number | null;
  cols: number;
  rows: number;
  total: number;
  matches: number;
  cells: { ix: number; iy: number; n: number }[];
  missing_reason: string | null;
}

export interface CoverageRow {
  season: number;
  kind: string;
  expected: number;
  present: number;
  missing: number;
  /** SofaScore respondió 404: no se puede recuperar. */
  missing_from_source: number;
  /** Nunca se pidió. */
  pending: number;
  failed: number;
  blocked: number;
}

export interface ActionableGap {
  season: number;
  kind: string;
  pending: number;
  failed: number;
  blocked: number;
}

export interface KnownGap {
  season: number | null;
  kind: string;
  scope: string;
  reason: string;
  source: string;
}

export interface ModelRun {
  model: string;
  version: string;
  trained_on: string;
  params: Record<string, unknown> | string;
  metrics: unknown;
}

export interface Status {
  release_id: string;
  built_at: string | null;
  data_as_of: string | null;
  stale: boolean;
  stale_after_hours: number;
  overdue_matches: number;
  coverage: CoverageRow[];
  actionable: ActionableGap[];
  known_gaps: KnownGap[];
  ledger: Record<string, Record<string, Record<string, number>>>;
  models: ModelRun[];
  release_log: { release_id: string; built_at: string; matches: number; data_as_of: string | null }[];
}
