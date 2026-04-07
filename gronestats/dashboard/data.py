from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from gronestats.data_layout import season_layout
from gronestats.dashboard.config import (
    DATA_ROOT,
    DEFAULT_SEASON_YEAR,
    DEFAULT_DASHBOARD_TOURNAMENTS,
    LEAGUE_NAME,
    PLAYER_IMAGES_DIR,
    REGULAR_SEASON_MAX_ROUND,
    TEAM_IMAGES_DIR,
    TOURNAMENT_LABELS,
    TOURNAMENT_ORDER,
    build_season_label,
)
from gronestats.dashboard.models import ConsolidatedSeasonOverview, DatasetBundle, FilterState, SeasonDataset


DASHBOARD_TABLES = (
    "matches.parquet",
    "teams.parquet",
    "players.parquet",
    "player_match.parquet",
    "player_totals_full_season.parquet",
    "team_stats.parquet",
    "average_positions.parquet",
    "heatmap_points.parquet",
    "shot_events.parquet",
    "match_momentum.parquet",
)


def read_parquet(path: Path, *, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path, columns=columns)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _join_tournament_labels(labels: list[str]) -> str:
    if not labels:
        return "Sin torneo"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} + {labels[1]}"
    return ", ".join(labels)


def describe_active_scope(matches: pd.DataFrame, filters: FilterState) -> str:
    selected_tournaments = list(filters.tournaments or [])
    if selected_tournaments:
        tournament_values = sorted(dict.fromkeys(selected_tournaments), key=tournament_sort_key)
    elif "tournament" in matches.columns:
        tournament_values = sorted(matches["tournament"].dropna().astype(str).unique().tolist(), key=tournament_sort_key)
    else:
        tournament_values = []

    scope = matches.copy()
    if tournament_values and "tournament" in scope.columns:
        scope = scope[scope["tournament"].isin(tournament_values)]

    start_round, end_round = filters.round_range
    if "round_number" in scope.columns and not scope.empty:
        scope = scope[scope["round_number"].between(start_round, end_round)]

    if not scope.empty and "round_number" in scope.columns:
        min_round = int(scope["round_number"].min())
        max_round = int(scope["round_number"].max())
    else:
        min_round, max_round = start_round, end_round

    tournament_label = _join_tournament_labels([tournament_display_label(value) for value in tournament_values])
    round_label = f"R{min_round}" if min_round == max_round else f"R{min_round}-R{max_round}"
    return f"{tournament_label} | {round_label}"


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


def normalize_shot_events(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "match_id", ["match_id", "MATCH_ID", "matchId", "matchid"])
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId", "teamid"])
    work = coalesce_columns(work, "player_id", ["player_id", "PLAYER_ID", "playerId", "playerid"])
    work = coalesce_columns(work, "name", ["name", "NAME", "player", "player_name"])
    for column in ["match_id", "team_id", "player_id", "shot_id", "time", "added_time", "time_seconds", "x", "y", "z"]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    for column in ["match_id", "team_id", "player_id", "shot_id"]:
        if column in work.columns:
            work[column] = work[column].astype("Int64")
    if "is_home" in work.columns:
        raw = work["is_home"]
        if raw.dtype == bool:
            work["is_home"] = raw
        else:
            work["is_home"] = (
                raw.astype("string")
                .str.strip()
                .str.lower()
                .map({"true": True, "false": False, "1": True, "0": False, "home": True, "away": False})
            )
    for column in ["shot_type", "incident_type", "goal_type", "situation", "body_part", "team_name", "name"]:
        if column in work.columns:
            work[column] = work[column].astype("string").str.strip()
    sort_columns = [column for column in ["match_id", "time_seconds", "time", "shot_id"] if column in work.columns]
    if sort_columns:
        work = work.sort_values(sort_columns, kind="mergesort")
    return work.reset_index(drop=True)


def normalize_match_momentum(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "match_id", ["match_id", "MATCH_ID", "matchId", "matchid"])
    if "match_id" in work.columns:
        work["match_id"] = pd.to_numeric(work["match_id"], errors="coerce").astype("Int64")
    for column in ["minute", "value"]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    if "dominant_side" in work.columns:
        work["dominant_side"] = work["dominant_side"].astype("string").str.strip().str.lower()
    sort_columns = [column for column in ["match_id", "minute"] if column in work.columns]
    if sort_columns:
        work = work.sort_values(sort_columns, kind="mergesort")
    return work.reset_index(drop=True)


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


def build_team_options(bundle: DatasetBundle) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not bundle.teams.empty and {"team_id", "team_name"}.issubset(bundle.teams.columns):
        frames.append(bundle.teams[["team_id", "team_name"]].copy())
    if not bundle.matches.empty:
        if {"home_id", "home"}.issubset(bundle.matches.columns):
            frames.append(
                bundle.matches[["home_id", "home"]]
                .rename(columns={"home_id": "team_id", "home": "team_name"})
                .copy()
            )
        if {"away_id", "away"}.issubset(bundle.matches.columns):
            frames.append(
                bundle.matches[["away_id", "away"]]
                .rename(columns={"away_id": "team_id", "away": "team_name"})
                .copy()
            )
    if not frames:
        return pd.DataFrame(columns=["team_id", "team_name"])

    options = pd.concat(frames, ignore_index=True)
    options["team_id"] = pd.to_numeric(options.get("team_id"), errors="coerce").astype("Int64")
    options["team_name"] = options.get("team_name", pd.Series(index=options.index, dtype="object")).astype("string").str.strip()
    options = options.loc[options["team_id"].notna() & options["team_name"].notna() & (options["team_name"] != "")]
    if options.empty:
        return pd.DataFrame(columns=["team_id", "team_name"])
    return options.drop_duplicates(subset=["team_id"], keep="first").sort_values("team_name").reset_index(drop=True)


def describe_bundle_gaps(bundle: DatasetBundle) -> tuple[str, ...]:
    gaps: list[str] = []
    if not bundle.has_player_layer:
        gaps.append(
            "Sin player_match publicado: Overview, Equipos y Partidos siguen activos; Jugadores se habilita cuando entren stats individuales."
        )
    if not bundle.has_match_stats_layer:
        gaps.append(
            "Sin team_stats ampliado: el detalle de partidos se apoya en marcador, contexto y planillas cuando existan."
        )
    if not bundle.has_positional_layer:
        gaps.append(
            "Sin average_positions ni heatmaps: los mapas posicionales quedan ocultos hasta completar el backfill analitico."
        )
    if not bundle.has_shot_layer:
        gaps.append(
            "Sin shot_events: el shotmap Opta del partido se oculta hasta publicar la capa de tiros."
        )
    if not bundle.has_momentum_layer:
        gaps.append(
            "Sin match_momentum: la curva de impulso por minuto no estara disponible para esta temporada."
        )
    return tuple(gaps)


def season_current_dir(season_year: int) -> Path:
    return season_layout(season_year, league=LEAGUE_NAME).dashboard.current_dir


def season_parquet_signature(season_year: int) -> tuple[tuple[str, float], ...]:
    data_dir = season_current_dir(season_year)
    files = []
    for name in ("manifest.json", "validation.json", *DASHBOARD_TABLES):
        path = data_dir / name
        files.append((name, path.stat().st_mtime if path.exists() else -1.0))
    return tuple(files)


def season_catalog_signature() -> tuple[tuple[int, tuple[tuple[str, float], ...]], ...]:
    if not DATA_ROOT.exists():
        return tuple()

    signatures: list[tuple[int, tuple[tuple[str, float], ...]]] = []
    for season_dir in DATA_ROOT.iterdir():
        if not season_dir.is_dir() or not season_dir.name.isdigit():
            continue
        season_year = int(season_dir.name)
        signatures.append((season_year, season_parquet_signature(season_year)))
    return tuple(sorted(signatures, key=lambda item: item[0], reverse=True))


def _discover_available_seasons() -> list[SeasonDataset]:
    seasons: list[SeasonDataset] = []
    if not DATA_ROOT.exists():
        return seasons

    for season_dir in DATA_ROOT.iterdir():
        if not season_dir.is_dir() or not season_dir.name.isdigit():
            continue
        season_year = int(season_dir.name)
        current_dir = season_layout(season_year, league=LEAGUE_NAME).dashboard.current_dir
        if not (current_dir / "matches.parquet").exists():
            continue
        manifest = read_json(current_dir / "manifest.json")
        validation = read_json(current_dir / "validation.json")
        seasons.append(
            SeasonDataset(
                season_year=season_year,
                season_label=build_season_label(season_year),
                data_dir=current_dir,
                manifest=manifest,
                validation=validation,
            )
        )
    return sorted(seasons, key=lambda item: item.season_year, reverse=True)


@st.cache_data(show_spinner=False)
def load_season_catalog(_signature: tuple[tuple[int, tuple[tuple[str, float], ...]], ...]) -> tuple[SeasonDataset, ...]:
    return tuple(_discover_available_seasons())


def resolve_default_season_year(seasons: tuple[SeasonDataset, ...] | list[SeasonDataset]) -> int:
    if seasons:
        return max(dataset.season_year for dataset in seasons)
    return DEFAULT_SEASON_YEAR


def resolve_season_dataset(
    season_year: int,
    seasons: tuple[SeasonDataset, ...] | list[SeasonDataset],
) -> SeasonDataset | None:
    for dataset in seasons:
        if dataset.season_year == season_year:
            return dataset
    return None


def _top_scorer(player_match: pd.DataFrame) -> tuple[str, int]:
    if player_match.empty:
        return ("Sin datos", 0)

    work = player_match.copy()
    if "player_id" in work.columns:
        work["player_id"] = pd.to_numeric(work["player_id"], errors="coerce").astype("Int64")
    if "goals" not in work.columns:
        work["goals"] = 0
    work["goals"] = pd.to_numeric(work["goals"], errors="coerce").fillna(0)
    if "name" not in work.columns:
        work["name"] = pd.NA
    work["name"] = work["name"].astype("string").str.strip()
    work = work.loc[work["player_id"].notna() & work["name"].notna()].copy()
    if work.empty:
        return ("Sin datos", 0)

    scorers = (
        work.groupby(["player_id", "name"], dropna=False)["goals"]
        .sum()
        .reset_index()
        .sort_values(["goals", "name"], ascending=[False, True], kind="mergesort")
        .reset_index(drop=True)
    )
    leader = scorers.iloc[0]
    return (str(leader["name"]), int(leader["goals"]))


@st.cache_data(show_spinner=False)
def load_consolidated_season_overview(
    _signature: tuple[tuple[int, tuple[tuple[str, float], ...]], ...],
) -> ConsolidatedSeasonOverview:
    seasons = load_season_catalog(_signature)
    rows: list[dict[str, Any]] = []
    unique_player_ids: set[int] = set()
    total_matches = 0
    total_goals = 0
    passed_seasons = 0
    warning_seasons = 0

    for dataset in seasons:
        matches = read_parquet(dataset.data_dir / "matches.parquet", columns=["match_id", "home_score", "away_score"])
        teams = read_parquet(dataset.data_dir / "teams.parquet", columns=["team_id"])
        players = read_parquet(dataset.data_dir / "players.parquet", columns=["player_id"])
        player_match = read_parquet(dataset.data_dir / "player_match.parquet", columns=["player_id", "name", "goals"])

        if "player_id" in players.columns:
            unique_player_ids.update(
                pd.to_numeric(players["player_id"], errors="coerce").dropna().astype(int).tolist()
            )

        match_count = int(matches["match_id"].nunique()) if "match_id" in matches.columns else 0
        team_count = int(teams["team_id"].nunique()) if "team_id" in teams.columns else 0
        player_count = int(players["player_id"].nunique()) if "player_id" in players.columns else 0
        goals = 0
        if not matches.empty:
            home_goals = pd.to_numeric(matches.get("home_score"), errors="coerce").fillna(0)
            away_goals = pd.to_numeric(matches.get("away_score"), errors="coerce").fillna(0)
            goals = int((home_goals + away_goals).sum())
        goals_per_match = round(goals / match_count, 2) if match_count else 0.0
        top_scorer_name, top_scorer_goals = _top_scorer(player_match)
        validated_at = dataset.validation.get("validated_at") or dataset.manifest.get("ended_at")

        total_matches += match_count
        total_goals += goals
        if dataset.validation_status == "passed":
            passed_seasons += 1
        if dataset.warning_count:
            warning_seasons += 1

        rows.append(
            {
                "season_year": dataset.season_year,
                "season_label": dataset.season_label,
                "matches": match_count,
                "teams": team_count,
                "players": player_count,
                "goals": goals,
                "goals_per_match": goals_per_match,
                "validation_status": dataset.validation_status,
                "warning_count": dataset.warning_count,
                "coverage_label": dataset.coverage_label,
                "release_id": dataset.manifest.get("release_id", "-"),
                "validated_at": validated_at,
                "top_scorer": top_scorer_name,
                "top_scorer_goals": top_scorer_goals,
            }
        )

    seasons_table = pd.DataFrame(rows)
    if not seasons_table.empty:
        seasons_table = seasons_table.sort_values("season_year", ascending=False).reset_index(drop=True)
    goals_per_match = round(total_goals / total_matches, 2) if total_matches else 0.0
    return ConsolidatedSeasonOverview(
        total_seasons=len(seasons),
        total_matches=total_matches,
        total_players=len(unique_player_ids),
        total_goals=total_goals,
        goals_per_match=goals_per_match,
        passed_seasons=passed_seasons,
        warning_seasons=warning_seasons,
        seasons_table=seasons_table,
    )


@st.cache_data(show_spinner=False)
def load_dashboard_data(season_year: int, _signature: tuple[tuple[str, float], ...]) -> DatasetBundle:
    data_dir = season_current_dir(season_year)
    manifest = read_json(data_dir / "manifest.json")
    validation = read_json(data_dir / "validation.json")
    matches = normalize_matches(read_parquet(data_dir / "matches.parquet"))
    allowed_match_ids = set(matches["match_id"].dropna().astype(int).tolist())
    teams = normalize_teams(read_parquet(data_dir / "teams.parquet"))
    players = normalize_players(read_parquet(data_dir / "players.parquet"))
    player_match = filter_by_match_ids(
        normalize_player_match(read_parquet(data_dir / "player_match.parquet"), matches),
        allowed_match_ids,
    )
    # Full-season totals are exported for lineage, but dashboard metrics still rebuild
    # active-scope player totals from player_match to avoid mixing in excluded rounds.
    player_totals = pd.DataFrame()
    team_stats = filter_by_match_ids(normalize_team_stats(read_parquet(data_dir / "team_stats.parquet")), allowed_match_ids)
    average_positions = filter_by_match_ids(
        normalize_average_positions(read_parquet(data_dir / "average_positions.parquet")),
        allowed_match_ids,
    )
    heatmap_points = filter_by_match_ids(
        normalize_heatmap_points(read_parquet(data_dir / "heatmap_points.parquet")),
        allowed_match_ids,
    )
    shot_events = filter_by_match_ids(
        normalize_shot_events(read_parquet(data_dir / "shot_events.parquet")),
        allowed_match_ids,
    )
    match_momentum = filter_by_match_ids(
        normalize_match_momentum(read_parquet(data_dir / "match_momentum.parquet")),
        allowed_match_ids,
    )
    return DatasetBundle(
        season_year=season_year,
        season_label=build_season_label(season_year),
        data_dir=data_dir,
        matches=matches,
        teams=teams,
        players=players,
        player_match=player_match,
        player_totals=player_totals,
        team_stats=team_stats,
        average_positions=average_positions,
        heatmap_points=heatmap_points,
        validation_status=str(validation.get("status", "unknown")),
        validation_warnings=tuple(validation.get("warnings", [])),
        manifest=manifest,
        validation=validation,
        loaded_at=datetime.now(),
        shot_events=shot_events,
        match_momentum=match_momentum,
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
