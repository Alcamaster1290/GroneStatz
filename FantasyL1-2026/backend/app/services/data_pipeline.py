from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import duckdb
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.services.fantasy import ensure_round, get_or_create_season

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


def _upsert_fixtures(db: Session, rows: List[dict]) -> None:
    if not rows:
        return
    db.execute(
        text(
            """
            INSERT INTO fixtures (
                season_id, round_id, match_id, home_team_id, away_team_id, kickoff_at, stadium, city
            )
            VALUES (
                :season_id, :round_id, :match_id, :home_team_id, :away_team_id, :kickoff_at, :stadium, :city
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

        # Fixtures
        match_cols = _get_columns(con, "matches")
        match_id_col = _pick_column(match_cols, ["match_id", "id"])
        round_col = _pick_column(match_cols, ["round_number", "round", "round_no"])
        if not match_id_col or not round_col:
            raise ValueError("matches_missing_match_id_or_round")

        home_col = _pick_column(match_cols, ["home_team_id", "home_id", "home_team"])
        away_col = _pick_column(match_cols, ["away_team_id", "away_id", "away_team"])
        kickoff_col = _pick_column(match_cols, ["kickoff_at", "kickoff", "datetime", "date", "match_date"])
        stadium_col = _pick_column(match_cols, ["stadium", "venue"])
        city_col = _pick_column(match_cols, ["city"])

        kickoff_expr = kickoff_col or "NULL"
        stadium_expr = stadium_col or "NULL"
        city_expr = city_col or "NULL"
        home_expr = home_col or "NULL"
        away_expr = away_col or "NULL"

        match_rows = con.execute(
            f"SELECT {match_id_col} as match_id, {round_col} as round_number, {home_expr} as home_team_id, {away_expr} as away_team_id, {kickoff_expr} as kickoff_at, {stadium_expr} as stadium, {city_expr} as city FROM matches"
        ).fetchall()

        rounds_map = {}
        fixtures_payload = []
        for row in match_rows:
            round_number = int(row[1])
            if round_number not in rounds_map:
                round_obj = ensure_round(db, season.id, round_number)
                rounds_map[round_number] = round_obj.id
            kickoff = row[4]
            if kickoff is not None and not isinstance(kickoff, datetime):
                try:
                    kickoff = datetime.fromisoformat(str(kickoff))
                except ValueError:
                    kickoff = None
            fixtures_payload.append(
                {
                    "season_id": season.id,
                    "round_id": rounds_map[round_number],
                    "match_id": row[0],
                    "home_team_id": row[2],
                    "away_team_id": row[3],
                    "kickoff_at": kickoff,
                    "stadium": row[5],
                    "city": row[6],
                }
            )

        _upsert_fixtures(db, fixtures_payload)
        db.commit()
    finally:
        db.close()
        con.close()
