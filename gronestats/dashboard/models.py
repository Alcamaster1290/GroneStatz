from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass(frozen=True)
class FilterState:
    round_range: tuple[int, int]
    min_minutes: int
    tournaments: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatasetBundle:
    matches: pd.DataFrame
    teams: pd.DataFrame
    players: pd.DataFrame
    player_match: pd.DataFrame
    player_totals: pd.DataFrame
    team_stats: pd.DataFrame
    average_positions: pd.DataFrame
    heatmap_points: pd.DataFrame
    loaded_at: datetime


@dataclass(frozen=True)
class LeagueOverview:
    total_matches: int
    total_teams: int
    total_players: int
    total_goals: int
    goals_per_match: float
    standings: pd.DataFrame
    goals_by_round: pd.DataFrame
    venue_goals: pd.DataFrame
    form_table: pd.DataFrame
    leaders: dict[str, pd.DataFrame]
    top_matches: pd.DataFrame


@dataclass(frozen=True)
class TeamProfile:
    team_id: int
    team_name: str
    team_row: pd.Series
    team_color: str
    summary: dict[str, float | int | str]
    recent_matches: pd.DataFrame
    splits: pd.DataFrame
    top_players: pd.DataFrame
    comparison: pd.DataFrame


@dataclass(frozen=True)
class PlayerProfile:
    player_id: int
    player_row: pd.Series
    team_color: str
    summary: dict[str, float | int | str]
    percentiles: pd.DataFrame
    recent_matches: pd.DataFrame
    available_visual_matches: pd.DataFrame
    visual_coverage: dict[str, object]
    default_visual_match_id: int | None
    default_visual_mode: str
    default_visual_scope: str
    contextual_average_position_row: pd.Series | None
    accumulated_average_position_row: pd.Series | None
    contextual_heatmap_points: pd.DataFrame
    accumulated_heatmap_points: pd.DataFrame


@dataclass(frozen=True)
class MatchSummary:
    match_id: int
    match_row: pd.Series
    home_team_color: str
    away_team_color: str
    curated_stats: pd.DataFrame
    grouped_stats: dict[str, pd.DataFrame]
    player_rows: pd.DataFrame
    standout_players: pd.DataFrame
    insight_cards: list[dict[str, str]]
    home_context_matches: pd.DataFrame
    away_context_matches: pd.DataFrame
    catalog_neighbors: dict[str, object]
    origin_context: dict[str, object]
    team_average_positions: pd.DataFrame
    average_position_metadata: dict[str, object]
