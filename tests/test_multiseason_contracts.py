from __future__ import annotations

import warnings

import pandas as pd

from gronestats.data_layout import season_layout
from gronestats.dashboard.data import (
    build_team_options,
    load_dashboard_data,
    season_parquet_signature,
)
from gronestats.dashboard.metrics import (
    build_league_overview,
    build_match_catalog,
    build_match_summary,
    build_player_profile,
    build_players_table,
    build_team_profile,
)
from gronestats.dashboard.models import FilterState
from gronestats.processing.canonical_warehouse import (
    build_dashboard_bundle_from_canonical,
    build_fantasy_bundle_from_canonical,
    load_canonical_tables_for_season,
)
from gronestats.processing.fantasy_export import FANTASY_EXPORT_TABLES


SEASONS = (2022, 2023, 2024, 2025, 2026)
DASHBOARD_TABLES = (
    "matches",
    "teams",
    "players",
    "player_match",
    "player_totals_full_season",
    "team_stats",
    "average_positions",
    "heatmap_points",
    "shot_events",
    "match_momentum",
    "player_identity",
)


def _schema_signature(path) -> tuple[list[str], dict[str, str]]:
    frame = pd.read_parquet(path)
    return list(frame.columns), {column: str(dtype) for column, dtype in frame.dtypes.items()}


def _season_filters(bundle) -> FilterState:
    tournaments = tuple(bundle.matches["tournament"].dropna().astype(str).unique().tolist()) if "tournament" in bundle.matches.columns else ()
    round_min = int(bundle.matches["round_number"].min()) if not bundle.matches.empty else 1
    round_max = int(bundle.matches["round_number"].max()) if not bundle.matches.empty else 1
    return FilterState(round_range=(round_min, round_max), min_minutes=0, tournaments=tournaments)


def test_dashboard_schema_consistency_across_published_seasons() -> None:
    reference_season = SEASONS[0]
    reference_dir = season_layout(reference_season, league="Liga 1 Peru").dashboard.current_dir

    for table_name in DASHBOARD_TABLES:
        reference_schema = _schema_signature(reference_dir / f"{table_name}.parquet")
        for season in SEASONS[1:]:
            candidate_dir = season_layout(season, league="Liga 1 Peru").dashboard.current_dir
            assert _schema_signature(candidate_dir / f"{table_name}.parquet") == reference_schema


def test_fantasy_schema_consistency_across_published_seasons() -> None:
    reference_season = SEASONS[0]
    reference_dir = season_layout(reference_season, league="Liga 1 Peru").fantasy.current_dir

    for table_name in FANTASY_EXPORT_TABLES:
        reference_schema = _schema_signature(reference_dir / f"{table_name}.parquet")
        for season in SEASONS[1:]:
            candidate_dir = season_layout(season, league="Liga 1 Peru").fantasy.current_dir
            assert _schema_signature(candidate_dir / f"{table_name}.parquet") == reference_schema


def test_dashboard_loader_emits_no_futurewarnings_for_published_seasons() -> None:
    for season in SEASONS:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            bundle = load_dashboard_data(season, season_parquet_signature(season))
        future_warnings = [warning for warning in caught if issubclass(warning.category, FutureWarning)]
        assert bundle.has_schedule
        assert future_warnings == []


def test_dashboard_smoke_with_real_published_seasons() -> None:
    for season in SEASONS:
        bundle = load_dashboard_data(season, season_parquet_signature(season))
        filters = _season_filters(bundle)
        overview = build_league_overview(bundle, filters)
        team_options = build_team_options(bundle)
        catalog = build_match_catalog(bundle, filters)

        assert overview.total_matches >= 1
        assert not catalog.empty
        if not team_options.empty:
            team_id = int(team_options.iloc[0]["team_id"])
            assert build_team_profile(bundle, filters, team_id) is not None
        if bundle.has_player_layer:
            players_table = build_players_table(bundle, filters)
            assert not players_table.empty
            player_id = int(players_table.iloc[0]["player_id"])
            assert build_player_profile(bundle, filters, player_id) is not None

        match_id = int(catalog.iloc[0]["match_id"])
        assert build_match_summary(bundle, filters, match_id, catalog) is not None


def test_published_targets_match_warehouse_exports_by_row_count() -> None:
    warehouse_path = season_layout(2026, league="Liga 1 Peru").warehouse_db_path

    for season in SEASONS:
        canonical_tables = load_canonical_tables_for_season(warehouse_path, season)
        dashboard_bundle = build_dashboard_bundle_from_canonical(canonical_tables)
        fantasy_bundle = build_fantasy_bundle_from_canonical(canonical_tables)
        dashboard_dir = season_layout(season, league="Liga 1 Peru").dashboard.current_dir
        fantasy_dir = season_layout(season, league="Liga 1 Peru").fantasy.current_dir

        for table_name in DASHBOARD_TABLES:
            published = pd.read_parquet(dashboard_dir / f"{table_name}.parquet")
            assert len(published) == len(dashboard_bundle[table_name])

        for table_name in FANTASY_EXPORT_TABLES:
            published = pd.read_parquet(fantasy_dir / f"{table_name}.parquet")
            assert len(published) == len(fantasy_bundle[table_name])


def test_published_dashboard_types_cover_known_drift_columns() -> None:
    for season in SEASONS:
        current_dir = season_layout(season, league="Liga 1 Peru").dashboard.current_dir
        matches = pd.read_parquet(current_dir / "matches.parquet")
        teams = pd.read_parquet(current_dir / "teams.parquet")
        team_stats = pd.read_parquet(current_dir / "team_stats.parquet")
        shot_events = pd.read_parquet(current_dir / "shot_events.parquet")
        heatmap_points = pd.read_parquet(current_dir / "heatmap_points.parquet")

        assert "status" in matches.columns
        assert str(matches["status"].dtype) == "string"
        assert "is_altitude_team" in teams.columns
        assert str(teams["is_altitude_team"].dtype) == "boolean"
        assert str(team_stats["HOMEVALUE"].dtype) == "float64"
        assert str(team_stats["AWAYVALUE"].dtype) == "float64"
        assert str(shot_events["z"].dtype) == "float64"
        assert list(heatmap_points.columns) == ["match_id", "player_id", "team_id", "team_name", "name", "x", "y"]
