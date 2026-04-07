from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class FilterState:
    round_range: tuple[int, int]
    min_minutes: int
    tournaments: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatasetBundle:
    season_year: int
    season_label: str
    data_dir: Path
    matches: pd.DataFrame
    teams: pd.DataFrame
    players: pd.DataFrame
    player_match: pd.DataFrame
    player_totals: pd.DataFrame
    team_stats: pd.DataFrame
    average_positions: pd.DataFrame
    heatmap_points: pd.DataFrame
    validation_status: str
    validation_warnings: tuple[str, ...]
    manifest: dict[str, Any]
    validation: dict[str, Any]
    loaded_at: datetime
    shot_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    match_momentum: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def has_schedule(self) -> bool:
        return not self.matches.empty

    @property
    def has_team_layer(self) -> bool:
        return not self.teams.empty

    @property
    def has_player_layer(self) -> bool:
        return not self.player_match.empty

    @property
    def has_match_stats_layer(self) -> bool:
        return not self.team_stats.empty

    @property
    def has_positional_layer(self) -> bool:
        return not self.average_positions.empty or not self.heatmap_points.empty

    @property
    def has_shot_layer(self) -> bool:
        return not self.shot_events.empty

    @property
    def has_momentum_layer(self) -> bool:
        return not self.match_momentum.empty

    @property
    def warning_count(self) -> int:
        return len(self.validation_warnings)

    @property
    def coverage_label(self) -> str:
        if self.validation_status == "passed" and self.warning_count == 0:
            return "Validacion passed"
        if self.validation_status == "passed":
            return f"Validacion passed | {self.warning_count} warnings"
        if self.validation_status:
            return f"Validacion {self.validation_status}"
        return "Validacion no disponible"


@dataclass(frozen=True)
class SeasonDataset:
    season_year: int
    season_label: str
    data_dir: Path
    manifest: dict[str, Any]
    validation: dict[str, Any]

    @property
    def validation_status(self) -> str:
        return str(self.validation.get("status", "unknown"))

    @property
    def warning_count(self) -> int:
        warnings = self.validation.get("warnings", [])
        return len(warnings) if isinstance(warnings, list) else 0

    @property
    def coverage_label(self) -> str:
        if self.validation_status == "passed" and self.warning_count == 0:
            return "Validacion passed"
        if self.validation_status == "passed":
            return f"Validacion passed | {self.warning_count} warnings"
        return f"Validacion {self.validation_status}"


@dataclass(frozen=True)
class ConsolidatedSeasonOverview:
    total_seasons: int
    total_matches: int
    total_players: int
    total_goals: int
    goals_per_match: float
    passed_seasons: int
    warning_seasons: int
    seasons_table: pd.DataFrame


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
    shot_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    shot_events_metadata: dict[str, object] = field(default_factory=dict)
    momentum_series: pd.DataFrame = field(default_factory=pd.DataFrame)
    momentum_metadata: dict[str, object] = field(default_factory=dict)
    goalkeeper_saves: pd.DataFrame = field(default_factory=pd.DataFrame)
