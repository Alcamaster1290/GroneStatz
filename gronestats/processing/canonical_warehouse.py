from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from gronestats.processing.fantasy_export import FANTASY_EXPORT_TABLES, build_fantasy_export_bundle


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    pandas_dtype: str
    duckdb_type: str


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: tuple[ColumnSpec, ...]

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)


def _string(name: str) -> ColumnSpec:
    return ColumnSpec(name=name, pandas_dtype="string", duckdb_type="TEXT")


def _int(name: str) -> ColumnSpec:
    return ColumnSpec(name=name, pandas_dtype="Int64", duckdb_type="BIGINT")


def _float(name: str) -> ColumnSpec:
    return ColumnSpec(name=name, pandas_dtype="float64", duckdb_type="DOUBLE")


def _bool(name: str) -> ColumnSpec:
    return ColumnSpec(name=name, pandas_dtype="boolean", duckdb_type="BOOLEAN")


def _datetime(name: str) -> ColumnSpec:
    return ColumnSpec(name=name, pandas_dtype="datetime64[ns]", duckdb_type="TIMESTAMP")


CANONICAL_SCHEMAS: dict[str, TableSchema] = {
    "matches_canonical": TableSchema(
        "matches_canonical",
        (
            _int("season_year"),
            _int("match_id"),
            _int("round_number"),
            _string("tournament"),
            _string("status"),
            _int("home_id"),
            _int("away_id"),
            _string("home"),
            _string("away"),
            _int("home_score"),
            _int("away_score"),
            _string("resultado_final"),
            _string("fecha"),
            _string("estadio"),
            _string("ciudad"),
            _string("arbitro"),
        ),
    ),
    "teams_canonical": TableSchema(
        "teams_canonical",
        (
            _int("season_year"),
            _int("team_id"),
            _string("short_name"),
            _string("full_name"),
            _string("team_colors"),
            _bool("is_altitude_team"),
            _string("competitiveness_level"),
            _int("stadium_id"),
            _string("stadium_name_city"),
            _string("province"),
            _string("department"),
            _string("region"),
        ),
    ),
    "players_canonical": TableSchema(
        "players_canonical",
        (
            _int("season_year"),
            _int("player_id"),
            _string("name"),
            _string("short_name"),
            _string("position"),
            _int("team_id"),
            _string("dateofbirth"),
            _float("age_jan_2026"),
        ),
    ),
    "player_identity_canonical": TableSchema(
        "player_identity_canonical",
        (
            _int("season_year"),
            _int("player_id"),
            _int("team_id"),
            _string("name"),
            _string("short_name"),
            _string("position"),
            _int("shirt_number"),
            _string("dateofbirth"),
            _float("age_jan_2026"),
            _int("last_match_id"),
            _datetime("last_seen_at"),
        ),
    ),
    "player_match_canonical": TableSchema(
        "player_match_canonical",
        (
            _int("season_year"),
            _int("match_id"),
            _int("player_id"),
            _string("name"),
            _int("team_id"),
            _string("position"),
            _int("minutesplayed"),
            _int("goals"),
            _int("assists"),
            _int("yellowcards"),
            _int("redcards"),
            _int("saves"),
            _int("fouls"),
            _int("penaltywon"),
            _int("penaltysave"),
            _int("penaltyconceded"),
            _float("rating"),
        ),
    ),
    "player_totals_season_canonical": TableSchema(
        "player_totals_season_canonical",
        (
            _int("season_year"),
            _int("player_id"),
            _int("goals"),
            _int("assists"),
            _int("saves"),
            _int("fouls"),
            _int("minutesplayed"),
            _int("penaltywon"),
            _int("penaltysave"),
            _int("penaltyconceded"),
            _int("matches_played"),
        ),
    ),
    "team_stats_canonical": TableSchema(
        "team_stats_canonical",
        (
            _int("season_year"),
            _string("NAME"),
            _string("HOME"),
            _string("AWAY"),
            _int("COMPARECODE"),
            _string("STATISTICSTYPE"),
            _string("VALUETYPE"),
            _float("HOMEVALUE"),
            _float("AWAYVALUE"),
            _int("RENDERTYPE"),
            _string("KEY"),
            _string("PERIOD"),
            _string("GROUP"),
            _float("HOMETOTAL"),
            _float("AWAYTOTAL"),
            _int("MATCH_ID"),
        ),
    ),
    "average_positions_canonical": TableSchema(
        "average_positions_canonical",
        (
            _int("season_year"),
            _int("match_id"),
            _int("player_id"),
            _int("team_id"),
            _string("team_name"),
            _string("name"),
            _int("shirt_number"),
            _string("position"),
            _float("average_x"),
            _float("average_y"),
            _int("points_count"),
            _bool("is_starter"),
        ),
    ),
    "heatmap_points_canonical": TableSchema(
        "heatmap_points_canonical",
        (
            _int("season_year"),
            _int("match_id"),
            _int("player_id"),
            _int("team_id"),
            _string("team_name"),
            _string("name"),
            _float("x"),
            _float("y"),
        ),
    ),
    "shot_events_canonical": TableSchema(
        "shot_events_canonical",
        (
            _int("season_year"),
            _int("match_id"),
            _int("shot_id"),
            _int("player_id"),
            _bool("is_home"),
            _string("shot_type"),
            _string("situation"),
            _string("body_part"),
            _string("goal_mouth_location"),
            _string("goal_mouth_coordinates"),
            _int("time"),
            _float("added_time"),
            _int("time_seconds"),
            _string("incident_type"),
            _string("block_coordinates"),
            _string("goal_type"),
            _string("name"),
            _string("short_name"),
            _string("position"),
            _int("jersey_number"),
            _float("x"),
            _float("y"),
            _float("z"),
            _int("team_id"),
            _string("team_name"),
        ),
    ),
    "match_momentum_canonical": TableSchema(
        "match_momentum_canonical",
        (
            _int("season_year"),
            _int("match_id"),
            _float("minute"),
            _float("value"),
            _string("dominant_side"),
        ),
    ),
}


DASHBOARD_EXPORT_SCHEMAS: dict[str, TableSchema] = {
    "matches": TableSchema(
        "matches",
        (
            _int("match_id"),
            _int("round_number"),
            _string("tournament"),
            _int("season"),
            _string("status"),
            _int("home_id"),
            _int("away_id"),
            _string("home"),
            _string("away"),
            _int("home_score"),
            _int("away_score"),
            _string("resultado_final"),
            _string("fecha"),
            _string("estadio"),
            _string("ciudad"),
            _string("arbitro"),
        ),
    ),
    "teams": TableSchema("teams", CANONICAL_SCHEMAS["teams_canonical"].columns[1:]),
    "players": TableSchema("players", CANONICAL_SCHEMAS["players_canonical"].columns[1:]),
    "player_identity": TableSchema(
        "player_identity",
        (
            _int("player_id"),
            _string("name"),
            _string("short_name"),
            _string("position"),
            _int("team_id"),
            _string("dateofbirth"),
            _float("age_jan_2026"),
            _int("last_match_id"),
            _datetime("last_seen_at"),
        ),
    ),
    "player_match": TableSchema("player_match", CANONICAL_SCHEMAS["player_match_canonical"].columns[1:]),
    "player_totals_full_season": TableSchema(
        "player_totals_full_season",
        CANONICAL_SCHEMAS["player_totals_season_canonical"].columns[1:],
    ),
    "team_stats": TableSchema("team_stats", CANONICAL_SCHEMAS["team_stats_canonical"].columns[1:]),
    "average_positions": TableSchema("average_positions", CANONICAL_SCHEMAS["average_positions_canonical"].columns[1:]),
    "heatmap_points": TableSchema("heatmap_points", CANONICAL_SCHEMAS["heatmap_points_canonical"].columns[1:]),
    "shot_events": TableSchema("shot_events", CANONICAL_SCHEMAS["shot_events_canonical"].columns[1:]),
    "match_momentum": TableSchema("match_momentum", CANONICAL_SCHEMAS["match_momentum_canonical"].columns[1:]),
}


FANTASY_EXPORT_SCHEMAS: dict[str, TableSchema] = {
    "matches": DASHBOARD_EXPORT_SCHEMAS["matches"],
    "teams": DASHBOARD_EXPORT_SCHEMAS["teams"],
    "players": DASHBOARD_EXPORT_SCHEMAS["players"],
    "player_match": DASHBOARD_EXPORT_SCHEMAS["player_match"],
    "player_totals": TableSchema("player_totals", DASHBOARD_EXPORT_SCHEMAS["player_totals_full_season"].columns),
    "team_stats": DASHBOARD_EXPORT_SCHEMAS["team_stats"],
    "player_team": TableSchema(
        "player_team",
        (
            _int("player_id"),
            _int("team_id"),
            _string("name"),
            _string("position"),
        ),
    ),
    "player_transfer": TableSchema(
        "player_transfer",
        (
            _int("player_id"),
            _int("team_id"),
            _string("name"),
            _string("short_name"),
            _string("position"),
            _string("team_name"),
        ),
    ),
    "players_fantasy": TableSchema(
        "players_fantasy",
        (
            _int("player_id"),
            _string("name"),
            _string("short_name"),
            _string("position"),
            _float("price"),
            _int("team_id"),
            _int("minutesplayed"),
            _int("matches_played"),
            _int("goals"),
            _int("assists"),
            _int("saves"),
            _int("fouls"),
            _int("penaltywon"),
            _int("penaltysave"),
            _int("penaltyconceded"),
            _float("goals_pm"),
            _float("assists_pm"),
            _float("saves_pm"),
            _float("fouls_pm"),
            _float("penaltywon_pm"),
            _float("penaltysave_pm"),
            _float("penaltyconceded_pm"),
        ),
    ),
}


CANONICAL_TABLES = tuple(CANONICAL_SCHEMAS.keys())


def _load_duckdb():
    try:
        import duckdb  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in runtime, not unit tests
        raise RuntimeError(
            "duckdb is required for the canonical warehouse. Install `duckdb==0.10.2` in the active Python environment."
        ) from exc
    return duckdb


def empty_typed_frame(schema: TableSchema) -> pd.DataFrame:
    return pd.DataFrame({column.name: pd.Series(dtype=column.pandas_dtype) for column in schema.columns})


def _normalize_string(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip()
    return text.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "NaT": pd.NA})


def _normalize_boolean(series: pd.Series) -> pd.Series:
    if str(series.dtype) == "boolean":
        return series.astype("boolean")
    lowered = series.astype("string").str.strip().str.lower()
    mapped = lowered.map(
        {
            "true": True,
            "false": False,
            "1": True,
            "0": False,
            "yes": True,
            "no": False,
            "home": True,
            "away": False,
        }
    )
    numeric = pd.to_numeric(series, errors="coerce")
    mapped.loc[numeric.notna()] = numeric.loc[numeric.notna()].astype(int).astype(bool)
    return mapped.astype("boolean")


def _normalize_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").astype("datetime64[ns]")


def _normalize_numeric(series: pd.Series, dtype: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if dtype == "Int64":
        return numeric.astype("Int64")
    return numeric.astype(dtype)


def cast_frame_to_schema(frame: pd.DataFrame | None, schema: TableSchema) -> pd.DataFrame:
    if frame is None:
        return empty_typed_frame(schema)
    work = frame.copy()
    for column in schema.columns:
        if column.name not in work.columns:
            work[column.name] = pd.Series(pd.NA, index=work.index)
    work = work.loc[:, list(schema.column_names)].copy()
    for column in schema.columns:
        if column.pandas_dtype in {"Int64", "float64"}:
            work[column.name] = _normalize_numeric(work[column.name], column.pandas_dtype)
        elif column.pandas_dtype == "boolean":
            work[column.name] = _normalize_boolean(work[column.name])
        elif column.pandas_dtype == "datetime64[ns]":
            work[column.name] = _normalize_datetime(work[column.name])
        else:
            work[column.name] = _normalize_string(work[column.name])
    return work


def _with_season(frame: pd.DataFrame, season: int) -> pd.DataFrame:
    work = frame.copy()
    work["season_year"] = season
    return work


def build_canonical_tables(curated_tables: dict[str, pd.DataFrame], season: int) -> dict[str, pd.DataFrame]:
    matches = _with_season(curated_tables.get("matches", pd.DataFrame()).copy(), season)
    if "status" not in matches.columns:
        matches["status"] = pd.NA

    player_identity = _with_season(curated_tables.get("player_identity", pd.DataFrame()).copy(), season)
    if "shirt_number" not in player_identity.columns:
        player_identity["shirt_number"] = pd.NA

    canonical_tables = {
        "matches_canonical": cast_frame_to_schema(matches, CANONICAL_SCHEMAS["matches_canonical"]),
        "teams_canonical": cast_frame_to_schema(
            _with_season(curated_tables.get("teams", pd.DataFrame()).copy(), season),
            CANONICAL_SCHEMAS["teams_canonical"],
        ),
        "players_canonical": cast_frame_to_schema(
            _with_season(curated_tables.get("players", pd.DataFrame()).copy(), season),
            CANONICAL_SCHEMAS["players_canonical"],
        ),
        "player_identity_canonical": cast_frame_to_schema(
            player_identity,
            CANONICAL_SCHEMAS["player_identity_canonical"],
        ),
        "player_match_canonical": cast_frame_to_schema(
            _with_season(curated_tables.get("player_match", pd.DataFrame()).copy(), season),
            CANONICAL_SCHEMAS["player_match_canonical"],
        ),
        "player_totals_season_canonical": cast_frame_to_schema(
            _with_season(curated_tables.get("player_totals_full_season", pd.DataFrame()).copy(), season),
            CANONICAL_SCHEMAS["player_totals_season_canonical"],
        ),
        "team_stats_canonical": cast_frame_to_schema(
            _with_season(curated_tables.get("team_stats", pd.DataFrame()).copy(), season),
            CANONICAL_SCHEMAS["team_stats_canonical"],
        ),
        "average_positions_canonical": cast_frame_to_schema(
            _with_season(curated_tables.get("average_positions", pd.DataFrame()).copy(), season),
            CANONICAL_SCHEMAS["average_positions_canonical"],
        ),
        "heatmap_points_canonical": cast_frame_to_schema(
            _with_season(curated_tables.get("heatmap_points", pd.DataFrame()).copy(), season),
            CANONICAL_SCHEMAS["heatmap_points_canonical"],
        ),
        "shot_events_canonical": cast_frame_to_schema(
            _with_season(curated_tables.get("shot_events", pd.DataFrame()).copy(), season),
            CANONICAL_SCHEMAS["shot_events_canonical"],
        ),
        "match_momentum_canonical": cast_frame_to_schema(
            _with_season(curated_tables.get("match_momentum", pd.DataFrame()).copy(), season),
            CANONICAL_SCHEMAS["match_momentum_canonical"],
        ),
    }
    return canonical_tables


def build_dashboard_bundle_from_canonical(canonical_tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    matches = canonical_tables["matches_canonical"].drop(columns=["season_year"]).copy()
    matches.insert(3, "season", canonical_tables["matches_canonical"]["season_year"])
    player_identity = canonical_tables["player_identity_canonical"].drop(columns=["season_year", "shirt_number"]).copy()

    bundle = {
        "matches": cast_frame_to_schema(matches, DASHBOARD_EXPORT_SCHEMAS["matches"]),
        "teams": cast_frame_to_schema(
            canonical_tables["teams_canonical"].drop(columns=["season_year"]),
            DASHBOARD_EXPORT_SCHEMAS["teams"],
        ),
        "players": cast_frame_to_schema(
            canonical_tables["players_canonical"].drop(columns=["season_year"]),
            DASHBOARD_EXPORT_SCHEMAS["players"],
        ),
        "player_match": cast_frame_to_schema(
            canonical_tables["player_match_canonical"].drop(columns=["season_year"]),
            DASHBOARD_EXPORT_SCHEMAS["player_match"],
        ),
        "player_totals_full_season": cast_frame_to_schema(
            canonical_tables["player_totals_season_canonical"].drop(columns=["season_year"]),
            DASHBOARD_EXPORT_SCHEMAS["player_totals_full_season"],
        ),
        "team_stats": cast_frame_to_schema(
            canonical_tables["team_stats_canonical"].drop(columns=["season_year"]),
            DASHBOARD_EXPORT_SCHEMAS["team_stats"],
        ),
        "average_positions": cast_frame_to_schema(
            canonical_tables["average_positions_canonical"].drop(columns=["season_year"]),
            DASHBOARD_EXPORT_SCHEMAS["average_positions"],
        ),
        "heatmap_points": cast_frame_to_schema(
            canonical_tables["heatmap_points_canonical"].drop(columns=["season_year"]),
            DASHBOARD_EXPORT_SCHEMAS["heatmap_points"],
        ),
        "shot_events": cast_frame_to_schema(
            canonical_tables["shot_events_canonical"].drop(columns=["season_year"]),
            DASHBOARD_EXPORT_SCHEMAS["shot_events"],
        ),
        "match_momentum": cast_frame_to_schema(
            canonical_tables["match_momentum_canonical"].drop(columns=["season_year"]),
            DASHBOARD_EXPORT_SCHEMAS["match_momentum"],
        ),
        "player_identity": cast_frame_to_schema(player_identity, DASHBOARD_EXPORT_SCHEMAS["player_identity"]),
    }
    return bundle


def build_fantasy_bundle_from_canonical(canonical_tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    dashboard_bundle = build_dashboard_bundle_from_canonical(canonical_tables)
    fantasy_seed = {
        "matches": dashboard_bundle["matches"],
        "teams": dashboard_bundle["teams"],
        "players": dashboard_bundle["players"],
        "player_match": dashboard_bundle["player_match"],
        "team_stats": dashboard_bundle["team_stats"],
    }
    raw_bundle = build_fantasy_export_bundle(fantasy_seed)
    return {
        table_name: cast_frame_to_schema(raw_bundle.get(table_name, pd.DataFrame()), FANTASY_EXPORT_SCHEMAS[table_name])
        for table_name in FANTASY_EXPORT_TABLES
    }


def _schema_sql(schema: TableSchema) -> str:
    columns = ", ".join(f'"{column.name}" {column.duckdb_type}' for column in schema.columns)
    return f'CREATE TABLE IF NOT EXISTS "{schema.name}" ({columns})'


def ensure_warehouse_tables(connection: Any) -> None:
    for schema in CANONICAL_SCHEMAS.values():
        connection.execute(_schema_sql(schema))


def upsert_canonical_tables(warehouse_path: Path, canonical_tables: dict[str, pd.DataFrame], season: int) -> dict[str, int]:
    duckdb = _load_duckdb()
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse_path))
    row_counts: dict[str, int] = {}
    try:
        ensure_warehouse_tables(con)
        for table_name, schema in CANONICAL_SCHEMAS.items():
            frame = cast_frame_to_schema(canonical_tables.get(table_name), schema)
            con.execute(f'DELETE FROM "{table_name}" WHERE season_year = ?', [int(season)])
            temp_name = f"staging_{table_name}"
            con.register(temp_name, frame)
            columns_sql = ", ".join(f'"{column}"' for column in schema.column_names)
            con.execute(
                f'INSERT INTO "{table_name}" ({columns_sql}) SELECT {columns_sql} FROM "{temp_name}"'
            )
            con.unregister(temp_name)
            row_counts[table_name] = int(len(frame))
    finally:
        con.close()
    return row_counts


def load_canonical_tables_for_season(warehouse_path: Path, season: int) -> dict[str, pd.DataFrame]:
    duckdb = _load_duckdb()
    if not warehouse_path.exists():
        raise FileNotFoundError(f"warehouse_not_found: {warehouse_path}")
    con = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        tables: dict[str, pd.DataFrame] = {}
        for table_name, schema in CANONICAL_SCHEMAS.items():
            frame = con.execute(
                f'SELECT * FROM "{table_name}" WHERE season_year = ?',
                [int(season)],
            ).fetch_df()
            tables[table_name] = cast_frame_to_schema(frame, schema)
        return tables
    finally:
        con.close()


def validate_warehouse_contract(warehouse_path: Path, season: int) -> dict[str, Any]:
    blocking_errors: list[str] = []
    warnings: list[str] = []
    row_counts: dict[str, int] = {}

    if not warehouse_path.exists():
        return {
            "status": "failed",
            "validated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "blocking_errors": [f"Warehouse not found: {warehouse_path}"],
            "warnings": [],
            "stats": {"row_counts": {}},
        }

    duckdb = _load_duckdb()
    con = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        existing_tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        for table_name, schema in CANONICAL_SCHEMAS.items():
            if table_name not in existing_tables:
                blocking_errors.append(f"Missing canonical table: {table_name}")
                continue
            info = con.execute(f'PRAGMA table_info("{table_name}")').fetch_df()
            actual_columns = info["name"].tolist()
            expected_columns = list(schema.column_names)
            if actual_columns != expected_columns:
                blocking_errors.append(
                    f"Canonical schema drift in {table_name}: expected {expected_columns}, got {actual_columns}"
                )
                continue
            row_counts[table_name] = int(
                con.execute(f'SELECT COUNT(*) FROM "{table_name}" WHERE season_year = ?', [int(season)]).fetchone()[0]
            )
        if row_counts.get("matches_canonical", 0) == 0:
            warnings.append(f"Warehouse season {season} has no matches_canonical rows.")
    finally:
        con.close()

    return {
        "status": "passed" if not blocking_errors else "failed",
        "validated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "stats": {"row_counts": row_counts},
    }
