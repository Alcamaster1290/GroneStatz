from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from gronestats.data_layout import season_layout
from gronestats.processing.fantasy_export import (
    REQUIRED_PLAYERS_FANTASY_COLS,
    build_fantasy_export_bundle,
    validate_fantasy_export_bundle,
)
from gronestats.processing.pipeline import write_table_bundle


def _sample_curated_tables() -> dict[str, pd.DataFrame]:
    matches = pd.DataFrame(
        {
            "match_id": [1, 2],
            "round_number": [1, 2],
            "home_id": [10, 20],
            "away_id": [20, 30],
            "home": ["Alianza", "Melgar"],
            "away": ["Melgar", "Cristal"],
            "home_score": [1, 0],
            "away_score": [0, 2],
        }
    )
    teams = pd.DataFrame(
        {
            "team_id": [10, 20, 30],
            "short_name": ["Alianza", "Melgar", "Cristal"],
            "full_name": ["Alianza Lima", "FBC Melgar", "Sporting Cristal"],
        }
    )
    players = pd.DataFrame(
        {
            "player_id": [101, 202],
            "name": ["Jugador Uno", "Jugador Dos"],
            "short_name": ["J. Uno", "J. Dos"],
            "position": ["F", "M"],
            "team_id": [10, 30],
            "age_jan_2026": [24.0, 22.0],
        }
    )
    player_match = pd.DataFrame(
        {
            "match_id": [1, 1, 2],
            "player_id": [101, 202, 202],
            "name": ["Jugador Uno", "Jugador Dos", "Jugador Dos"],
            "team_id": [10, 20, 30],
            "position": ["F", "M", "M"],
            "minutesplayed": [90, 45, 90],
            "goals": [1, 0, 1],
            "assists": [0, 1, 0],
            "saves": [0, 0, 0],
            "fouls": [1, 1, 2],
            "penaltywon": [0, 0, 1],
            "penaltysave": [0, 0, 0],
            "penaltyconceded": [0, 0, 0],
        }
    )
    team_stats = pd.DataFrame({"MATCH_ID": [1], "GROUP": ["Match overview"], "KEY": ["possession"], "NAME": ["Posesion"]})
    return {
        "matches": matches,
        "teams": teams,
        "players": players,
        "player_match": player_match,
        "team_stats": team_stats,
    }


def _load_fantasy_data_pipeline_module():
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("pydantic_settings")
    backend_dir = Path(__file__).resolve().parents[1] / "FantasyL1-2026" / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    os.environ.setdefault("JWT_SECRET", "test-secret")
    os.environ.setdefault("ADMIN_TOKEN", "test-admin")
    from app.services.data_pipeline import ingest_parquets_to_duckdb

    return ingest_parquets_to_duckdb


def test_build_fantasy_export_bundle_and_validate(tmp_path: Path) -> None:
    bundle = build_fantasy_export_bundle(_sample_curated_tables())

    assert set(REQUIRED_PLAYERS_FANTASY_COLS).issubset(bundle["players_fantasy"].columns)
    assert not bundle["players_fantasy"].empty
    assert not bundle["player_transfer"].empty

    write_table_bundle(tmp_path, bundle)
    validation = validate_fantasy_export_bundle(tmp_path)

    assert validation["status"] == "passed"
    assert validation["blocking_errors"] == []


def test_fantasy_backend_ingests_published_bundle(tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    ingest_parquets_to_duckdb = _load_fantasy_data_pipeline_module()
    bundle = build_fantasy_export_bundle(_sample_curated_tables())
    write_table_bundle(tmp_path, bundle)

    duckdb_path = tmp_path / "fantasy.duckdb"
    settings = SimpleNamespace(PARQUET_DIR=str(tmp_path), DUCKDB_PATH=str(duckdb_path))

    ingest_parquets_to_duckdb(settings)

    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        assert {"matches", "teams", "players", "players_fantasy", "player_match", "player_totals", "player_team", "player_transfer", "team_stats"}.issubset(tables)
        players_fantasy_cols = set(con.table("players_fantasy").columns)
        assert REQUIRED_PLAYERS_FANTASY_COLS.issubset(players_fantasy_cols)
    finally:
        con.close()


def test_fantasy_backend_ingests_real_published_multiseason_bundles(tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    ingest_parquets_to_duckdb = _load_fantasy_data_pipeline_module()

    for season in (2022, 2023, 2024, 2025, 2026):
        parquet_dir = season_layout(season, league="Liga 1 Peru").fantasy.current_dir
        duckdb_path = tmp_path / f"fantasy_{season}.duckdb"
        settings = SimpleNamespace(PARQUET_DIR=str(parquet_dir), DUCKDB_PATH=str(duckdb_path))

        ingest_parquets_to_duckdb(settings)

        con = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
            assert {"matches", "teams", "players", "players_fantasy", "player_match", "player_totals", "player_team", "player_transfer", "team_stats"}.issubset(tables)
            players_fantasy_cols = set(con.table("players_fantasy").columns)
            assert REQUIRED_PLAYERS_FANTASY_COLS.issubset(players_fantasy_cols)
        finally:
            con.close()
