from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from gronestats.processing.canonical_warehouse import (
    CANONICAL_SCHEMAS,
    DASHBOARD_EXPORT_SCHEMAS,
    FANTASY_EXPORT_SCHEMAS,
    build_canonical_tables,
    build_dashboard_bundle_from_canonical,
    build_fantasy_bundle_from_canonical,
    cast_frame_to_schema,
    empty_typed_frame,
    load_canonical_tables_for_season,
    upsert_canonical_tables,
    validate_warehouse_contract,
)


def _sample_curated_tables() -> dict[str, pd.DataFrame]:
    return {
        "matches": pd.DataFrame(
            {
                "match_id": [1],
                "round_number": [1],
                "tournament": ["Liga 1, Apertura"],
                "home_id": [10],
                "away_id": [20],
                "home": ["Alianza"],
                "away": ["Melgar"],
                "home_score": [1],
                "away_score": [0],
                "resultado_final": ["Alianza 1-0 Melgar"],
                "fecha": ["01/01/2025 15:00"],
                "estadio": ["Matute"],
                "ciudad": ["Lima"],
                "arbitro": ["A"],
            }
        ),
        "teams": pd.DataFrame(
            {
                "team_id": [10, 20],
                "short_name": ["Alianza", "Melgar"],
                "full_name": ["Alianza Lima", "FBC Melgar"],
                "team_colors": ["#112233", "#445566"],
            }
        ),
        "players": pd.DataFrame(
            {
                "player_id": [100, 200],
                "name": ["Jugador Uno", "Jugador Dos"],
                "short_name": ["J. Uno", "J. Dos"],
                "position": ["F", "G"],
                "team_id": [10, 20],
                "dateofbirth": ["2000-01-01", "1998-03-04"],
                "age_jan_2026": [26.0, 28.0],
            }
        ),
        "player_identity": pd.DataFrame(
            {
                "player_id": [100, 200],
                "name": ["Jugador Uno", "Jugador Dos"],
                "short_name": ["J. Uno", "J. Dos"],
                "position": ["F", "G"],
                "team_id": [10, 20],
                "dateofbirth": ["2000-01-01", "1998-03-04"],
                "age_jan_2026": [26.0, 28.0],
                "last_match_id": [1, 1],
                "last_seen_at": pd.to_datetime(["2025-01-01 15:00:00", "2025-01-01 15:00:00"]),
            }
        ),
        "player_match": pd.DataFrame(
            {
                "match_id": [1, 1],
                "player_id": [100, 200],
                "name": ["Jugador Uno", "Jugador Dos"],
                "team_id": [10, 20],
                "position": ["F", "G"],
                "minutesplayed": [90, 90],
                "goals": [1, 0],
                "assists": [0, 0],
                "yellowcards": [0, 0],
                "redcards": [0, 0],
                "saves": [0, 3],
                "fouls": [1, 0],
                "penaltywon": [0, 0],
                "penaltysave": [0, 0],
                "penaltyconceded": [0, 0],
                "rating": [7.4, 7.1],
            }
        ),
        "player_totals_full_season": pd.DataFrame(
            {
                "player_id": [100, 200],
                "goals": [1, 0],
                "assists": [0, 0],
                "saves": [0, 3],
                "fouls": [1, 0],
                "minutesplayed": [90, 90],
                "penaltywon": [0, 0],
                "penaltysave": [0, 0],
                "penaltyconceded": [0, 0],
                "matches_played": [1, 1],
            }
        ),
        "team_stats": pd.DataFrame(
            {
                "NAME": ["Posesion"],
                "HOME": ["Alianza"],
                "AWAY": ["Melgar"],
                "COMPARECODE": [1],
                "STATISTICSTYPE": ["positive"],
                "VALUETYPE": ["percent"],
                "HOMEVALUE": [60],
                "AWAYVALUE": [40],
                "RENDERTYPE": [2],
                "KEY": ["ballPossession"],
                "PERIOD": ["ALL"],
                "GROUP": ["Match overview"],
                "HOMETOTAL": [100.0],
                "AWAYTOTAL": [100.0],
                "MATCH_ID": [1],
            }
        ),
        "average_positions": pd.DataFrame(
            {
                "match_id": [1],
                "player_id": [100],
                "team_id": [10],
                "team_name": ["Alianza"],
                "name": ["Jugador Uno"],
                "shirt_number": [9],
                "position": ["F"],
                "average_x": [42.0],
                "average_y": [55.0],
                "points_count": [12],
                "is_starter": [True],
            }
        ),
        "heatmap_points": pd.DataFrame(columns=["match_id", "player_id", "team_id", "team_name", "name", "x", "y"]),
        "shot_events": pd.DataFrame(
            {
                "match_id": [1],
                "shot_id": [9001],
                "player_id": [100],
                "is_home": [True],
                "shot_type": ["goal"],
                "situation": ["open_play"],
                "body_part": ["right_foot"],
                "goal_mouth_location": ["center"],
                "goal_mouth_coordinates": ["50,20"],
                "time": [24],
                "added_time": [0.0],
                "time_seconds": [1440],
                "incident_type": ["shot"],
                "block_coordinates": [pd.NA],
                "goal_type": ["regular"],
                "name": ["Jugador Uno"],
                "short_name": ["J. Uno"],
                "position": ["F"],
                "jersey_number": [9],
                "x": [85.0],
                "y": [50.0],
                "z": [1],
                "team_id": [10],
                "team_name": ["Alianza"],
            }
        ),
        "match_momentum": pd.DataFrame(
            {
                "match_id": [1, 1],
                "minute": [1.0, 2.0],
                "value": [3, -2],
                "dominant_side": ["home", "away"],
            }
        ),
    }


def test_build_canonical_tables_backfills_missing_columns_and_types() -> None:
    canonical = build_canonical_tables(_sample_curated_tables(), season=2025)

    matches = canonical["matches_canonical"]
    teams = canonical["teams_canonical"]
    heatmap_points = canonical["heatmap_points_canonical"]
    shot_events = canonical["shot_events_canonical"]

    assert "status" in matches.columns
    assert str(matches["status"].dtype) == "string"
    assert list(teams.columns) == list(CANONICAL_SCHEMAS["teams_canonical"].column_names)
    assert str(teams["is_altitude_team"].dtype) == "boolean"
    assert list(heatmap_points.columns) == list(CANONICAL_SCHEMAS["heatmap_points_canonical"].column_names)
    assert str(shot_events["z"].dtype) == "float64"


def test_warehouse_roundtrip_builds_dashboard_and_fantasy_exports(tmp_path: Path) -> None:
    pytest.importorskip("duckdb")
    warehouse_path = tmp_path / "warehouse" / "gronestats.duckdb"

    canonical = build_canonical_tables(_sample_curated_tables(), season=2025)
    row_counts = upsert_canonical_tables(warehouse_path, canonical, season=2025)
    restored = load_canonical_tables_for_season(warehouse_path, season=2025)
    dashboard_bundle = build_dashboard_bundle_from_canonical(restored)
    fantasy_bundle = build_fantasy_bundle_from_canonical(restored)
    validation = validate_warehouse_contract(warehouse_path, season=2025)

    assert row_counts["matches_canonical"] == 1
    assert validation["status"] == "passed"
    assert list(dashboard_bundle["matches"].columns) == list(DASHBOARD_EXPORT_SCHEMAS["matches"].column_names)
    assert str(dashboard_bundle["teams"]["is_altitude_team"].dtype) == "boolean"
    assert list(fantasy_bundle["player_transfer"].columns) == list(FANTASY_EXPORT_SCHEMAS["player_transfer"].column_names)
    assert str(fantasy_bundle["player_transfer"]["player_id"].dtype) == "Int64"
    assert str(fantasy_bundle["players_fantasy"]["matches_played"].dtype) == "Int64"


def test_empty_typed_frame_preserves_schema_for_optional_layers() -> None:
    frame = empty_typed_frame(CANONICAL_SCHEMAS["heatmap_points_canonical"])
    coerced = cast_frame_to_schema(frame, CANONICAL_SCHEMAS["heatmap_points_canonical"])

    assert frame.empty
    assert list(frame.columns) == ["season_year", "match_id", "player_id", "team_id", "team_name", "name", "x", "y"]
    assert str(coerced["x"].dtype) == "float64"
