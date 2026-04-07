from __future__ import annotations

from pathlib import Path

import pandas as pd

from gronestats.processing.fantasy_pricing import (
    _remap_prices_by_position_quantiles,
    _round_float_columns,
    _safe_per_match,
    _stretch_goalkeeper_prices,
    apply_price_outlier_corrections,
    calculate_price,
)


FANTASY_EXPORT_TABLES = (
    "matches",
    "teams",
    "players",
    "players_fantasy",
    "player_match",
    "player_totals",
    "player_team",
    "player_transfer",
    "team_stats",
)

REQUIRED_PLAYERS_FANTASY_COLS = {"player_id", "name", "position", "team_id", "price"}


def _normalize_id_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    result = series.astype("string").str.strip()
    result.loc[numeric.notna()] = numeric.loc[numeric.notna()].astype("Int64").astype("string")
    result = result.str.replace(".0", "", regex=False)
    return result


def _normalize_position(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.upper().replace({"GK": "G", "NAN": pd.NA, "NONE": pd.NA, "": pd.NA})


def _base_price_by_position(series: pd.Series) -> pd.Series:
    mapped = _normalize_position(series).map({"G": 5.0, "D": 5.5, "M": 6.2, "F": 7.0})
    return mapped.fillna(5.0)


def build_player_totals_export(player_match: pd.DataFrame) -> pd.DataFrame:
    if player_match.empty:
        return pd.DataFrame(
            columns=[
                "player_id",
                "goals",
                "assists",
                "saves",
                "fouls",
                "minutesplayed",
                "penaltywon",
                "penaltysave",
                "penaltyconceded",
                "matches_played",
            ]
        )
    work = player_match.copy()
    for column in ["player_id", "match_id"]:
        work[column] = pd.to_numeric(work.get(column), errors="coerce").astype("Int64")
    for column in ["goals", "assists", "saves", "fouls", "minutesplayed", "penaltywon", "penaltysave", "penaltyconceded"]:
        work[column] = pd.to_numeric(work.get(column, 0), errors="coerce").fillna(0)
    totals = (
        work.dropna(subset=["player_id"])
        .groupby("player_id", as_index=False)
        .agg(
            goals=("goals", "sum"),
            assists=("assists", "sum"),
            saves=("saves", "sum"),
            fouls=("fouls", "sum"),
            minutesplayed=("minutesplayed", "sum"),
            penaltywon=("penaltywon", "sum"),
            penaltysave=("penaltysave", "sum"),
            penaltyconceded=("penaltyconceded", "sum"),
            matches_played=("match_id", "nunique"),
        )
        .sort_values("player_id", kind="mergesort")
        .reset_index(drop=True)
    )
    totals["player_id"] = pd.to_numeric(totals["player_id"], errors="coerce").astype("Int64")
    for column in [
        "goals",
        "assists",
        "saves",
        "fouls",
        "minutesplayed",
        "penaltywon",
        "penaltysave",
        "penaltyconceded",
        "matches_played",
    ]:
        totals[column] = pd.to_numeric(totals[column], errors="coerce").astype("Int64")
    return totals


def build_player_team_export(player_match: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not player_match.empty:
        subset = player_match.copy()
        keep = [column for column in ["player_id", "team_id", "name", "position"] if column in subset.columns]
        if keep:
            frames.append(subset[keep])
    if not players.empty:
        subset = players.copy()
        keep = [column for column in ["player_id", "team_id", "name", "position"] if column in subset.columns]
        if keep:
            frames.append(subset[keep])
    if not frames:
        return pd.DataFrame(columns=["player_id", "team_id", "name", "position"])
    merged = pd.concat(frames, ignore_index=True)
    merged["player_id"] = pd.to_numeric(merged.get("player_id"), errors="coerce").astype("Int64")
    merged["team_id"] = pd.to_numeric(merged.get("team_id"), errors="coerce").astype("Int64")
    if "position" in merged.columns:
        merged["position"] = _normalize_position(merged["position"])
    if "name" in merged.columns:
        merged["name"] = merged["name"].astype("string").str.strip()
    merged = merged.dropna(subset=["player_id", "team_id"])
    merged = merged.drop_duplicates(subset=["player_id", "team_id", "position"], keep="last")
    return merged.sort_values(["player_id", "team_id"], kind="mergesort").reset_index(drop=True)


def build_player_transfer_export(player_team: pd.DataFrame, players: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    if player_team.empty:
        return pd.DataFrame(columns=["player_id", "team_id", "name", "short_name", "position", "team_name"])

    transfer_ids = (
        player_team.dropna(subset=["player_id", "team_id"])
        .groupby("player_id")["team_id"]
        .nunique()
    )
    transfer_ids = transfer_ids[transfer_ids > 1].index.tolist()
    if not transfer_ids:
        return pd.DataFrame(columns=["player_id", "team_id", "name", "short_name", "position", "team_name"])

    frame = player_team[player_team["player_id"].isin(transfer_ids)].copy()
    if not players.empty:
        player_lookup = players.copy()
        player_lookup["player_id"] = pd.to_numeric(player_lookup.get("player_id"), errors="coerce").astype("Int64")
        keep = [column for column in ["player_id", "short_name", "name"] if column in player_lookup.columns]
        frame = frame.merge(player_lookup[keep].drop_duplicates(subset=["player_id"]), on="player_id", how="left", suffixes=("", "_player"))
        if "name_player" in frame.columns:
            frame["name"] = frame["name_player"].combine_first(frame.get("name"))
            frame = frame.drop(columns=["name_player"])
    if not teams.empty:
        team_lookup = teams.copy()
        team_lookup["team_id"] = pd.to_numeric(team_lookup.get("team_id"), errors="coerce").astype("Int64")
        if "short_name" not in team_lookup.columns and "team_name" in team_lookup.columns:
            team_lookup["short_name"] = team_lookup["team_name"]
        keep = [column for column in ["team_id", "short_name", "full_name"] if column in team_lookup.columns]
        frame = frame.merge(team_lookup[keep].drop_duplicates(subset=["team_id"]), on="team_id", how="left", suffixes=("", "_team"))
        frame["team_name"] = frame.get("short_name_team", pd.Series(index=frame.index, dtype="object")).combine_first(
            frame.get("full_name", pd.Series(index=frame.index, dtype="object"))
        )
        frame = frame.drop(columns=[column for column in ["short_name_team", "full_name"] if column in frame.columns], errors="ignore")
    else:
        frame["team_name"] = pd.NA
    keep_cols = [column for column in ["player_id", "team_id", "name", "short_name", "position", "team_name"] if column in frame.columns]
    result = frame[keep_cols].drop_duplicates().sort_values(["player_id", "team_id"], kind="mergesort").reset_index(drop=True)
    for column in ["player_id", "team_id"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").astype("Int64")
    for column in ["name", "short_name", "position", "team_name"]:
        if column in result.columns:
            result[column] = result[column].astype("string").str.strip()
    return result


def build_players_fantasy_export(players: pd.DataFrame, player_totals: pd.DataFrame) -> pd.DataFrame:
    if players.empty:
        return pd.DataFrame(columns=["player_id", "name", "short_name", "position", "price", "team_id"])

    players_work = players.copy()
    players_work["player_id"] = pd.to_numeric(players_work.get("player_id"), errors="coerce").astype("Int64")
    if "team_id" in players_work.columns:
        players_work["team_id"] = pd.to_numeric(players_work.get("team_id"), errors="coerce").astype("Int64")
    players_work["position"] = _normalize_position(players_work.get("position", pd.Series(index=players_work.index, dtype="object")))
    if "name" in players_work.columns:
        players_work["name"] = players_work["name"].astype("string").str.strip()
    if "short_name" in players_work.columns:
        players_work["short_name"] = players_work["short_name"].astype("string").str.strip()

    totals_work = player_totals.copy() if not player_totals.empty else pd.DataFrame(columns=["player_id"])
    if not totals_work.empty:
        totals_work["player_id"] = pd.to_numeric(totals_work.get("player_id"), errors="coerce").astype("Int64")

    fantasy = players_work.merge(totals_work, on="player_id", how="left")
    for column in ["goals", "assists", "saves", "fouls", "minutesplayed", "penaltywon", "penaltysave", "penaltyconceded", "matches_played"]:
        fantasy[column] = pd.to_numeric(fantasy.get(column, 0), errors="coerce").fillna(0)

    fantasy["goals_pm"] = _safe_per_match(fantasy["goals"], fantasy["matches_played"])
    fantasy["assists_pm"] = _safe_per_match(fantasy["assists"], fantasy["matches_played"])
    fantasy["saves_pm"] = _safe_per_match(fantasy["saves"], fantasy["matches_played"])
    fantasy["fouls_pm"] = _safe_per_match(fantasy["fouls"], fantasy["matches_played"])
    fantasy["penaltywon_pm"] = _safe_per_match(fantasy["penaltywon"], fantasy["matches_played"])
    fantasy["penaltysave_pm"] = _safe_per_match(fantasy["penaltysave"], fantasy["matches_played"])
    fantasy["penaltyconceded_pm"] = _safe_per_match(fantasy["penaltyconceded"], fantasy["matches_played"])
    fantasy["price"] = fantasy.apply(calculate_price, axis=1)

    valid_mask = fantasy["minutesplayed"] >= 90
    if valid_mask.any():
        fantasy.loc[valid_mask, "price"] = _remap_prices_by_position_quantiles(
            fantasy.loc[valid_mask, "price"],
            fantasy.loc[valid_mask, "position"],
            fantasy.loc[valid_mask, "minutesplayed"],
            min_price_all=5.0,
            max_price_all=9.8,
        )
        fantasy.loc[valid_mask, "price"] = _stretch_goalkeeper_prices(
            fantasy.loc[valid_mask, "price"],
            fantasy.loc[valid_mask, "position"],
            target_max=6.6,
            min_price=5.5,
        )
    if (~valid_mask).any():
        fantasy.loc[~valid_mask, "price"] = _base_price_by_position(fantasy.loc[~valid_mask, "position"])

    fantasy["price"] = fantasy["price"].clip(5.0, 9.8).round(1)
    fantasy = apply_price_outlier_corrections(fantasy)
    fantasy["price"] = fantasy["price"].round(1)
    fantasy["team_id"] = pd.to_numeric(fantasy.get("team_id"), errors="coerce").astype("Int64")
    fantasy = fantasy.dropna(subset=["player_id", "name", "position"])
    fantasy = fantasy.drop_duplicates(subset=["player_id"], keep="last")
    keep_cols = [
        column
        for column in [
            "player_id",
            "name",
            "short_name",
            "position",
            "price",
            "team_id",
            "minutesplayed",
            "matches_played",
            "goals",
            "assists",
            "saves",
            "fouls",
            "penaltywon",
            "penaltysave",
            "penaltyconceded",
            "goals_pm",
            "assists_pm",
            "saves_pm",
            "fouls_pm",
            "penaltywon_pm",
            "penaltysave_pm",
            "penaltyconceded_pm",
        ]
        if column in fantasy.columns
    ]
    result = _round_float_columns(fantasy[keep_cols].copy(), decimals=2)
    for column in [
        "player_id",
        "team_id",
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
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").astype("Int64")
    for column in ["name", "short_name", "position"]:
        if column in result.columns:
            result[column] = result[column].astype("string").str.strip()
    result["price"] = pd.to_numeric(result["price"], errors="coerce").round(1)
    return result.sort_values(["position", "price", "name"], ascending=[True, False, True], kind="mergesort").reset_index(drop=True)


def build_fantasy_export_bundle(curated_tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    matches = curated_tables.get("matches", pd.DataFrame()).copy()
    teams = curated_tables.get("teams", pd.DataFrame()).copy()
    players = curated_tables.get("players", pd.DataFrame()).copy()
    player_match = curated_tables.get("player_match", pd.DataFrame()).copy()
    team_stats = curated_tables.get("team_stats", pd.DataFrame()).copy()

    player_totals = build_player_totals_export(player_match)
    player_team = build_player_team_export(player_match, players)
    player_transfer = build_player_transfer_export(player_team, players, teams)
    players_fantasy = build_players_fantasy_export(players, player_totals)

    return {
        "matches": matches,
        "teams": teams,
        "players": players,
        "players_fantasy": players_fantasy,
        "player_match": player_match,
        "player_totals": player_totals,
        "player_team": player_team,
        "player_transfer": player_transfer,
        "team_stats": team_stats,
    }


def validate_fantasy_export_bundle(dataset_dir: Path) -> dict[str, object]:
    dataset_path = Path(dataset_dir)
    blocking_errors: list[str] = []
    warnings: list[str] = []
    row_counts: dict[str, int] = {}

    for table_name in FANTASY_EXPORT_TABLES:
        path = dataset_path / f"{table_name}.parquet"
        if not path.exists():
            blocking_errors.append(f"Missing fantasy table: {table_name}")
            continue
        frame = pd.read_parquet(path)
        row_counts[table_name] = int(len(frame))
        if table_name == "players_fantasy":
            missing_cols = sorted(REQUIRED_PLAYERS_FANTASY_COLS.difference(frame.columns))
            if missing_cols:
                blocking_errors.append(f"players_fantasy missing columns: {', '.join(missing_cols)}")
            elif frame.empty:
                warnings.append("players_fantasy is empty; Fantasy sync will publish an empty catalog.")

    timestamp_paths = [dataset_path / f"{table_name}.parquet" for table_name in FANTASY_EXPORT_TABLES if (dataset_path / f"{table_name}.parquet").exists()]
    timestamp_span_seconds = None
    if timestamp_paths:
        mtimes = [path.stat().st_mtime for path in timestamp_paths]
        timestamp_span_seconds = max(mtimes) - min(mtimes)
        if timestamp_span_seconds > 600:
            blocking_errors.append(
                f"Fantasy base table timestamp span is too large ({timestamp_span_seconds:.1f}s), indicating mixed releases."
            )

    return {
        "status": "passed" if not blocking_errors else "failed",
        "validated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "stats": {
            "row_counts": row_counts,
            "timestamp_span_seconds": timestamp_span_seconds,
        },
    }
