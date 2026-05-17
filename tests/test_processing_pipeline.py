from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from gronestats.processing.pipeline import (
    FANTASY_SOURCE_MODE,
    PipelinePaths,
    REQUIRED_CURATED_TABLES,
    build_parser,
    build_average_positions_curated,
    build_heatmap_points_curated,
    build_player_totals_full_season,
    publish_release_atomically,
    resolve_changed_match_ids,
    should_refresh_fantasy_bridge,
    source_mode_from_paths,
    stringify_if_mixed_objects,
    validate_dataset_contract,
)


def _write_required_contract_tables(dataset_dir: Path) -> None:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    for table_name in REQUIRED_CURATED_TABLES:
        pd.DataFrame().to_parquet(dataset_dir / f"{table_name}.parquet", index=False)


def _make_pipeline_paths(base_dir: Path, season: int = 2026) -> PipelinePaths:
    return PipelinePaths(
        base_dir=base_dir,
        league="Liga 1 Peru",
        season=season,
        run_id="20260404_000001",
        release_id="20260404_000001",
    )


def test_build_player_totals_full_season_aggregates_player_match() -> None:
    player_match = pd.DataFrame(
        {
            "match_id": [1, 2, 2],
            "player_id": [10, 10, 20],
            "goals": [1, 2, 0],
            "assists": [0, 1, 1],
            "saves": [0, 0, 3],
            "fouls": [2, 1, 0],
            "minutesplayed": [90, 45, 90],
            "penaltywon": [0, 1, 0],
            "penaltysave": [0, 0, 0],
            "penaltyconceded": [0, 0, 1],
        }
    )

    totals = build_player_totals_full_season(player_match).set_index("player_id")

    assert totals.loc[10, "goals"] == 3
    assert totals.loc[10, "assists"] == 1
    assert totals.loc[10, "matches_played"] == 2
    assert totals.loc[20, "saves"] == 3
    assert totals.loc[20, "penaltyconceded"] == 1


def test_average_positions_and_heatmap_points_keep_raw_coordinates() -> None:
    player_stats_raw = pd.DataFrame(
        {
            "match_id": [1],
            "id": [101],
            "name": ["Jugador Uno"],
            "shortName": ["J. Uno"],
            "teamId": [7],
            "position": ["M"],
            "shirtNumber": [8],
            "substitute": [False],
        }
    )
    average_positions_raw = pd.DataFrame(
        {
            "match_id": [1],
            "id": [101],
            "name": ["Jugador Uno"],
            "position": ["M"],
            "jerseyNumber": [8],
            "averageX": [0.0],
            "averageY": [55.5],
            "pointsCount": [12],
            "team": ["Equipo A"],
        }
    )
    heatmaps_raw = pd.DataFrame(
        {
            "match_id": [1],
            "player": ["Jugador Uno"],
            "heatmap": ["{'id': 101, 'heatmap': [(0, 10), (15.5, 20)]}"],
        }
    )
    teams = pd.DataFrame({"team_id": [7], "short_name": ["Equipo A"]})

    average_positions = build_average_positions_curated(average_positions_raw, player_stats_raw, teams)
    heatmap_points = build_heatmap_points_curated(heatmaps_raw, player_stats_raw, teams)

    assert average_positions.iloc[0]["average_x"] == 0.0
    assert average_positions.iloc[0]["average_y"] == 55.5
    assert heatmap_points["x"].tolist() == [0.0, 15.5]
    assert heatmap_points["y"].tolist() == [10.0, 20.0]


def test_resolve_changed_match_ids_detects_inventory_and_master_changes() -> None:
    current_raw = pd.DataFrame(
        {
            "match_id": [1, 2],
            "file_name": ["Sofascore_1.xlsx", "Sofascore_2.xlsx"],
            "size_bytes": [100, 250],
            "modified_ns": [1, 2],
        }
    )
    previous_raw = pd.DataFrame(
        {
            "match_id": [1, 2, 3],
            "file_name": ["Sofascore_1.xlsx", "Sofascore_2.xlsx", "Sofascore_3.xlsx"],
            "size_bytes": [100, 200, 300],
            "modified_ns": [1, 2, 3],
        }
    )
    current_master = pd.DataFrame({"match_id": [1, 2], "row_hash": ["same", "new-hash"]})
    previous_master = pd.DataFrame({"match_id": [1, 2, 3], "row_hash": ["same", "old-hash", "hash-3"]})

    changed = resolve_changed_match_ids(current_raw, previous_raw, current_master, previous_master)

    assert changed == {2, 3}


def test_source_mode_prefers_sofascore_when_fantasy_bridge_is_empty(tmp_path: Path) -> None:
    paths = _make_pipeline_paths(tmp_path)
    paths.fantasy_bridge_dir.mkdir(parents=True, exist_ok=True)
    paths.legacy_master_clean_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"match_id": [15590541], "home_score": [1], "away_score": [0]}).to_excel(
        paths.legacy_master_clean_path,
        index=False,
    )
    paths.fantasy_bridge_manifest_path.write_text(
        json.dumps(
            {
                "source_mode": FANTASY_SOURCE_MODE,
                "counts": {"fixtures": 0, "player_match_stats": 0},
            }
        ),
        encoding="utf-8",
    )
    paths.fantasy_python_path.parent.mkdir(parents=True, exist_ok=True)
    paths.fantasy_python_path.write_text("", encoding="utf-8")

    assert source_mode_from_paths(paths) == "sofascore"
    assert should_refresh_fantasy_bridge(paths) is False


def test_parser_supports_publish_and_validate_targets() -> None:
    parser = build_parser()

    run_args = parser.parse_args(["run", "--publish-target", "fantasy", "--from-phase", "build-warehouse"])
    validate_args = parser.parse_args(["validate", "--target", "all"])

    assert run_args.publish_target == "fantasy"
    assert run_args.from_phase == "build-warehouse"
    assert validate_args.target == "all"


def test_validate_dataset_contract_flags_orphans_and_missing_required_sheets(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "curated"
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    _write_required_contract_tables(dataset_dir)

    matches = pd.DataFrame({"match_id": [1], "home_score": [1], "away_score": [0]})
    teams = pd.DataFrame({"team_id": [10], "short_name": ["Equipo A"]})
    players = pd.DataFrame({"player_id": [100], "name": ["Jugador Uno"]})
    player_match = pd.DataFrame({"match_id": [99], "player_id": [100], "team_id": [999]})
    average_positions = pd.DataFrame({"match_id": [1], "player_id": [555], "average_x": [10], "average_y": [20]})
    heatmap_points = pd.DataFrame({"match_id": [42], "player_id": [100], "x": [1], "y": [2]})

    matches.to_parquet(dataset_dir / "matches.parquet", index=False)
    teams.to_parquet(dataset_dir / "teams.parquet", index=False)
    players.to_parquet(dataset_dir / "players.parquet", index=False)
    player_match.to_parquet(dataset_dir / "player_match.parquet", index=False)
    average_positions.to_parquet(dataset_dir / "average_positions.parquet", index=False)
    heatmap_points.to_parquet(dataset_dir / "heatmap_points.parquet", index=False)

    coverage = pd.DataFrame(
        {
            "match_id": [1],
            "has_player_stats": [False],
            "has_team_stats": [True],
            "has_average_positions": [False],
            "has_heatmaps": [False],
            "has_shotmap": [True],
            "has_momentum": [True],
        }
    )
    coverage.to_parquet(staging_dir / "sheet_coverage.parquet", index=False)

    validation = validate_dataset_contract(
        dataset_dir=dataset_dir,
        master_matches=pd.DataFrame({"match_id": [1]}),
        staging_dir=staging_dir,
        reference_dir=None,
    )

    assert validation["status"] == "failed"
    assert any("player_match has orphan match_ids" in message for message in validation["blocking_errors"])
    assert any("unresolved team_id" in message for message in validation["blocking_errors"])
    assert any("average_positions has orphan player_ids" in message for message in validation["blocking_errors"])
    assert any("Missing required sheet 'player_stats'" in message for message in validation["blocking_errors"])
    assert any("Missing warning-only sheet 'heatmaps'" in message for message in validation["warnings"])


def test_validate_dataset_contract_relaxes_required_sheet_gaps_for_legacy_seasons(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "curated"
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    _write_required_contract_tables(dataset_dir)

    matches = pd.DataFrame({"match_id": [1], "home_score": [1], "away_score": [0]})
    teams = pd.DataFrame({"team_id": [10], "short_name": ["Equipo A"]})
    players = pd.DataFrame({"player_id": [100], "name": ["Jugador Uno"]})
    player_match = pd.DataFrame({"match_id": [1], "player_id": [100], "team_id": [10]})

    matches.to_parquet(dataset_dir / "matches.parquet", index=False)
    teams.to_parquet(dataset_dir / "teams.parquet", index=False)
    players.to_parquet(dataset_dir / "players.parquet", index=False)
    player_match.to_parquet(dataset_dir / "player_match.parquet", index=False)

    coverage = pd.DataFrame(
        {
            "match_id": [1],
            "has_player_stats": [False],
            "has_team_stats": [False],
            "has_average_positions": [False],
            "has_heatmaps": [False],
            "has_shotmap": [False],
            "has_momentum": [False],
        }
    )
    coverage.to_parquet(staging_dir / "sheet_coverage.parquet", index=False)

    validation = validate_dataset_contract(
        dataset_dir=dataset_dir,
        master_matches=pd.DataFrame({"match_id": [1]}),
        staging_dir=staging_dir,
        reference_dir=None,
        season=2023,
    )

    assert validation["status"] == "passed"
    assert not validation["blocking_errors"]
    assert any("Missing legacy non-blocking sheet 'player_stats'" in message for message in validation["warnings"])


def test_validate_dataset_contract_requires_finished_player_stats_for_fantasy_bridge(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "curated"
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    _write_required_contract_tables(dataset_dir)

    pd.DataFrame({"match_id": [1], "status": ["Finalizado"], "home_score": [1], "away_score": [0]}).to_parquet(
        dataset_dir / "matches.parquet",
        index=False,
    )
    pd.DataFrame({"team_id": [10], "short_name": ["Equipo A"]}).to_parquet(dataset_dir / "teams.parquet", index=False)
    pd.DataFrame({"player_id": [100], "name": ["Jugador Uno"]}).to_parquet(dataset_dir / "players.parquet", index=False)
    pd.DataFrame({"match_id": [1], "player_id": [100], "team_id": [10]}).to_parquet(dataset_dir / "player_match.parquet", index=False)

    pd.DataFrame(
        {
            "match_id": [1],
            "has_player_stats": [False],
            "has_team_stats": [False],
            "has_average_positions": [False],
            "has_heatmaps": [False],
            "has_shotmap": [False],
            "has_momentum": [False],
        }
    ).to_parquet(staging_dir / "sheet_coverage.parquet", index=False)

    validation = validate_dataset_contract(
        dataset_dir=dataset_dir,
        master_matches=pd.DataFrame({"match_id": [1], "status": ["Finalizado"], "home_score": [1], "away_score": [0]}),
        staging_dir=staging_dir,
        reference_dir=None,
        season=2026,
        source_mode=FANTASY_SOURCE_MODE,
    )

    assert validation["status"] == "failed"
    assert any("Missing required finished-match sheet 'player_stats'" in message for message in validation["blocking_errors"])
    assert not any("Fantasy admin bridge validation mode enabled for season 2026" in message for message in validation["warnings"])


def test_validate_dataset_contract_allows_schedule_only_fantasy_bridge_release(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "curated"
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    _write_required_contract_tables(dataset_dir)

    pd.DataFrame({"match_id": [1], "status": ["Programado"], "home_score": [pd.NA], "away_score": [pd.NA]}).to_parquet(
        dataset_dir / "matches.parquet",
        index=False,
    )
    pd.DataFrame({"team_id": [10], "short_name": ["Equipo A"]}).to_parquet(dataset_dir / "teams.parquet", index=False)
    pd.DataFrame().to_parquet(dataset_dir / "players.parquet", index=False)
    pd.DataFrame().to_parquet(dataset_dir / "player_match.parquet", index=False)

    pd.DataFrame(
        {
            "match_id": [1],
            "has_player_stats": [False],
            "has_team_stats": [False],
            "has_average_positions": [False],
            "has_heatmaps": [False],
            "has_shotmap": [False],
            "has_momentum": [False],
        }
    ).to_parquet(staging_dir / "sheet_coverage.parquet", index=False)

    validation = validate_dataset_contract(
        dataset_dir=dataset_dir,
        master_matches=pd.DataFrame({"match_id": [1], "status": ["Programado"], "home_score": [pd.NA], "away_score": [pd.NA]}),
        staging_dir=staging_dir,
        reference_dir=None,
        season=2026,
        source_mode=FANTASY_SOURCE_MODE,
    )

    assert validation["status"] == "passed"
    assert not validation["blocking_errors"]
    assert any("schedule-only" in message for message in validation["warnings"])


def test_validate_dataset_contract_allows_partial_advanced_layers_for_fantasy_bridge(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "curated"
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    _write_required_contract_tables(dataset_dir)

    pd.DataFrame({"match_id": [1], "status": ["Finalizado"], "home_score": [1], "away_score": [0]}).to_parquet(
        dataset_dir / "matches.parquet",
        index=False,
    )
    pd.DataFrame({"team_id": [10], "short_name": ["Equipo A"]}).to_parquet(dataset_dir / "teams.parquet", index=False)
    pd.DataFrame({"player_id": [100], "name": ["Jugador Uno"]}).to_parquet(dataset_dir / "players.parquet", index=False)
    pd.DataFrame({"match_id": [1], "player_id": [100], "team_id": [10], "goals": [1]}).to_parquet(
        dataset_dir / "player_match.parquet",
        index=False,
    )

    pd.DataFrame(
        {
            "match_id": [1],
            "has_player_stats": [True],
            "has_team_stats": [False],
            "has_average_positions": [False],
            "has_heatmaps": [False],
            "has_shotmap": [False],
            "has_momentum": [False],
        }
    ).to_parquet(staging_dir / "sheet_coverage.parquet", index=False)

    validation = validate_dataset_contract(
        dataset_dir=dataset_dir,
        master_matches=pd.DataFrame({"match_id": [1], "status": ["Finalizado"], "home_score": [1], "away_score": [0]}),
        staging_dir=staging_dir,
        reference_dir=None,
        season=2026,
        source_mode=FANTASY_SOURCE_MODE,
    )

    assert validation["status"] == "passed"
    assert not validation["blocking_errors"]
    assert any("Missing bridge non-blocking sheet 'team_stats'" in message for message in validation["warnings"])
    assert any("Missing warning-only sheet 'shotmap'" in message for message in validation["warnings"])


def test_validate_dataset_contract_allows_current_season_partial_sofascore(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "curated"
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    _write_required_contract_tables(dataset_dir)

    pd.DataFrame({"match_id": [1], "status": ["Finalizado"], "home_score": [1], "away_score": [0]}).to_parquet(
        dataset_dir / "matches.parquet",
        index=False,
    )
    pd.DataFrame({"team_id": [10], "short_name": ["Equipo A"]}).to_parquet(dataset_dir / "teams.parquet", index=False)
    pd.DataFrame().to_parquet(dataset_dir / "players.parquet", index=False)
    pd.DataFrame().to_parquet(dataset_dir / "player_match.parquet", index=False)

    pd.DataFrame(
        {
            "match_id": [1],
            "has_player_stats": [False],
            "has_team_stats": [False],
            "has_average_positions": [False],
            "has_heatmaps": [False],
            "has_shotmap": [False],
            "has_momentum": [False],
        }
    ).to_parquet(staging_dir / "sheet_coverage.parquet", index=False)

    validation = validate_dataset_contract(
        dataset_dir=dataset_dir,
        master_matches=pd.DataFrame({"match_id": [1], "status": ["Finalizado"], "home_score": [1], "away_score": [0]}),
        staging_dir=staging_dir,
        reference_dir=None,
        season=2026,
        source_mode="sofascore",
    )

    assert validation["status"] == "passed"
    assert not validation["blocking_errors"]
    assert any("Missing current-season non-blocking sheet 'player_stats'" in message for message in validation["warnings"])


def test_validate_dataset_contract_appends_optional_backfill_classification(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "curated"
    staging_dir = tmp_path / "staging"
    raw_dir = tmp_path / "raw" / "optional_backfill"
    staging_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    _write_required_contract_tables(dataset_dir)

    pd.DataFrame({"match_id": [1], "home_score": [1], "away_score": [0]}).to_parquet(dataset_dir / "matches.parquet", index=False)
    pd.DataFrame({"team_id": [10], "short_name": ["Equipo A"]}).to_parquet(dataset_dir / "teams.parquet", index=False)
    pd.DataFrame({"player_id": [100], "name": ["Jugador Uno"]}).to_parquet(dataset_dir / "players.parquet", index=False)
    pd.DataFrame({"match_id": [1], "player_id": [100], "team_id": [10]}).to_parquet(dataset_dir / "player_match.parquet", index=False)

    pd.DataFrame(
        {
            "match_id": [1],
            "has_player_stats": [True],
            "has_team_stats": [True],
            "has_average_positions": [True],
            "has_heatmaps": [True],
            "has_shotmap": [False],
            "has_momentum": [False],
        }
    ).to_parquet(staging_dir / "sheet_coverage.parquet", index=False)

    (raw_dir / "latest_report.json").write_text(
        json.dumps(
            {
                "results": [
                    {"sheet_key": "shotmap", "match_id": 1, "classification": "missing_from_source"},
                    {"sheet_key": "momentum", "match_id": 1, "classification": "retryable_error"},
                ]
            }
        ),
        encoding="utf-8",
    )

    validation = validate_dataset_contract(
        dataset_dir=dataset_dir,
        master_matches=pd.DataFrame({"match_id": [1]}),
        staging_dir=staging_dir,
        reference_dir=None,
        season=2025,
    )

    assert any("backfill: missing_from_source=1" in message for message in validation["warnings"])
    assert any("backfill: retryable_error=1" in message for message in validation["warnings"])


def test_stringify_if_mixed_objects_normalizes_numeric_and_mixed_id_columns() -> None:
    frame = pd.DataFrame(
        {
            "player_id": ["922877", 1018556, "Ángel Zamudio"],
            "home": ["50%", 3, "1"],
            "name": ["Jugador Uno", "Jugador Dos", "Jugador Tres"],
        }
    )

    result = stringify_if_mixed_objects(frame)

    assert result["player_id"].tolist() == ["922877", "1018556", "Ángel Zamudio"]
    assert result["home"].tolist() == ["50%", "3", "1"]
    assert result["name"].tolist() == ["Jugador Uno", "Jugador Dos", "Jugador Tres"]


def test_publish_release_atomically_swaps_current_dir(tmp_path: Path) -> None:
    dashboard_dir = tmp_path / "dashboard"
    release_dir = dashboard_dir / "releases" / "20260403_010101"
    current_dir = dashboard_dir / "current"

    release_dir.mkdir(parents=True, exist_ok=True)
    current_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "matches.parquet").write_text("new", encoding="utf-8")
    (current_dir / "matches.parquet").write_text("old", encoding="utf-8")

    publish_release_atomically(release_dir, current_dir)

    assert (current_dir / "matches.parquet").read_text(encoding="utf-8") == "new"
    assert not (dashboard_dir / "_current_20260403_010101").exists()
    assert not (dashboard_dir / "_current_backup_20260403_010101").exists()
