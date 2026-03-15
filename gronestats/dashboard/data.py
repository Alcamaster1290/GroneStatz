from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from gronestats.dashboard.config import (
    DATA_DIR,
    DEFAULT_DASHBOARD_TOURNAMENTS,
    PLAYER_IMAGES_DIR,
    REGULAR_SEASON_MAX_ROUND,
    TEAM_IMAGES_DIR,
    TOURNAMENT_LABELS,
    TOURNAMENT_ORDER,
)
from gronestats.dashboard.models import DatasetBundle


def read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def coalesce_columns(df: pd.DataFrame, target: str, candidates: list[str]) -> pd.DataFrame:
    existing = [column for column in candidates if column in df.columns]
    if not existing:
        return df
    work = df.copy()
    if target not in work.columns:
        work[target] = pd.NA
    for column in existing:
        if column == target:
            continue
        work[target] = work[target].combine_first(work[column])
    drop_columns = [column for column in existing if column != target]
    return work.drop(columns=drop_columns, errors="ignore")


def tournament_sort_key(value: object) -> tuple[int, str]:
    text = str(value).strip() if value is not None and not pd.isna(value) else ""
    return (TOURNAMENT_ORDER.get(text, len(TOURNAMENT_ORDER)), text or "Sin torneo")


def tournament_display_label(value: object) -> str:
    if value is None or pd.isna(value):
        return "Sin torneo"
    text = str(value).strip()
    if not text:
        return "Sin torneo"
    return TOURNAMENT_LABELS.get(text, text)


def build_round_label(tournament: object, round_number: object) -> str:
    label = tournament_display_label(tournament)
    round_value = pd.to_numeric(pd.Series([round_number]), errors="coerce").iloc[0]
    if pd.isna(round_value):
        return label
    return f"{label} · R{int(round_value)}"


def normalize_matches(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    for column in ["match_id", "round_number", "home_id", "away_id", "home_score", "away_score"]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce").astype("Int64")
    if "tournament" not in work.columns:
        work["tournament"] = pd.NA
    work["tournament"] = work["tournament"].astype("string").str.strip()
    if "fecha" in work.columns:
        work["fecha_dt"] = pd.to_datetime(work["fecha"], format="%d/%m/%Y %H:%M", errors="coerce")
    work["round_number"] = work["round_number"].fillna(0).astype(int)
    work["tournament_label"] = work["tournament"].map(tournament_display_label)
    work["round_label"] = work.apply(lambda row: build_round_label(row.get("tournament"), row.get("round_number")), axis=1)
    work["scoreline"] = (
        work["home_score"].fillna(0).astype(int).astype(str)
        + " - "
        + work["away_score"].fillna(0).astype(int).astype(str)
    )
    work["tournament_order"] = work["tournament"].map(lambda value: tournament_sort_key(value)[0])
    return work.sort_values(["tournament_order", "round_number", "fecha_dt", "match_id"]).drop(columns="tournament_order").reset_index(drop=True)


def normalize_teams(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId", "teamid"])
    work["team_id"] = pd.to_numeric(work["team_id"], errors="coerce").astype("Int64")
    if "short_name" not in work.columns and "shortName" in work.columns:
        work["short_name"] = work["shortName"]
    if "full_name" not in work.columns and "fullName" in work.columns:
        work["full_name"] = work["fullName"]
    work["team_name"] = work.get("short_name", pd.Series(index=work.index, dtype="object")).combine_first(
        work.get("full_name", pd.Series(index=work.index, dtype="object"))
    )
    if "is_altitude_team" in work.columns:
        work["is_altitude_team"] = work["is_altitude_team"].fillna(0).astype(int)
    return work.sort_values("team_name").reset_index(drop=True)


def normalize_players(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "player_id", ["player_id", "PLAYER_ID", "playerId", "playerid"])
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId", "teamid"])
    work = coalesce_columns(work, "name", ["name", "NAME", "player", "player_name"])
    work = coalesce_columns(work, "position", ["position", "POSITION", "pos"])
    work["player_id"] = pd.to_numeric(work["player_id"], errors="coerce").astype("Int64")
    work["team_id"] = pd.to_numeric(work["team_id"], errors="coerce").astype("Int64")
    work["position"] = work["position"].astype(str).str.strip().str.upper().replace({"NAN": pd.NA})
    return work.sort_values("name").reset_index(drop=True)


def normalize_player_match(df: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "player_id", ["player_id", "PLAYER_ID", "playerId", "playerid"])
    work = coalesce_columns(work, "match_id", ["match_id", "MATCH_ID", "matchId", "matchid"])
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId", "teamid"])
    work = coalesce_columns(work, "name", ["name", "NAME", "player", "player_name"])
    work = coalesce_columns(work, "position", ["position", "POSITION", "pos"])
    work = coalesce_columns(work, "assists", ["assists", "ASSISTS", "assist", "GOALASSIST", "goalassist"])
    for column in [
        "player_id",
        "match_id",
        "team_id",
        "minutesplayed",
        "goals",
        "assists",
        "saves",
        "fouls",
        "penaltywon",
        "penaltysave",
        "penaltyconceded",
        "rating",
    ]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    work["position"] = work["position"].astype(str).str.strip().str.upper().replace({"NAN": pd.NA})

    match_columns = [
        column
        for column in ["match_id", "round_number", "tournament", "tournament_label", "round_label", "fecha_dt", "home", "away", "home_id", "away_id", "scoreline"]
        if column in matches.columns
    ]
    if match_columns:
        work = work.merge(matches[match_columns], on="match_id", how="left")
    sort_columns = [column for column in ["tournament_label", "round_number", "fecha_dt", "match_id", "name"] if column in work.columns]
    return work.sort_values(sort_columns).reset_index(drop=True)


def normalize_player_totals(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "player_id", ["player_id", "PLAYER_ID", "playerId", "playerid"])
    work["player_id"] = pd.to_numeric(work["player_id"], errors="coerce").astype("Int64")
    for column in [
        "minutesplayed",
        "matches_played",
        "goals",
        "assists",
        "saves",
        "fouls",
        "penaltywon",
        "penaltysave",
        "penaltyconceded",
    ]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work


def normalize_team_stats(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "match_id", ["match_id", "MATCH_ID", "matchId", "matchid"])
    work = coalesce_columns(work, "name", ["name", "NAME"])
    work["match_id"] = pd.to_numeric(work["match_id"], errors="coerce").astype("Int64")
    for column in ["HOMEVALUE", "AWAYVALUE", "HOMETOTAL", "AWAYTOTAL"]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work


def normalize_average_positions(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "player_id", ["player_id", "PLAYER_ID", "id"])
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId"])
    work = coalesce_columns(work, "team_name", ["team_name", "TEAM_NAME", "teamName", "team"])
    work = coalesce_columns(work, "name", ["name", "NAME", "player", "player_name"])
    work = coalesce_columns(work, "position", ["position", "POSITION", "pos"])
    work = coalesce_columns(work, "shirt_number", ["shirt_number", "shirtNumber", "jerseyNumber"])
    work = coalesce_columns(work, "average_x", ["average_x", "averageX"])
    work = coalesce_columns(work, "average_y", ["average_y", "averageY"])
    work = coalesce_columns(work, "points_count", ["points_count", "pointsCount"])
    for column in ["match_id", "player_id", "team_id", "shirt_number", "points_count"]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce").astype("Int64")
    for column in ["average_x", "average_y"]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    if "is_starter" in work.columns:
        work["is_starter"] = work["is_starter"].astype("boolean")
    work["position"] = work["position"].astype(str).str.strip().str.upper().replace({"NAN": pd.NA})
    return work.sort_values(["match_id", "team_name", "shirt_number", "name"], kind="mergesort").reset_index(drop=True)


def normalize_heatmap_points(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "player_id", ["player_id", "PLAYER_ID", "id"])
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId"])
    work = coalesce_columns(work, "team_name", ["team_name", "TEAM_NAME", "teamName", "team"])
    work = coalesce_columns(work, "name", ["name", "NAME", "player", "player_name"])
    for column in ["match_id", "player_id", "team_id"]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce").astype("Int64")
    for column in ["x", "y"]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(["match_id", "player_id"], kind="mergesort").reset_index(drop=True)


def filter_regular_season_matches(matches: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return matches
    if "tournament" in matches.columns and matches["tournament"].notna().any():
        allowed = [tournament for tournament in DEFAULT_DASHBOARD_TOURNAMENTS if tournament in set(matches["tournament"].dropna().astype(str))]
        if allowed:
            return matches.loc[matches["tournament"].isin(allowed)].reset_index(drop=True)
    if "round_number" not in matches.columns:
        return matches
    return matches.loc[matches["round_number"] <= REGULAR_SEASON_MAX_ROUND].reset_index(drop=True)


def filter_by_match_ids(frame: pd.DataFrame, match_ids: set[int]) -> pd.DataFrame:
    if frame.empty or "match_id" not in frame.columns:
        return frame
    return frame.loc[frame["match_id"].isin(match_ids)].reset_index(drop=True)


def parquet_signature() -> tuple[tuple[str, float], ...]:
    files = []
    for name in [
        "matches.parquet",
        "teams.parquet",
        "players.parquet",
        "player_match.parquet",
        "player_totals.parquet",
        "team_stats.parquet",
        "average_positions.parquet",
        "heatmap_points.parquet",
    ]:
        path = DATA_DIR / name
        files.append((name, path.stat().st_mtime if path.exists() else -1.0))
    return tuple(files)


@st.cache_data(show_spinner=False)
def load_dashboard_data(_signature: tuple[tuple[str, float], ...]) -> DatasetBundle:
    matches = normalize_matches(read_parquet(DATA_DIR / "matches.parquet"))
    allowed_match_ids = set(matches["match_id"].dropna().astype(int).tolist())
    teams = normalize_teams(read_parquet(DATA_DIR / "teams.parquet"))
    players = normalize_players(read_parquet(DATA_DIR / "players.parquet"))
    player_match = filter_by_match_ids(
        normalize_player_match(read_parquet(DATA_DIR / "player_match.parquet"), matches),
        allowed_match_ids,
    )
    # Season totals are not reliable once playoff rounds are excluded, so we force
    # player metrics to be rebuilt from player_match inside the active regular-season scope.
    player_totals = pd.DataFrame()
    team_stats = filter_by_match_ids(normalize_team_stats(read_parquet(DATA_DIR / "team_stats.parquet")), allowed_match_ids)
    average_positions = filter_by_match_ids(
        normalize_average_positions(read_parquet(DATA_DIR / "average_positions.parquet")),
        allowed_match_ids,
    )
    heatmap_points = filter_by_match_ids(
        normalize_heatmap_points(read_parquet(DATA_DIR / "heatmap_points.parquet")),
        allowed_match_ids,
    )
    return DatasetBundle(
        matches=matches,
        teams=teams,
        players=players,
        player_match=player_match,
        player_totals=player_totals,
        team_stats=team_stats,
        average_positions=average_positions,
        heatmap_points=heatmap_points,
        loaded_at=datetime.now(),
    )


def _find_image(entity_id: int | str | None, directory: Path) -> Path | None:
    if entity_id is None:
        return None
    try:
        entity = str(int(entity_id))
    except (TypeError, ValueError):
        entity = str(entity_id).strip()
    if not entity:
        return None
    for extension in [".png", ".jpg", ".jpeg", ".webp"]:
        path = directory / f"{entity}{extension}"
        if path.exists():
            return path
    return None


def find_player_image(player_id: int | str | None) -> Path | None:
    return _find_image(player_id, PLAYER_IMAGES_DIR)


def find_team_image(team_id: int | str | None) -> Path | None:
    return _find_image(team_id, TEAM_IMAGES_DIR)
