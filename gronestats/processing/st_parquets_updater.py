
# Directorio de parquets (Windows):
#   gronestats\data\Liga 1 Peru\2025\parquets
#
# Requisitos:
#   pip install streamlit pandas pyarrow

from __future__ import annotations

from pathlib import Path
import importlib.util
import re
import sys
import pandas as pd
import streamlit as st

try:
    from gronestats.processing.st_create_parquets import (
        calculate_price,
        apply_price_outlier_corrections,
        _round_float_columns,
        _stretch_goalkeeper_prices,
        _remap_prices_by_position_quantiles,
    )
except ModuleNotFoundError:
    BASE_DIR = Path(__file__).resolve().parents[2]
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    try:
        from gronestats.processing.st_create_parquets import (
            calculate_price,
            apply_price_outlier_corrections,
            _round_float_columns,
            _stretch_goalkeeper_prices,
            _remap_prices_by_position_quantiles,
        )
    except ModuleNotFoundError:
        module_path = Path(__file__).resolve().parent / "st_create_parquets.py"
        spec = importlib.util.spec_from_file_location("st_create_parquets", module_path)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        sys.modules["st_create_parquets"] = module
        spec.loader.exec_module(module)
        calculate_price = module.calculate_price
        apply_price_outlier_corrections = module.apply_price_outlier_corrections
        _round_float_columns = module._round_float_columns
        _stretch_goalkeeper_prices = module._stretch_goalkeeper_prices
        _remap_prices_by_position_quantiles = module._remap_prices_by_position_quantiles

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Parquets Updater - Fantasy", layout="wide")

BASE_DIR = Path(__file__).resolve().parents[2]  # .../GroneStatz
PARQUETS_DIR = BASE_DIR / "gronestats" / "data" / "Liga 1 Peru" / "2025" / "parquets" / "normalized"

FILES = {
    "players_fantasy": PARQUETS_DIR / "players_fantasy.parquet",
    "players": PARQUETS_DIR / "players.parquet",
    "teams": PARQUETS_DIR / "teams.parquet",
    "player_totals": PARQUETS_DIR / "player_totals.parquet",
    "player_match": PARQUETS_DIR / "player_match.parquet",
    "player_transfer": PARQUETS_DIR / "player_transfer.parquet",
}

POS_CANON = ["G", "D", "M", "F"]
POS_UI = ["GK", "D", "M", "F"]
POS_CANON_MAP = {
    "GK": "G",
    "G": "G",
    "ARQUERO": "G",
    "ARQ": "G",
    "GOALKEEPER": "G",
    "D": "D",
    "M": "M",
    "F": "F",
}


# -------------------------
# Helpers
# -------------------------
@st.cache_data(show_spinner=False)
def read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)

def normalize_team_id(x):
    if pd.isna(x) or x == "":
        return pd.NA
    try:
        return int(x)
    except Exception:
        return pd.NA

def normalize_pos(x):
    if pd.isna(x) or x == "":
        return pd.NA
    x = str(x).strip().upper()
    return POS_CANON_MAP.get(x, pd.NA)


def display_pos(x):
    if pd.isna(x) or x == "":
        return pd.NA
    x = str(x).strip().upper()
    if x == "G":
        return "GK"
    return x


def normalize_name_key(name: str) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", str(name).strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_team_name_map(teams_df: pd.DataFrame) -> dict[str, int]:
    if teams_df is None or teams_df.empty:
        return {}
    work = normalize_teams(teams_df)
    mapping: dict[str, int] = {}
    for _, row in work.iterrows():
        team_id = row.get("team_id")
        if pd.isna(team_id):
            continue
        team_id = int(team_id)
        for col in ["team_name", "short_name", "full_name"]:
            raw = row.get(col)
            if pd.isna(raw):
                continue
            key = normalize_name_key(str(raw))
            if key and key not in mapping:
                mapping[key] = team_id
    return mapping


def generate_short_name(full_name: str) -> str | None:
    if not full_name:
        return None
    tokens = [t for t in str(full_name).strip().split() if t]
    if len(tokens) == 1:
        return tokens[0]
    connectors = {
        "de",
        "del",
        "la",
        "las",
        "los",
        "da",
        "do",
        "dos",
        "di",
        "van",
        "von",
        "y",
    }
    surname_parts = [tokens[-1]]
    idx = len(tokens) - 2
    while idx >= 0 and tokens[idx].lower() in connectors:
        surname_parts.insert(0, tokens[idx])
        idx -= 1
    surname = " ".join(surname_parts)
    return f"{tokens[0][0]} {surname}".strip()

def safe_cols(df: pd.DataFrame, wanted: list[str]) -> list[str]:
    return [c for c in wanted if c in df.columns]

def coalesce_columns(df: pd.DataFrame, target: str, candidates: list[str]) -> pd.DataFrame:
    existing = [c for c in candidates if c in df.columns]
    if not existing:
        return df
    work = df.copy()
    if target not in work.columns:
        work[target] = pd.NA
    for c in existing:
        if c == target:
            continue
        work[target] = work[target].combine_first(work[c])
    drop_cols = [c for c in existing if c != target]
    return work.drop(columns=drop_cols, errors="ignore")

def normalize_player_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "player_id", ["player_id", "PLAYER_ID", "playerId", "playerid"])
    work = coalesce_columns(work, "match_id", ["match_id", "MATCH_ID", "matchId", "matchid"])
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId", "teamid"])
    work = coalesce_columns(work, "name", ["name", "NAME"])
    work = coalesce_columns(
        work,
        "short_name",
        ["short_name", "shortName", "shortname", "SHORT_NAME", "SHORTNAME", "short name"],
    )
    work = coalesce_columns(work, "position", ["position", "POSITION", "pos"])
    work = coalesce_columns(work, "goals", ["goals", "GOALS", "goal"])
    work = coalesce_columns(work, "assists", ["assists", "ASSISTS", "assist", "GOALASSIST", "goalassist", "goal_assist"])
    work = coalesce_columns(work, "saves", ["saves", "SAVES", "save"])
    work = coalesce_columns(work, "fouls", ["fouls", "FOULS", "foul"])
    work = coalesce_columns(work, "minutesplayed", ["minutesplayed", "MINUTESPLAYED", "minutes_played", "minutes"])
    work = coalesce_columns(work, "matches_played", ["matches_played", "MATCHES_PLAYED", "matchesplayed"])
    work = coalesce_columns(work, "penaltywon", ["penaltywon", "PENALTYWON", "penalty_won"])
    work = coalesce_columns(work, "penaltysave", ["penaltysave", "PENALTYSAVE", "penalty_save"])
    work = coalesce_columns(work, "penaltyconceded", ["penaltyconceded", "PENALTYCONCEDED", "penalty_conceded"])
    work = coalesce_columns(work, "rating", ["rating", "RATING"])
    for col in ["player_id", "match_id", "team_id"]:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce").astype("Int64")
    if "position" in work.columns:
        work["position"] = (
            work["position"]
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"NAN": pd.NA})
            .apply(normalize_pos)
        )
    return work


def normalize_teams(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId", "teamid"])
    if "team_id" in work.columns:
        work["team_id"] = pd.to_numeric(work["team_id"], errors="coerce").astype("Int64")
    if "short_name" not in work.columns and "shortName" in work.columns:
        work["short_name"] = work["shortName"]
    if "full_name" not in work.columns and "fullName" in work.columns:
        work["full_name"] = work["fullName"]
    work["team_name"] = work.get("short_name", pd.Series(index=work.index, dtype="object")).combine_first(
        work.get("full_name", pd.Series(index=work.index, dtype="object"))
    )
    return work


def parse_player_ids(raw_text: str) -> list[int]:
    if not raw_text:
        return []
    tokens = re.split(r"[,\s;]+", raw_text.strip())
    ids: list[int] = []
    seen = set()
    for token in tokens:
        if not token:
            continue
        try:
            val = int(float(token))
        except ValueError:
            continue
        if val not in seen:
            seen.add(val)
            ids.append(val)
    return ids


def parse_player_rows(raw_text: str, team_name_map: dict[str, int] | None = None) -> list[dict]:
    rows = []
    if not raw_text:
        return rows
    team_name_map = team_name_map or {}
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for line in lines:
        parts = [p.strip() for p in re.split(r"[,\t;]+", line)]
        if len(parts) < 2:
            continue
        player_id = None
        name = ""
        short_name = None
        position = pd.NA
        team_id = pd.NA

        def _is_number(value: str) -> bool:
            if value is None:
                return False
            try:
                float(value)
                return True
            except ValueError:
                return False

        if len(parts) >= 3 and (not _is_number(parts[0])) and _is_number(parts[2]):
            team_name = parts[0]
            name = parts[1].strip()
            try:
                player_id = int(float(parts[2]))
            except ValueError:
                player_id = None
            pos_raw = parts[3].strip() if len(parts) > 3 and parts[3] else ""
            position = normalize_pos(pos_raw)
            team_key = normalize_name_key(team_name)
            team_id = team_name_map.get(team_key, pd.NA)
            if pd.isna(team_id) and len(parts) > 4 and _is_number(parts[4]):
                team_id = normalize_team_id(parts[4])
            short_name = generate_short_name(name)
            offset = 4
        else:
            try:
                player_id = int(float(parts[0]))
            except ValueError:
                player_id = None
            name = parts[1].strip() if len(parts) > 1 else ""
            short_name = parts[2].strip() if len(parts) > 2 and parts[2] else None
            pos_raw = parts[3].strip() if len(parts) > 3 and parts[3] else ""
            position = normalize_pos(pos_raw)
            team_id = normalize_team_id(parts[4]) if len(parts) > 4 and parts[4] else pd.NA
            offset = 5

        if player_id is None or not name:
            continue
        if not short_name:
            short_name = generate_short_name(name)

        def _num(idx: int) -> float:
            if len(parts) <= idx or parts[idx] == "":
                return 0.0
            try:
                return float(parts[idx])
            except ValueError:
                return 0.0

        rows.append(
            {
                "player_id": player_id,
                "name": name,
                "short_name": short_name,
                "position": position,
                "team_id": int(team_id) if pd.notna(team_id) else None,
                "minutesplayed": _num(offset + 0),
                "matches_played": _num(offset + 1),
                "goals": _num(offset + 2),
                "assists": _num(offset + 3),
                "saves": _num(offset + 4),
                "fouls": _num(offset + 5),
            }
        )
    return rows


def build_view(players_fantasy: pd.DataFrame, players: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    view = normalize_player_columns(players_fantasy)
    players = normalize_player_columns(players)
    teams = normalize_teams(teams)
    for col in ["name", "short_name", "position", "team_id"]:
        if col not in view.columns:
            view[col] = pd.NA
    if not players.empty and "player_id" in players.columns:
        cols = [c for c in ["player_id", "name", "short_name", "position", "team_id"] if c in players.columns]
        view = view.merge(players[cols], on="player_id", how="left", suffixes=("", "_players"))
        for col in ["name", "short_name", "position", "team_id"]:
            alt = f"{col}_players"
            if alt in view.columns:
                view[col] = view[alt].combine_first(view[col])
        view = view.drop(columns=[c for c in view.columns if c.endswith("_players")], errors="ignore")
    view["position_effective"] = (
        view.get("position", pd.NA)
        .astype(str)
        .str.upper()
        .replace({"NAN": pd.NA})
        .apply(normalize_pos)
    )
    view["position_display"] = view["position_effective"].apply(display_pos)
    view["team_id_effective"] = pd.to_numeric(view.get("team_id"), errors="coerce").astype("Int64")
    if not teams.empty and "team_id" in teams.columns:
        team_lookup = teams[["team_id", "team_name"]].dropna(subset=["team_id"]).drop_duplicates()
        view = view.merge(
            team_lookup,
            left_on="team_id_effective",
            right_on="team_id",
            how="left",
            suffixes=("", "_team"),
        )
        view["team_name_effective"] = view["team_name"]
    else:
        view["team_name_effective"] = pd.NA
    return view


def _safe_per_match(series: pd.Series, matches: pd.Series) -> pd.Series:
    safe_matches = matches.where(matches > 0)
    return series.div(safe_matches).fillna(0)


def recalc_players_fantasy(players_fantasy: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    fantasy = normalize_player_columns(players_fantasy)
    players = normalize_player_columns(players)
    original_ids = set()
    if "player_id" in fantasy.columns:
        original_ids = set(fantasy["player_id"].dropna().astype(int).tolist())
    for col in ["name", "short_name", "position", "team_id"]:
        if col not in fantasy.columns:
            fantasy[col] = pd.NA
    if not players.empty and "player_id" in players.columns:
        cols = [c for c in ["player_id", "name", "short_name", "position", "team_id"] if c in players.columns]
        fantasy = fantasy.merge(players[cols], on="player_id", how="left", suffixes=("", "_players"))
        for col in ["name", "short_name", "position", "team_id"]:
            alt = f"{col}_players"
            if alt in fantasy.columns:
                fantasy[col] = fantasy[alt].combine_first(fantasy[col])
        fantasy = fantasy.drop(columns=[c for c in fantasy.columns if c.endswith("_players")], errors="ignore")
    if original_ids and "player_id" in fantasy.columns:
        fantasy = fantasy[fantasy["player_id"].dropna().astype(int).isin(original_ids)].copy()
    for col in [
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
        if col not in fantasy.columns:
            fantasy[col] = 0
        fantasy[col] = pd.to_numeric(fantasy[col], errors="coerce").fillna(0)
    for src, target in [
        ("goals", "goals_pm"),
        ("assists", "assists_pm"),
        ("saves", "saves_pm"),
        ("fouls", "fouls_pm"),
        ("penaltywon", "penaltywon_pm"),
        ("penaltysave", "penaltysave_pm"),
        ("penaltyconceded", "penaltyconceded_pm"),
    ]:
        fantasy[target] = _safe_per_match(fantasy[src], fantasy["matches_played"])
    favorite_team_ids = {2302, 2305, 2311}
    fantasy["price_raw"] = fantasy.apply(calculate_price, axis=1)
    team_id_num = pd.to_numeric(fantasy.get("team_id"), errors="coerce")
    matches_num = pd.to_numeric(fantasy["matches_played"], errors="coerce").fillna(0)
    minutes_num = pd.to_numeric(fantasy["minutesplayed"], errors="coerce").fillna(0)
    bonus_mask = (
        team_id_num.isin(favorite_team_ids)
        & (matches_num > 30)
        & (minutes_num > 1600)
        & (minutes_num >= 90)
    )
    if bonus_mask.any() and "position" in fantasy.columns:
        pos_upper = fantasy["position"].astype(str).str.strip().str.upper()
        top_bonus = pd.Series(False, index=fantasy.index)
        for pos in ["G", "D", "M", "F"]:
            pos_mask = bonus_mask & (pos_upper == pos)
            if not pos_mask.any():
                continue
            top_idx = (
                fantasy.loc[pos_mask, "price_raw"]
                .sort_values(ascending=False)
                .head(2)
                .index
            )
            top_bonus.loc[top_idx] = True
        bonus_mask = top_bonus
    fantasy.loc[bonus_mask, "price_raw"] = fantasy.loc[bonus_mask, "price_raw"] + 0.5
    min_price_all = 5.0
    max_price_all = 9.8
    minutes_for_price = pd.to_numeric(fantasy["minutesplayed"], errors="coerce")
    avg_minutes = minutes_for_price[minutes_for_price > 0].mean()
    if pd.isna(avg_minutes):
        avg_minutes = 90
    minutes_for_price = minutes_for_price.fillna(avg_minutes)
    minutes_for_price = minutes_for_price.mask(minutes_for_price <= 0, avg_minutes)
    fantasy["price"] = _remap_prices_by_position_quantiles(
        fantasy["price_raw"],
        fantasy.get("position"),
        minutes_for_price,
        min_price_all=min_price_all,
        max_price_all=max_price_all,
    )
    fantasy["price"] = fantasy["price"].clip(min_price_all, max_price_all)
    fantasy.loc[bonus_mask, "price"] = fantasy.loc[bonus_mask, "price"] + 1.0
    fantasy["price"] = fantasy["price"].clip(min_price_all, max_price_all)
    if "position" in fantasy.columns:
        pos_upper = fantasy["position"].astype(str).str.strip().str.upper()
        m_mask = pos_upper == "M"
        d_mask = pos_upper == "D"
        fantasy.loc[m_mask, "price"] = fantasy.loc[m_mask, "price"].clip(upper=8.9)
        fantasy.loc[d_mask, "price"] = fantasy.loc[d_mask, "price"].clip(upper=7.9)
    fantasy["price"] = _stretch_goalkeeper_prices(fantasy["price"], fantasy.get("position"))
    fantasy["price"] = fantasy["price"].round(1)
    fantasy = fantasy.drop(columns=["price_raw"], errors="ignore")
    fantasy = _round_float_columns(fantasy, decimals=2)
    fantasy["price"] = fantasy["price"].round(1)
    fantasy = apply_price_outlier_corrections(fantasy)
    fantasy["price"] = fantasy["price"].round(1)
    return fantasy


def update_players_row(
    players_df: pd.DataFrame,
    player_id: int,
    position: str | None,
    team_id: int | None,
    name: str | None,
) -> pd.DataFrame:
    work = normalize_player_columns(players_df)
    for col in ["player_id", "name", "position", "team_id"]:
        if col not in work.columns:
            work[col] = pd.NA
    mask = work["player_id"] == player_id
    if mask.any():
        if position is not None and position is not pd.NA:
            work.loc[mask, "position"] = position
        if team_id is not None and team_id is not pd.NA:
            work.loc[mask, "team_id"] = team_id
        if name:
            work.loc[mask, "name"] = work.loc[mask, "name"].fillna(name)
    else:
        new_row = {
            "player_id": player_id,
            "name": name,
            "position": position,
            "team_id": team_id,
        }
        work = pd.concat([work, pd.DataFrame([new_row])], ignore_index=True)
    work["player_id"] = pd.to_numeric(work["player_id"], errors="coerce").astype("Int64")
    if "team_id" in work.columns:
        work["team_id"] = pd.to_numeric(work["team_id"], errors="coerce").astype("Int64")
    if "position" in work.columns:
        work["position"] = (
            work["position"]
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"NAN": pd.NA})
            .apply(normalize_pos)
        )
    return work


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def sync_players_price(players_df: pd.DataFrame, fantasy_df: pd.DataFrame) -> pd.DataFrame:
    if players_df.empty or fantasy_df.empty:
        return players_df
    players = normalize_player_columns(players_df)
    fantasy = normalize_player_columns(fantasy_df)
    if "player_id" not in players.columns or "player_id" not in fantasy.columns:
        return players_df
    if "price" not in fantasy.columns:
        return players_df
    price_map = fantasy[["player_id", "price"]].dropna(subset=["player_id"]).drop_duplicates(subset=["player_id"])
    merged = players.merge(price_map, on="player_id", how="left", suffixes=("", "_fantasy"))
    if "price_fantasy" in merged.columns:
        if "price" in players.columns:
            merged["price"] = merged["price_fantasy"].combine_first(merged["price"])
        else:
            merged["price"] = merged["price_fantasy"]
        merged = merged.drop(columns=["price_fantasy"])
    original_cols = list(players.columns)
    if "price" not in original_cols:
        original_cols.append("price")
    return merged[original_cols].copy()


def remove_player_rows(
    players_fantasy_df: pd.DataFrame,
    player_id: int,
) -> pd.DataFrame:
    fantasy = normalize_player_columns(players_fantasy_df)
    return fantasy[fantasy["player_id"] != player_id].copy()


def add_short_name_to_fantasy(
    players_fantasy_df: pd.DataFrame,
    players_df: pd.DataFrame,
) -> pd.DataFrame:
    if players_fantasy_df.empty or players_df.empty:
        return players_fantasy_df
    if "player_id" not in players_fantasy_df.columns:
        return players_fantasy_df
    players = normalize_player_columns(players_df)
    if "player_id" not in players.columns or "short_name" not in players.columns:
        return players_fantasy_df
    ids = pd.to_numeric(players["player_id"], errors="coerce").astype("Int64")
    short = players["short_name"].astype("string")
    short_map = {
        int(pid): str(short_name)
        for pid, short_name in zip(ids, short)
        if pd.notna(pid) and pd.notna(short_name) and str(short_name).strip() != ""
    }
    if not short_map:
        return players_fantasy_df
    work = players_fantasy_df.copy()
    fantasy_ids = pd.to_numeric(work["player_id"], errors="coerce").astype("Int64")
    mapped = fantasy_ids.map(short_map)
    if "short_name" in work.columns:
        work["short_name"] = work["short_name"].combine_first(mapped)
    else:
        work["short_name"] = mapped
    return work


def _append_row(df: pd.DataFrame, row: dict) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame([row])
    work = df.copy()
    for key in row.keys():
        if key not in work.columns:
            work[key] = pd.NA
    return pd.concat([work, pd.DataFrame([row])], ignore_index=True)


def add_new_player_to_fantasy(
    players_df: pd.DataFrame,
    players_fantasy_df: pd.DataFrame,
    player_id: int,
    name: str,
    short_name: str | None,
    position: str | None,
    team_id: int | None,
    minutesplayed: float,
    matches_played: float,
    goals: float,
    assists: float,
    saves: float,
    fouls: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    players = normalize_player_columns(players_df)
    fantasy = normalize_player_columns(players_fantasy_df)
    if "player_id" not in fantasy.columns:
        fantasy["player_id"] = pd.NA
    existing_fantasy = set(fantasy["player_id"].dropna().astype(int).tolist())
    existing_players = set()
    if "player_id" in players.columns:
        existing_players = set(players["player_id"].dropna().astype(int).tolist())
    # Solo evitar duplicados dentro del fantasy.
    if player_id in existing_fantasy:
        return players_df, players_fantasy_df

    players = update_players_row(players, player_id, position, team_id, name)
    if not short_name:
        short_name = generate_short_name(name)
    if short_name:
        if "short_name" not in players.columns:
            players["short_name"] = pd.NA
        players.loc[players["player_id"] == player_id, "short_name"] = short_name

    new_row = {
        "player_id": player_id,
        "name": name,
        "short_name": short_name if short_name else pd.NA,
        "position": position,
        "team_id": team_id,
        "minutesplayed": minutesplayed,
        "matches_played": matches_played,
        "goals": goals,
        "assists": assists,
        "saves": saves,
        "fouls": fouls,
        "penaltywon": 0,
        "penaltysave": 0,
        "penaltyconceded": 0,
    }
    fantasy = _append_row(fantasy, new_row)
    return players, fantasy


def append_missing_players_from_players(
    players_fantasy_df: pd.DataFrame,
    players_df: pd.DataFrame,
) -> pd.DataFrame:
    fantasy = normalize_player_columns(players_fantasy_df)
    players = normalize_player_columns(players_df)
    if players.empty or "player_id" not in players.columns:
        return fantasy
    if "player_id" not in fantasy.columns:
        fantasy["player_id"] = pd.NA
    players_ids = set(players["player_id"].dropna().astype(int).tolist())
    fantasy_ids = set(fantasy["player_id"].dropna().astype(int).tolist())
    missing_ids = sorted(players_ids - fantasy_ids)
    if not missing_ids:
        return fantasy
    cols = [c for c in ["player_id", "name", "short_name", "position", "team_id"] if c in players.columns]
    missing_rows = players[players["player_id"].isin(missing_ids)][cols].drop_duplicates(subset=["player_id"])
    return pd.concat([fantasy, missing_rows], ignore_index=True)


# -------------------------
# Load
# -------------------------
missing_req = [k for k in ["players_fantasy", "teams"] if not FILES[k].exists()]
if missing_req:
    st.error(
        "Faltan archivos requeridos:\n- "
        + "\n- ".join(str(FILES[k]) for k in missing_req)
        + f"\n\nVerifica la ruta: {PARQUETS_DIR}"
    )
    st.stop()

players_fantasy = normalize_player_columns(read_parquet(FILES["players_fantasy"]))
players = normalize_player_columns(read_parquet(FILES["players"]))
teams = normalize_teams(read_parquet(FILES["teams"]))
team_name_map = build_team_name_map(teams)
totals = normalize_player_columns(read_parquet(FILES["player_totals"]))
pmatch = normalize_player_columns(read_parquet(FILES["player_match"]))
ptr = normalize_player_columns(read_parquet(FILES["player_transfer"]))
view = build_view(players_fantasy, players, teams)

# -------------------------
# UI
# -------------------------
st.title("Fantasy - Actualizador de jugadores")
st.caption("Usa filas de player_match para actualizar posicion y team_id.")

c0, c1, c2 = st.columns([2, 2, 2])
with c0:
    q = st.text_input("Buscar jugador", placeholder="Nombre...")
with c1:
    pos_options = POS_UI.copy()
    if "position_effective" in view.columns:
        missing_pos = view["position_effective"].isna().any()
        if missing_pos:
            pos_options = POS_UI + ["Sin posicion"]
    pos_filter = st.multiselect("Posicion", pos_options, default=pos_options)
with c2:
    team_names = sorted(view["team_name_effective"].dropna().unique().tolist()) if "team_name_effective" in view.columns else []
    team_options = team_names.copy()
    if "team_name_effective" in view.columns:
        if view["team_name_effective"].isna().any():
            team_options = team_names + ["Sin equipo"]
    team_filter = st.multiselect("Equipo", team_options, default=team_options)

filtered = view.copy()
if q:
    filtered = filtered[filtered["name"].astype(str).str.contains(q, case=False, na=False)]
if "position_effective" in filtered.columns and pos_filter:
    if len(pos_filter) != len(pos_options):
        pos_filter_canon = [normalize_pos(p) for p in pos_filter if p != "Sin posicion"]
        mask = filtered["position_effective"].isin(pos_filter_canon)
        if "Sin posicion" in pos_filter:
            mask = mask | filtered["position_effective"].isna()
        filtered = filtered[mask]
if "team_name_effective" in filtered.columns and team_filter:
    if len(team_filter) != len(team_options):
        mask = filtered["team_name_effective"].isin(team_filter)
        if "Sin equipo" in team_filter:
            mask = mask | filtered["team_name_effective"].isna()
        filtered = filtered[mask]

st.subheader("Distribucion por posicion")
if "position_effective" in filtered.columns:
    dist = (
        filtered["position_effective"]
        .value_counts(dropna=False)
        .reindex(POS_CANON)
        .fillna(0)
        .astype(int)
        .rename_axis("position")
        .reset_index(name="count")
    )
    dist["position"] = dist["position"].apply(display_pos)
    st.dataframe(dist, use_container_width=True, hide_index=True)

st.subheader("Vista de jugadores")
st.caption(f"Jugadores filtrados: {len(filtered)}")
cols_show = safe_cols(
    filtered,
    [
        "player_id",
        "name",
        "position_display",
        "team_name_effective",
        "team_id_effective",
        "price",
        "minutesplayed",
        "matches_played",
        "goals",
        "assists",
        "saves",
        "fouls",
    ],
)
players_table = filtered[cols_show]
if "price" in players_table.columns:
    players_table = players_table.sort_values("price", ascending=False)
st.dataframe(players_table, use_container_width=True)

# -------------------------
# Acciones por lista de IDs
# -------------------------
st.divider()
st.subheader("Acciones por lista de IDs")
st.caption("Pega IDs separados por coma, espacio o salto de linea.")
ids_text = st.text_area("Lista de player_id", height=120)
batch_ids = parse_player_ids(ids_text)
if ids_text and not batch_ids:
    st.warning("No se detectaron IDs validos.")
if batch_ids:
    st.write(f"IDs detectados: {len(batch_ids)}")
    preview_cols = safe_cols(
        view,
        [
            "player_id",
            "name",
            "short_name",
            "position_display",
            "team_name_effective",
            "team_id_effective",
            "price",
        ],
    )
    st.dataframe(view[view["player_id"].isin(batch_ids)][preview_cols], use_container_width=True)

    st.subheader("Asignar equipo a lista")
    team_options = []
    team_label_by_id: dict[int, str] = {}
    if not teams.empty and "team_id" in teams.columns:
        team_lookup = teams[["team_id", "team_name"]].dropna(subset=["team_id"]).drop_duplicates()
        for _, row_team in team_lookup.iterrows():
            team_id_val = row_team.get("team_id")
            if pd.isna(team_id_val):
                continue
            team_id_int = int(team_id_val)
            team_name = str(row_team.get("team_name", "")).strip() or "Equipo"
            team_options.append(team_id_int)
            team_label_by_id[team_id_int] = f"{team_name} ({team_id_int})"
    team_options = sorted(set(team_options))

    if team_options:
        selected_team_id = st.selectbox(
            "Nuevo equipo (lista)",
            options=team_options,
            format_func=lambda tid: team_label_by_id.get(tid, str(tid)),
            key="batch_team_select",
        )
        manual_team_id = st.number_input(
            "O ingresar team_id manual",
            min_value=0,
            step=1,
            value=0,
            key="batch_team_manual",
        )
        use_manual_team = st.checkbox("Usar team_id manual", value=False, key="batch_team_manual_check")
        proposed_team_id = manual_team_id if use_manual_team else selected_team_id
    else:
        proposed_team_id = st.number_input(
            "Nuevo team_id",
            min_value=0,
            step=1,
            value=0,
            key="batch_team_manual_only",
        )

    if st.button("Aplicar equipo a IDs", type="primary"):
        new_team_id = normalize_team_id(proposed_team_id)
        if pd.isna(new_team_id) or int(new_team_id) <= 0:
            st.warning("team_id invalido.")
        else:
            updated_players = players.copy()
            if "player_id" not in updated_players.columns:
                st.warning("players.parquet no tiene player_id.")
            else:
                updated_players.loc[
                    updated_players["player_id"].isin(batch_ids), "team_id"
                ] = new_team_id
                updated_fantasy = recalc_players_fantasy(players_fantasy, updated_players)
                updated_players = sync_players_price(updated_players, updated_fantasy)
                save_parquet(updated_players, FILES["players"])
                save_parquet(updated_fantasy, FILES["players_fantasy"])
                st.success("Equipo actualizado para la lista.")
                st.cache_data.clear()
                st.rerun()

    st.subheader("Asignar posicion a lista")
    batch_pos = st.selectbox(
        "Nueva posicion (lista)",
        options=POS_UI,
        key="batch_position_select",
    )
    if st.button("Aplicar posicion a IDs", type="primary"):
        new_pos = normalize_pos(batch_pos)
        if pd.isna(new_pos):
            st.warning("Posicion invalida.")
        else:
            updated_players = players.copy()
            if "player_id" not in updated_players.columns:
                st.warning("players.parquet no tiene player_id.")
            else:
                updated_players.loc[
                    updated_players["player_id"].isin(batch_ids), "position"
                ] = new_pos
                updated_fantasy = recalc_players_fantasy(players_fantasy, updated_players)
                updated_players = sync_players_price(updated_players, updated_fantasy)
                save_parquet(updated_players, FILES["players"])
                save_parquet(updated_fantasy, FILES["players_fantasy"])
                st.success("Posicion actualizada para la lista.")
                st.cache_data.clear()
                st.rerun()

    st.subheader("Eliminar jugadores del fantasy (lista)")
    delete_batch = st.checkbox("Eliminar jugadores del fantasy con estos IDs")
    if st.button("Eliminar jugadores (lista)", type="primary"):
        if not delete_batch:
            st.warning("Confirma el checkbox para eliminar.")
        else:
            updated_fantasy = players_fantasy.copy()
            if "player_id" not in updated_fantasy.columns:
                st.warning("players_fantasy.parquet no tiene player_id.")
            else:
                updated_fantasy = updated_fantasy[~updated_fantasy["player_id"].isin(batch_ids)]
                updated_fantasy = recalc_players_fantasy(updated_fantasy, players)
                updated_players = sync_players_price(players, updated_fantasy)
                save_parquet(updated_players, FILES["players"])
                save_parquet(updated_fantasy, FILES["players_fantasy"])
                st.success("Jugadores eliminados del fantasy.")
                st.cache_data.clear()
                st.rerun()

# -------------------------
# Detalle por jugador
# -------------------------
st.divider()
st.subheader("Detalle por jugador")

player_ids = filtered["player_id"].dropna().astype(int).unique().tolist()
if not player_ids:
    st.info("No hay jugadores con los filtros actuales.")
    st.stop()

sel = st.selectbox("player_id", options=player_ids)

row = view[view["player_id"] == sel].head(1)
if row.empty:
    st.warning("No encontrado.")
    st.stop()

r = row.iloc[0]
d1, d2, d3, d4 = st.columns([3,1,2,1])
d1.metric("Jugador", str(r.get("name", "")))
d2.metric("Posicion", str(r.get("position_display", "")))
d3.metric("Equipo (id)", str(r.get("team_id_effective", "")))
d4.metric("Precio", str(r.get("price", "")))

st.subheader("Modificar posicion")
current_pos_display = str(r.get("position_display", "")).strip() or "GK"
if current_pos_display not in POS_UI:
    current_pos_display = "GK"
new_pos_display = st.selectbox(
    "Nueva posicion",
    options=POS_UI,
    index=POS_UI.index(current_pos_display),
    key="position_modifier",
)
if st.button("Aplicar posicion", type="primary"):
    new_pos = normalize_pos(new_pos_display)
    name_value = str(r.get("name", "")).strip()
    current_team_id = normalize_team_id(r.get("team_id_effective"))
    updated_players = update_players_row(
        players,
        sel,
        new_pos,
        current_team_id,
        name_value if name_value else None,
    )
    updated_fantasy = recalc_players_fantasy(players_fantasy, updated_players)
    updated_players = sync_players_price(updated_players, updated_fantasy)
    save_parquet(updated_players, FILES["players"])
    save_parquet(updated_fantasy, FILES["players_fantasy"])
    st.success("Posicion actualizada.")
    st.cache_data.clear()
    st.rerun()

st.subheader("Eliminar jugador del fantasy")
delete_from_fantasy = st.checkbox("Eliminar este jugador de players_fantasy.parquet")

if delete_from_fantasy:
    if st.button("Eliminar jugador", type="primary"):
        updated_fantasy = remove_player_rows(
            players_fantasy,
            sel,
        )
        updated_fantasy = recalc_players_fantasy(updated_fantasy, players)
        updated_players = sync_players_price(players, updated_fantasy)
        save_parquet(updated_players, FILES["players"])
        save_parquet(updated_fantasy, FILES["players_fantasy"])
        st.success("Jugador eliminado y precios recalculados.")
        st.cache_data.clear()
        st.rerun()

st.subheader("Transferencia manual de equipo")
current_pos = normalize_pos(r.get("position_effective"))
name_value = str(r.get("name", "")).strip()
team_options = []
team_label_by_id: dict[int, str] = {}
if not teams.empty and "team_id" in teams.columns:
    team_lookup = teams[["team_id", "team_name"]].dropna(subset=["team_id"]).drop_duplicates()
    for _, row_team in team_lookup.iterrows():
        team_id_val = row_team.get("team_id")
        if pd.isna(team_id_val):
            continue
        team_id_int = int(team_id_val)
        team_name = str(row_team.get("team_name", "")).strip() or "Equipo"
        team_options.append(team_id_int)
        team_label_by_id[team_id_int] = f"{team_name} ({team_id_int})"
team_options = sorted(set(team_options))

if team_options:
    selected_team_id = st.selectbox(
        "Nuevo equipo (lista)",
        options=team_options,
        format_func=lambda tid: team_label_by_id.get(tid, str(tid)),
    )
    manual_team_id = st.number_input("O ingresar team_id manual", min_value=0, step=1, value=0)
    use_manual_team = st.checkbox("Usar team_id manual", value=False)
    proposed_team_id = manual_team_id if use_manual_team else selected_team_id
else:
    proposed_team_id = st.number_input("Nuevo team_id", min_value=0, step=1, value=0)

if st.button("Aplicar transferencia de equipo", type="primary"):
    new_team_id = normalize_team_id(proposed_team_id)
    if pd.isna(new_team_id) or int(new_team_id) <= 0:
        st.warning("team_id invalido.")
    else:
        updated_players = update_players_row(
            players,
            sel,
            current_pos,
            new_team_id,
            name_value if name_value else None,
        )
        updated_fantasy = recalc_players_fantasy(players_fantasy, updated_players)
        updated_players = sync_players_price(updated_players, updated_fantasy)
        save_parquet(updated_players, FILES["players"])
        save_parquet(updated_fantasy, FILES["players_fantasy"])
        st.success("Equipo actualizado y precios recalculados.")
        st.cache_data.clear()
        st.rerun()

tab_reload, tab1, tab2, tab3 = st.tabs(
    ["recargar players_fantasy", "player_totals", "player_match", "player_transfer"]
)

with tab_reload:
    st.subheader("Recargar players_fantasy desde players.parquet")
    st.caption("Actualiza name/position/team_id y recalcula precios.")

    players_count = int(players["player_id"].dropna().nunique()) if "player_id" in players.columns else 0
    fantasy_count = (
        int(players_fantasy["player_id"].dropna().nunique())
        if "player_id" in players_fantasy.columns
        else 0
    )
    st.write(f"players.parquet: {players_count} jugadores")
    st.write(f"players_fantasy.parquet: {fantasy_count} jugadores")

    missing_ids = []
    if "player_id" in players.columns:
        players_ids = set(players["player_id"].dropna().astype(int).tolist())
        fantasy_ids = (
            set(players_fantasy["player_id"].dropna().astype(int).tolist())
            if "player_id" in players_fantasy.columns
            else set()
        )
        missing_ids = sorted(players_ids - fantasy_ids)

    add_missing = st.checkbox("Agregar jugadores nuevos desde players.parquet", value=False)
    if missing_ids:
        st.caption(f"Nuevos jugadores detectados: {len(missing_ids)}")
        preview_cols = safe_cols(players, ["player_id", "name", "short_name", "position", "team_id"])
        st.dataframe(
            players[players["player_id"].isin(missing_ids)][preview_cols],
            use_container_width=True,
        )
    else:
        st.caption("No hay jugadores nuevos en players.parquet.")

    st.divider()
    st.subheader("Agregar short_name sin recalcular")
    raw_fantasy = read_parquet(FILES["players_fantasy"])
    if "short_name" in raw_fantasy.columns:
        missing_short = raw_fantasy["short_name"].isna().sum()
    else:
        missing_short = len(raw_fantasy)
    if "short_name" not in players.columns:
        st.info("players.parquet no tiene short_name.")
    else:
        st.caption(f"short_name faltante en players_fantasy: {missing_short}")
        if st.button("Agregar short_name a players_fantasy", type="primary"):
            updated_fantasy = add_short_name_to_fantasy(raw_fantasy, players)
            save_parquet(updated_fantasy, FILES["players_fantasy"])
            st.success("short_name agregado en players_fantasy.")
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.subheader("Agregar nuevo jugador al fantasy")
    st.caption("Crea un jugador en players.parquet y lo agrega a players_fantasy.parquet.")
    c_add1, c_add2, c_add3 = st.columns(3)
    with c_add1:
        new_player_id = st.number_input("player_id", min_value=0, step=1, value=0)
        new_player_name = st.text_input("Nombre completo")
        new_player_short = st.text_input("Short name (opcional)")
    with c_add2:
        new_player_pos_display = st.selectbox("Posicion", POS_UI, key="new_player_pos")
        new_player_team_id = st.number_input("team_id", min_value=0, step=1, value=0)
    with c_add3:
        new_minutes = st.number_input("Minutos (opcional)", min_value=0.0, step=1.0, value=0.0)
        new_matches = st.number_input("Partidos (opcional)", min_value=0.0, step=1.0, value=0.0)
        new_goals = st.number_input("Goles (opcional)", min_value=0.0, step=1.0, value=0.0)
        new_assists = st.number_input("Asistencias (opcional)", min_value=0.0, step=1.0, value=0.0)
        new_saves = st.number_input("Atajadas (opcional)", min_value=0.0, step=1.0, value=0.0)
        new_fouls = st.number_input("Faltas (opcional)", min_value=0.0, step=1.0, value=0.0)

    if st.button("Agregar jugador al fantasy", type="primary"):
        if new_player_id <= 0:
            st.warning("player_id invalido.")
        elif not new_player_name.strip():
            st.warning("Nombre requerido.")
        else:
            existing_players = set(
                players["player_id"].dropna().astype(int).tolist()
            ) if "player_id" in players.columns else set()
            existing_fantasy = set(
                players_fantasy["player_id"].dropna().astype(int).tolist()
            ) if "player_id" in players_fantasy.columns else set()
            if int(new_player_id) in existing_players or int(new_player_id) in existing_fantasy:
                st.warning("player_id ya existe en players o players_fantasy.")
                st.stop()
            new_pos = normalize_pos(new_player_pos_display)
            new_team = normalize_team_id(new_player_team_id)
            updated_players, updated_fantasy = add_new_player_to_fantasy(
                players,
                players_fantasy,
                int(new_player_id),
                new_player_name.strip(),
                new_player_short.strip() if new_player_short.strip() else None,
                new_pos,
                int(new_team) if pd.notna(new_team) else None,
                float(new_minutes),
                float(new_matches),
                float(new_goals),
                float(new_assists),
                float(new_saves),
                float(new_fouls),
            )
            if updated_fantasy is players_fantasy:
                st.warning("Jugador ya existe en players_fantasy.")
            else:
                updated_fantasy = recalc_players_fantasy(updated_fantasy, updated_players)
                updated_players = sync_players_price(updated_players, updated_fantasy)
                save_parquet(updated_players, FILES["players"])
                save_parquet(updated_fantasy, FILES["players_fantasy"])
                st.success("Jugador agregado y precios recalculados.")
                st.cache_data.clear()
                st.rerun()

    st.divider()
    st.subheader("Carga masiva de nuevos jugadores")
    st.caption(
        "Formato por linea (opcion A): player_id, nombre, short_name, posicion, team_id, minutos, partidos, goles, asistencias, saves, fouls"
    )
    st.info(
        "Formato alterno (opcion B): equipo, nombre, player_id, posicion, minutos, partidos, goles, asistencias, saves, fouls.\n"
        "Columnas requeridas: player_id, nombre. Opcionales: short_name, posicion(GK/D/M/F), team_id, minutos, partidos, goles, asistencias, saves, fouls."
    )
    bulk_text = st.text_area("Jugadores (bulk)", height=140)
    bulk_rows = parse_player_rows(bulk_text, team_name_map)
    if bulk_text and not bulk_rows:
        st.warning("No se detectaron filas validas.")
    if bulk_rows:
        bulk_ids = [row["player_id"] for row in bulk_rows]
        dup_ids = sorted({pid for pid in bulk_ids if bulk_ids.count(pid) > 1})
        if dup_ids:
            st.warning(f"IDs repetidos en el bulk: {', '.join(map(str, dup_ids))}")
        st.write(f"Filas validas: {len(bulk_rows)}")
        preview_df = pd.DataFrame(bulk_rows)[
            ["player_id", "name", "short_name", "position", "team_id"]
        ]
        st.dataframe(preview_df, use_container_width=True)

    if st.button("Agregar jugadores (bulk)", type="primary"):
        if not bulk_rows:
            st.warning("No hay filas validas.")
        else:
            updated_players = players.copy()
            updated_fantasy = players_fantasy.copy()
            existing_fantasy = set(
                updated_fantasy["player_id"].dropna().astype(int).tolist()
            ) if "player_id" in updated_fantasy.columns else set()
            added = 0
            skipped_existing = []
            for row in bulk_rows:
                pid = row["player_id"]
                if pid in existing_fantasy:
                    skipped_existing.append(pid)
                    continue
                updated_players, updated_fantasy = add_new_player_to_fantasy(
                    updated_players,
                    updated_fantasy,
                    pid,
                    row["name"],
                    row.get("short_name"),
                    row.get("position"),
                    row.get("team_id"),
                    row.get("minutesplayed", 0.0),
                    row.get("matches_played", 0.0),
                    row.get("goals", 0.0),
                    row.get("assists", 0.0),
                    row.get("saves", 0.0),
                    row.get("fouls", 0.0),
                )
                existing_players.add(pid)
                existing_fantasy.add(pid)
                added += 1
            if added == 0:
                st.info("No se agregaron jugadores nuevos. Recalculando precios.")
            updated_fantasy = recalc_players_fantasy(updated_fantasy, updated_players)
            updated_players = sync_players_price(updated_players, updated_fantasy)
            save_parquet(updated_players, FILES["players"])
            save_parquet(updated_fantasy, FILES["players_fantasy"])
            st.success(f"Jugadores agregados: {added}.")
            if skipped_existing:
                st.info(
                    f"IDs ya existentes en players_fantasy (omitidos): {', '.join(map(str, skipped_existing))}"
                )
            st.cache_data.clear()
            st.rerun()

    st.divider()
    if st.button("Recargar players_fantasy", type="primary"):
        updated_fantasy = players_fantasy
        if add_missing:
            updated_fantasy = append_missing_players_from_players(updated_fantasy, players)
        updated_fantasy = recalc_players_fantasy(updated_fantasy, players)
        updated_players = sync_players_price(players, updated_fantasy)
        save_parquet(updated_players, FILES["players"])
        save_parquet(updated_fantasy, FILES["players_fantasy"])
        st.success("players_fantasy actualizado desde players.parquet.")
        st.cache_data.clear()
        st.rerun()

with tab1:
    if totals.empty:
        st.info("player_totals.parquet no existe o esta vacio.")
    elif "player_id" in totals.columns:
        st.dataframe(totals[totals["player_id"] == sel], use_container_width=True)
    else:
        st.warning("player_totals.parquet no tiene columna player_id.")

with tab2:
    if pmatch.empty:
        st.info("player_match.parquet no existe o esta vacio.")
    elif "player_id" in pmatch.columns:
        pmatch_player = pmatch[pmatch["player_id"] == sel].copy()
        if pmatch_player.empty:
            st.info("Sin partidos para este jugador.")
        else:
            cols_match = [
                c
                for c in [
                    "match_id",
                    "team_id",
                    "position",
                    "minutesplayed",
                    "goals",
                    "assists",
                    "saves",
                    "rating",
                ]
                if c in pmatch_player.columns
            ]
            st.dataframe(pmatch_player[cols_match], use_container_width=True)

            pmatch_player = pmatch_player.reset_index(drop=True)
            labels = []
            for idx, row_m in pmatch_player.iterrows():
                label = (
                    f"{idx + 1} | match {row_m.get('match_id', '')} | "
                    f"pos {row_m.get('position', '')} | team {row_m.get('team_id', '')}"
                )
                labels.append(label)

            selected_idx = st.selectbox(
                "Fila para actualizar jugador",
                options=list(range(len(labels))),
                format_func=lambda i: labels[i],
            )
            selected_row = pmatch_player.iloc[selected_idx]
            new_pos = normalize_pos(selected_row.get("position"))
            new_team = normalize_team_id(selected_row.get("team_id"))
            st.caption(f"Seleccion: position={new_pos} team_id={new_team}")

            if st.button("Actualizar jugador con esta fila", type="primary"):
                name_value = str(r.get("name", "")).strip()
                updated_players = update_players_row(
                    players,
                    sel,
                    new_pos,
                    new_team,
                    name_value if name_value else None,
                )
                updated_fantasy = recalc_players_fantasy(players_fantasy, updated_players)
                updated_players = sync_players_price(updated_players, updated_fantasy)
                save_parquet(updated_players, FILES["players"])
                save_parquet(updated_fantasy, FILES["players_fantasy"])
                st.success("Parquets actualizados.")
                st.cache_data.clear()
                st.rerun()
    else:
        st.warning("player_match.parquet no tiene columna player_id.")

with tab3:
    if ptr.empty:
        st.info("player_transfer.parquet no existe o esta vacio.")
    elif "player_id" in ptr.columns:
        st.dataframe(ptr[ptr["player_id"] == sel], use_container_width=True)
    else:
        st.warning("player_transfer.parquet no tiene columna player_id.")
