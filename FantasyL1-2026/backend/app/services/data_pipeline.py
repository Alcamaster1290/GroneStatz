from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List, Optional

import duckdb
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.services.fantasy import get_or_create_season

logger = logging.getLogger(__name__)

EXPECTED_PARQUETS = {
    "matches.parquet": "matches",
    "teams.parquet": "teams",
    "players.parquet": "players",
    "players_fantasy.parquet": "players_fantasy",
    "player_match.parquet": "player_match",
    "player_totals.parquet": "player_totals",
    "player_team.parquet": "player_team",
    "player_transfer.parquet": "player_transfer",
    "team_stats.parquet": "team_stats",
}

REQUIRED_PLAYERS_FANTASY_COLS = {"player_id", "name", "position", "team_id", "price"}


def _get_columns(con: duckdb.DuckDBPyConnection, source: str) -> List[str]:
    rows = con.execute(f"DESCRIBE {source}").fetchall()
    return [row[0] for row in rows]


def _pick_column(columns: Iterable[str], candidates: List[str]) -> Optional[str]:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def ingest_parquets_to_duckdb(settings: Settings) -> None:
    parquet_dir = Path(settings.PARQUET_DIR)
    if not parquet_dir.exists():
        raise FileNotFoundError(f"parquet_dir_not_found: {parquet_dir}")

    duckdb_path = Path(settings.DUCKDB_PATH)
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        con = duckdb.connect(str(duckdb_path))
    except UnicodeDecodeError:
        if duckdb_path.exists():
            logger.warning("duckdb_unicode_error_recreate %s", duckdb_path)
            duckdb_path.unlink(missing_ok=True)
        con = duckdb.connect(str(duckdb_path))

    for parquet_name, table_name in EXPECTED_PARQUETS.items():
        parquet_path = parquet_dir / parquet_name
        if not parquet_path.exists():
            if parquet_name == "players_fantasy.parquet":
                raise FileNotFoundError("players_fantasy.parquet_missing")
            logger.warning("missing_parquet: %s", parquet_path)
            continue

        if parquet_name == "players_fantasy.parquet":
            columns = _get_columns(con, f"SELECT * FROM read_parquet('{parquet_path.as_posix()}')")
            missing = REQUIRED_PLAYERS_FANTASY_COLS - set(columns)
            if missing:
                raise ValueError(f"players_fantasy_missing_columns: {sorted(missing)}")

        con.execute(
            f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet('{parquet_path.as_posix()}')"
        )
        logger.info("ingested %s", parquet_name)

    con.close()


def _upsert_teams(db: Session, rows: List[dict]) -> None:
    if not rows:
        return
    db.execute(
        text(
            """
            INSERT INTO teams (id, name_short, name_full)
            VALUES (:id, :name_short, :name_full)
            ON CONFLICT (id) DO UPDATE
            SET name_short = EXCLUDED.name_short,
                name_full = EXCLUDED.name_full
            """
        ),
        rows,
    )


def _upsert_players(db: Session, rows: List[dict]) -> None:
    if not rows:
        return
    db.execute(
        text(
            """
            INSERT INTO players_catalog (
                player_id, name, short_name, position, team_id, price_current,
                minutesplayed, matches_played, goals, assists, saves, fouls, updated_at
            )
            VALUES (
                :player_id, :name, :short_name, :position, :team_id, :price_current,
                :minutesplayed, :matches_played, :goals, :assists, :saves, :fouls, NOW()
            )
            ON CONFLICT (player_id) DO UPDATE
            SET name = EXCLUDED.name,
                short_name = EXCLUDED.short_name,
                position = EXCLUDED.position,
                team_id = EXCLUDED.team_id,
                price_current = EXCLUDED.price_current,
                minutesplayed = EXCLUDED.minutesplayed,
                matches_played = EXCLUDED.matches_played,
                goals = EXCLUDED.goals,
                assists = EXCLUDED.assists,
                saves = EXCLUDED.saves,
                fouls = EXCLUDED.fouls,
                updated_at = NOW()
            """
        ),
        rows,
    )

def _prune_missing_players(db: Session, player_ids: List[int]) -> None:
    if not player_ids:
        logger.warning("players_fantasy_empty_skip_prune")
        return
    ids_param = bindparam("ids", expanding=True)
    params = {"ids": player_ids}

    # Remove references first to avoid FK violations.
    db.execute(
        text("DELETE FROM fantasy_team_players WHERE player_id NOT IN :ids").bindparams(ids_param),
        params,
    )
    db.execute(
        text("DELETE FROM fantasy_transfers WHERE out_player_id NOT IN :ids OR in_player_id NOT IN :ids").bindparams(
            ids_param
        ),
        params,
    )
    db.execute(
        text("DELETE FROM price_history WHERE player_id NOT IN :ids").bindparams(ids_param),
        params,
    )
    db.execute(
        text("DELETE FROM price_movements WHERE player_id NOT IN :ids").bindparams(ids_param),
        params,
    )
    db.execute(
        text("DELETE FROM points_round WHERE player_id NOT IN :ids").bindparams(ids_param),
        params,
    )
    db.execute(
        text("DELETE FROM player_round_stats WHERE player_id NOT IN :ids").bindparams(ids_param),
        params,
    )
    db.execute(
        text("DELETE FROM player_match_stats WHERE player_id NOT IN :ids").bindparams(ids_param),
        params,
    )
    db.execute(
        text("UPDATE fantasy_lineup_slots SET player_id = NULL WHERE player_id NOT IN :ids").bindparams(ids_param),
        params,
    )
    db.execute(
        text("DELETE FROM players_catalog WHERE player_id NOT IN :ids").bindparams(ids_param),
        params,
    )


def _upsert_fixtures(db: Session, rows: List[dict]) -> None:
    if not rows:
        return
    db.execute(
        text(
            """
            INSERT INTO fixtures (
                season_id, round_id, match_id, home_team_id, away_team_id, kickoff_at, stadium, city, status
            )
            VALUES (
                :season_id, :round_id, :match_id, :home_team_id, :away_team_id, :kickoff_at, :stadium, :city, :status
            )
            ON CONFLICT (match_id) DO UPDATE
            SET season_id = EXCLUDED.season_id,
                round_id = EXCLUDED.round_id,
                home_team_id = EXCLUDED.home_team_id,
                away_team_id = EXCLUDED.away_team_id,
                kickoff_at = EXCLUDED.kickoff_at,
                stadium = EXCLUDED.stadium,
                city = EXCLUDED.city
            """
        ),
        rows,
    )


def sync_duckdb_to_postgres(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    duckdb_path = Path(settings.DUCKDB_PATH)
    if not duckdb_path.exists():
        raise FileNotFoundError(f"duckdb_not_found: {duckdb_path}")

    con = duckdb.connect(str(duckdb_path), read_only=True)
    db = SessionLocal()

    try:
        season = get_or_create_season(db)

        # Teams
        team_cols = _get_columns(con, "teams")
        team_id_col = _pick_column(team_cols, ["team_id", "id"])
        if not team_id_col:
            raise ValueError("teams_missing_team_id")
        name_short_col = _pick_column(team_cols, ["name_short", "short_name", "abbr", "code", "name"])
        name_full_col = _pick_column(team_cols, ["name_full", "name", "team_name"])

        name_short_expr = name_short_col or "NULL"
        name_full_expr = name_full_col or name_short_col or "NULL"

        team_rows = con.execute(
            f"SELECT {team_id_col} as id, {name_short_expr} as name_short, {name_full_expr} as name_full FROM teams"
        ).fetchall()
        teams_payload = [
            {"id": row[0], "name_short": row[1], "name_full": row[2]} for row in team_rows
        ]
        _upsert_teams(db, teams_payload)

        # Ensure every team_id present in players_fantasy exists in teams (avoid FK violations).
        fantasy_team_ids = {
            row[0]
            for row in con.execute("SELECT DISTINCT team_id FROM players_fantasy").fetchall()
            if row[0] is not None
        }
        known_team_ids = {row[0] for row in team_rows if row[0] is not None}
        missing_team_ids = sorted(fantasy_team_ids - known_team_ids)
        if missing_team_ids:
            _upsert_teams(
                db,
                [{"id": team_id, "name_short": None, "name_full": None} for team_id in missing_team_ids],
            )

        # Players catalog
        player_cols = _get_columns(con, "players_fantasy")
        missing = REQUIRED_PLAYERS_FANTASY_COLS - set(player_cols)
        if missing:
            raise ValueError(f"players_fantasy_missing_columns: {sorted(missing)}")

        short_name_col = _pick_column(
            player_cols, ["short_name", "shortName", "shortname", "SHORT_NAME", "SHORTNAME"]
        )
        short_name_expr = short_name_col or "NULL"

        player_rows = con.execute(
            f"SELECT player_id, name, position, team_id, price, {short_name_expr} as short_name FROM players_fantasy"
        ).fetchall()
        players_payload = [
            {
                "player_id": row[0],
                "name": row[1],
                "position": row[2],
                "team_id": row[3],
                "price_current": float(row[4]),
                "short_name": row[5],
                "minutesplayed": 0,
                "matches_played": 0,
                "goals": 0,
                "assists": 0,
                "saves": 0,
                "fouls": 0,
            }
            for row in player_rows
        ]
        _upsert_players(db, players_payload)
        _prune_missing_players(db, [row[0] for row in player_rows])

        # Fixtures are not synced from parquet. They are managed via admin.
        db.commit()
    finally:
        db.close()
        con.close()
