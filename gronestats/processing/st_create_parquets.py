from pathlib import Path

import pandas as pd
import streamlit as st

MASTER_FILE = Path("gronestats/data/master_data/Partidos_Liga 1 Peru_2025_limpio.xlsx")
DETAILS_DIR = Path("gronestats/data/Liga 1 Peru/2025")
PARQUET_DIR = Path("gronestats/data/Liga 1 Peru/2025/parquets")
ALKAGRONE_FILE = Path("gronestats/data/master_data/BD Alkagrone 2025.xlsx")


@st.cache_data
def load_master() -> pd.DataFrame:
    if not MASTER_FILE.exists():
        st.error(f"No se encontró el archivo maestro: {MASTER_FILE}")
        return pd.DataFrame()
    df = pd.read_excel(MASTER_FILE)
    for col in ["match_id", "home_id", "away_id"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df


@st.cache_data
def load_alkagrone_teams() -> pd.DataFrame:
    if not ALKAGRONE_FILE.exists():
        st.error(f"No se encontro el archivo BD Alkagrone: {ALKAGRONE_FILE}")
        return pd.DataFrame()
    try:
        return pd.read_excel(ALKAGRONE_FILE, sheet_name="Equipos")
    except Exception as exc:
        st.error(f"No se pudo leer {ALKAGRONE_FILE} (Equipos): {exc}")
        return pd.DataFrame()


def load_details(match_id: str) -> dict[str, pd.DataFrame]:
    file_path = DETAILS_DIR / f"Sofascore_{match_id}.xlsx"
    if not file_path.exists():
        st.error(f"No existe el archivo de detalles: {file_path}")
        return {}
    try:
        return pd.read_excel(file_path, sheet_name=None)
    except Exception as exc:
        st.error(f"No se pudo leer {file_path}: {exc}")
        return {}


def _coalesce_columns(df: pd.DataFrame, target: str, aliases: list[str]) -> pd.DataFrame:
    work = df.copy()
    cols = [c for c in aliases if c in work.columns]
    if not cols:
        return work
    if target not in work.columns:
        work[target] = None
    for c in cols:
        work[target] = work[target].fillna(work[c])
    drop_cols = [c for c in cols if c != target]
    return work.drop(columns=drop_cols, errors="ignore")


def _normalize_player_stats_df(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work = _coalesce_columns(work, "player_id", ["playerId", "id", "player id", "player_id", "__pid"])
    work = _coalesce_columns(work, "name", ["name", "player", "player_name", "__name"])
    work = _coalesce_columns(
        work,
        "short_name",
        ["shortName", "short_name", "short name", "shortname", "SHORTNAME", "SHORT_NAME"],
    )
    work = _coalesce_columns(work, "team_id", ["teamId", "team id", "team_id"])
    work = _coalesce_columns(work, "position", ["position", "pos"])
    work = _coalesce_columns(work, "dateOfBirth", ["dateOfBirthTimestamp", "dateOfBirth", "dob", "birthTimestamp"])
    if "dateOfBirth" in work.columns:
        dob_series = work["dateOfBirth"]
        dob_num = pd.to_numeric(dob_series, errors="coerce")
        dt_num = pd.to_datetime(dob_num, unit="s", errors="coerce")
        mask_num = dob_num.notna()
        dt = dt_num.copy()
        dt.loc[~mask_num] = pd.to_datetime(dob_series[~mask_num], errors="coerce")
        work["dateOfBirth"] = dt.dt.strftime("%d/%m/%Y")
        ref = pd.Timestamp("2026-01-01")
        work["age_enero_2026"] = ((ref - dt).dt.days / 365.25).round(1)
    return work


def _normalize_id_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    as_int = numeric.dropna().astype("Int64").astype(str)
    result = series.astype(str).str.strip()
    result.loc[numeric.notna()] = as_int
    result = result.str.replace(".0", "", regex=False)
    return result


def _normalize_match_datetime(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        dt = pd.to_datetime(series, errors="coerce")
        dt = dt - pd.Timedelta(hours=5)
        return dt.dt.strftime("%d/%m/%Y %H:%M")

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        dt = pd.to_datetime(series, errors="coerce")
        dt = dt - pd.Timedelta(hours=5)
        return dt.dt.strftime("%d/%m/%Y %H:%M")

    max_val = numeric.abs().max()
    if max_val >= 1_000_000_000_000_000:
        unit = "ns"
    elif max_val >= 1_000_000_000_000:
        unit = "ms"
    else:
        unit = "s"

    dt_num = pd.to_datetime(numeric, unit=unit, errors="coerce")
    dt_txt = pd.to_datetime(series, errors="coerce")
    dt = dt_num.copy()
    dt.loc[numeric.isna()] = dt_txt[numeric.isna()]
    dt = dt - pd.Timedelta(hours=5)
    return dt.dt.strftime("%d/%m/%Y %H:%M")


def render_schema_section(title: str, source_df: pd.DataFrame, schema_df: pd.DataFrame) -> None:
    st.subheader(title)
    st.caption("Columnas completas (fuente)")
    st.write(f"Filas: {len(source_df)}")
    st.dataframe(source_df, use_container_width=True)
    st.caption("Esquema parquet")
    st.write(f"Filas: {len(schema_df)}")
    st.dataframe(schema_df, use_container_width=True)


def _round_float_columns(df: pd.DataFrame, decimals: int = 2) -> pd.DataFrame:
    if df.empty:
        return df
    float_cols = [c for c in df.columns if pd.api.types.is_float_dtype(df[c])]
    if not float_cols:
        return df
    work = df.copy()
    work[float_cols] = work[float_cols].round(decimals)
    return work


def _scale_prices_to_budget(
    prices: pd.Series,
    target_budget: float = 85.0,
    squad_size: int = 14,
    min_price: float = 5.0,
    max_price: float = 9.5,
    stretch: float = 1.25,
) -> pd.Series:
    prices_num = pd.to_numeric(prices, errors="coerce")
    mean_price = prices_num.mean()
    if pd.isna(mean_price) or mean_price <= 0:
        return prices
    target_mean = target_budget / squad_size
    scale = target_mean / mean_price
    scaled_prices = prices_num * scale
    if stretch and stretch != 1.0:
        center = scaled_prices.mean()
        scaled_prices = center + (scaled_prices - center) * stretch
    scaled_prices = scaled_prices.clip(min_price, max_price)
    current_mean = scaled_prices.mean()
    if current_mean and current_mean > 0:
        adjustment = target_mean / current_mean
        scaled_prices = (scaled_prices * adjustment).clip(min_price, max_price)
    return scaled_prices.round(1)


def _stretch_goalkeeper_prices(
    prices: pd.Series,
    positions: pd.Series,
    target_max: float = 6.6,
    min_price: float = 5.5,
) -> pd.Series:
    if prices.empty or positions is None:
        return prices
    pos = positions.astype(str).str.strip().str.upper()
    mask = pos == "G"
    if not mask.any():
        return prices
    gk_prices = pd.to_numeric(prices[mask], errors="coerce")
    min_gk = gk_prices.min()
    max_gk = gk_prices.max()
    if pd.isna(min_gk) or pd.isna(max_gk) or max_gk <= min_gk:
        return prices
    scale = (target_max - min_price) / (max_gk - min_gk)
    adjusted = prices.copy()
    adjusted.loc[mask] = (gk_prices - min_gk) * scale + min_price
    adjusted.loc[mask] = adjusted.loc[mask].clip(min_price, target_max)
    return adjusted


def _remap_prices_by_position_quantiles(
    prices: pd.Series,
    positions: pd.Series,
    minutes: pd.Series,
    min_price_all: float = 5.0,
    max_price_all: float = 9.8,
) -> pd.Series:
    prices_num = pd.to_numeric(prices, errors="coerce")
    pos = positions.astype(str).str.strip().str.upper()
    minutes_num = pd.to_numeric(minutes, errors="coerce").fillna(0)
    result = prices_num.copy()

    invalid_mask = minutes_num < 90
    result.loc[invalid_mask] = min_price_all

    ranges = {
        "D": [(0.0, 0.20, 5.0, 5.0), (0.20, 0.70, 5.0, 5.9), (0.70, 0.92, 6.4, 7.0), (0.92, 1.0, 7.0, 7.9)],
        "M": [(0.0, 0.20, 5.8, 6.4), (0.20, 0.60, 6.4, 7.2), (0.60, 0.85, 7.2, 8.2), (0.85, 1.0, 8.2, 8.9)],
        "F": [(0.0, 0.25, 6.0, 6.9), (0.25, 0.65, 6.9, 7.9), (0.65, 0.90, 7.9, 8.8), (0.90, 1.0, 8.8, 9.8)],
    }

    for position, segments in ranges.items():
        pos_mask = (pos == position) & ~invalid_mask
        if not pos_mask.any():
            continue
        q = prices_num[pos_mask].rank(pct=True, method="average")
        mapped = pd.Series(index=q.index, dtype="float64")
        for q0, q1, a, b in segments:
            if q1 <= q0:
                continue
            seg_mask = (q > q0) & (q <= q1) if q0 > 0 else (q <= q1)
            if not seg_mask.any():
                continue
            denom = q1 - q0
            mapped.loc[seg_mask] = a + (q[seg_mask] - q0) / denom * (b - a)
        mapped = mapped.fillna(min_price_all)
        result.loc[mapped.index] = mapped

    return result.clip(min_price_all, max_price_all)


def apply_price_outlier_corrections(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    required_cols = {
        "price",
        "position",
        "minutesplayed",
        "goals_pm",
        "assists_pm",
        "penaltywon_pm",
        "penaltyconceded_pm",
        "fouls_pm",
        "saves_pm",
        "penaltysave_pm",
    }
    missing = required_cols.difference(df.columns)
    if missing:
        return df

    work = df.copy()
    pos = work["position"].astype(str).str.strip().str.upper()
    minutes = pd.to_numeric(work["minutesplayed"], errors="coerce").fillna(0)
    avail = (minutes / 2500.0).pow(0.5).clip(0.25, 1.15)

    goals = pd.to_numeric(work["goals_pm"], errors="coerce").fillna(0)
    assists = pd.to_numeric(work["assists_pm"], errors="coerce").fillna(0)
    penalty_won = pd.to_numeric(work["penaltywon_pm"], errors="coerce").fillna(0)
    penalty_conceded = pd.to_numeric(work["penaltyconceded_pm"], errors="coerce").fillna(0)
    fouls = pd.to_numeric(work["fouls_pm"], errors="coerce").fillna(0)
    saves = pd.to_numeric(work["saves_pm"], errors="coerce").fillna(0)
    penalty_save = pd.to_numeric(work["penaltysave_pm"], errors="coerce").fillna(0)
    price = pd.to_numeric(work["price"], errors="coerce")

    performance_score = pd.Series(0.0, index=work.index, dtype="float64")
    mask_f = pos == "F"
    mask_m = pos == "M"
    mask_d = pos == "D"
    mask_g = pos == "G"
    performance_score.loc[mask_f] = (
        4.0 * goals
        + 3.0 * assists
        + 1.0 * penalty_won
        - 1.2 * penalty_conceded
        - 0.3 * fouls
    ).loc[mask_f] * avail.loc[mask_f]
    performance_score.loc[mask_m] = (
        3.2 * goals
        + 3.2 * assists
        + 0.8 * penalty_won
        - 1.2 * penalty_conceded
        - 0.25 * fouls
    ).loc[mask_m] * avail.loc[mask_m]
    performance_score.loc[mask_d] = (
        4.0 * goals
        + 2.5 * assists
        + 0.6 * penalty_won
        - 1.2 * penalty_conceded
        - 0.25 * fouls
    ).loc[mask_d] * avail.loc[mask_d]
    performance_score.loc[mask_g] = (
        0.35 * saves
        + 1.5 * penalty_save
        - 1.0 * penalty_conceded
        - 0.1 * fouls
    ).loc[mask_g] * avail.loc[mask_g]

    score_rank = performance_score.groupby(pos).rank(pct=True, method="average")
    price_rank = price.groupby(pos).rank(pct=True, method="average")
    rank_gap = price_rank - score_rank

    outlier = rank_gap.abs() >= 0.25
    m_overpriced = (pos == "M") & (rank_gap >= 0.15)
    adjust_mask = outlier | m_overpriced

    suggested_price = pd.Series(index=work.index, dtype="float64")
    for position in pos.dropna().unique():
        group_mask = pos == position
        if not group_mask.any():
            continue
        group_prices = price[group_mask].dropna()
        if group_prices.empty:
            continue
        group_ranks = score_rank[group_mask].clip(0, 1).fillna(0)
        suggested_price.loc[group_mask] = group_ranks.apply(
            lambda q: group_prices.quantile(q, interpolation="linear")
        )

    new_price = price.copy()
    blended = (0.7 * suggested_price + 0.3 * price).round(1)
    adjustable_mask = adjust_mask & suggested_price.notna() & price.notna()
    new_price.loc[adjustable_mask & mask_g] = blended.loc[adjustable_mask & mask_g].clip(5.5, 6.6)
    new_price.loc[adjustable_mask & mask_m] = blended.loc[adjustable_mask & mask_m].clip(5.0, 8.9)
    new_price.loc[adjustable_mask & mask_d] = blended.loc[adjustable_mask & mask_d].clip(5.0, 7.9)
    new_price.loc[adjustable_mask & ~mask_g & ~mask_m & ~mask_d] = blended.loc[
        adjustable_mask & ~mask_g & ~mask_m & ~mask_d
    ].clip(5.0, 9.8)
    new_price = new_price.round(1)

    adjusted_mask = (new_price != price) & adjustable_mask
    work["price"] = new_price
    work.attrs["price_corrections"] = {
        "total": int(adjusted_mask.sum()),
        "by_position": adjusted_mask.groupby(pos).sum().to_dict(),
    }
    return work


def _apply_price_corrections_to_players(
    players_df: pd.DataFrame,
    fantasy_df: pd.DataFrame,
) -> pd.DataFrame:
    if players_df.empty or fantasy_df.empty or "player_id" not in players_df.columns:
        return players_df
    players_work = players_df.copy()
    fantasy_work = fantasy_df.copy()
    if "player_id" in players_work.columns:
        players_work["_player_id_key"] = _normalize_id_series(players_work["player_id"])
    if "player_id" in fantasy_work.columns:
        fantasy_work["_player_id_key"] = _normalize_id_series(fantasy_work["player_id"])
    if "_player_id_key" not in players_work.columns or "_player_id_key" not in fantasy_work.columns:
        return players_df
    merge_cols = [
        "player_id",
        "price",
        "minutesplayed",
        "goals_pm",
        "assists_pm",
        "penaltywon_pm",
        "penaltyconceded_pm",
        "fouls_pm",
        "saves_pm",
        "penaltysave_pm",
    ]
    available_cols = [c for c in merge_cols if c in fantasy_work.columns]
    if "price" not in available_cols:
        return players_df
    enriched = players_work.merge(
        fantasy_work[available_cols + ["_player_id_key"]],
        on="_player_id_key",
        how="left",
        suffixes=("", "_fantasy"),
        sort=False,
    )
    enriched = apply_price_outlier_corrections(enriched)
    updated = players_df.copy()
    updated["price"] = enriched["price"]
    return updated


def export_parquet_tables(tables: dict[str, pd.DataFrame], output_dir: Path) -> tuple[list[Path], list[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    errors: list[str] = []
    for name, df in tables.items():
        if df.empty:
            continue
        out_path = output_dir / f"{name}.parquet"
        try:
            rounded = _round_float_columns(df, decimals=2)
            rounded.to_parquet(out_path, index=False)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            continue
        saved.append(out_path)
    return saved, errors


@st.cache_data
def load_all_player_stats() -> pd.DataFrame:
    rows = []
    if not DETAILS_DIR.exists():
        return pd.DataFrame()
    for f in DETAILS_DIR.glob("Sofascore_*.xlsx"):
        try:
            df_ps = pd.read_excel(f, sheet_name="Player Stats")
        except Exception:
            continue
        if df_ps.empty:
            continue
        df_ps = _normalize_player_stats_df(df_ps)
        df_ps.columns = [c.upper() for c in df_ps.columns]
        if "MATCH_ID" not in df_ps.columns:
            df_ps["MATCH_ID"] = f.stem.replace("Sofascore_", "")
        rows.append(df_ps)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


@st.cache_data
def load_team_stats() -> pd.DataFrame:
    rows = []
    if not DETAILS_DIR.exists():
        return pd.DataFrame()
    for f in DETAILS_DIR.glob("Sofascore_*.xlsx"):
        try:
            df_team = pd.read_excel(f, sheet_name="Team Stats")
        except Exception:
            continue
        if df_team.empty:
            continue
        df_team.columns = [c.upper() for c in df_team.columns]
        if "MATCH_ID" not in df_team.columns:
            df_team["MATCH_ID"] = f.stem.replace("Sofascore_", "")
        rows.append(df_team)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


@st.cache_data
def load_parquet_table(name: str) -> pd.DataFrame:
    path = PARQUET_DIR / f"{name}.parquet"
    if not path.exists():
        st.error(f"No existe el parquet: {path}")
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        st.error(f"No se pudo leer {path}: {exc}")
        return pd.DataFrame()


def _safe_per_match(series: pd.Series, matches: pd.Series) -> pd.Series:
    safe_matches = matches.where(matches > 0)
    return series.div(safe_matches).fillna(0)


def calculate_price(row: pd.Series) -> float:
    position = str(row.get("position", "")).strip().upper()
    base_map = {"G": 4.0, "D": 4.5, "M": 5.5, "F": 7.0}
    goals_map = {"F": 0.8, "M": 0.5, "D": 0.7, "G": 0.1}
    assists_map = {"M": 0.8, "F": 0.4, "D": 0.2, "G": 0.05}
    base = base_map.get(position, 5.0)
    goals = float(row.get("goals_pm", 0) or 0)
    assists = float(row.get("assists_pm", 0) or 0)
    saves = float(row.get("saves_pm", 0) or 0)
    fouls = float(row.get("fouls_pm", 0) or 0)
    penalty_won = float(row.get("penaltywon_pm", 0) or 0)
    penalty_save = float(row.get("penaltysave_pm", 0) or 0)
    penalty_conceded = float(row.get("penaltyconceded_pm", 0) or 0)
    minutes = float(row.get("minutesplayed", 0) or 0)
    matches = float(row.get("matches_played", 0) or 0)
    attack = goals_map.get(position, 0.0) * goals * 1.5 + assists_map.get(position, 0.0) * assists * 1.3
    if position == "G":
        keeper = 0.55 * saves
        keeper += 0.35 * (minutes / 1000.0)
        keeper += 0.08 * matches
        keeper += 0.5 * penalty_save
        keeper -= 0.04 * fouls
        keeper -= 0.2 * penalty_conceded
        price = base + keeper
        return max(3.5, round(price, 2))

    foul_penalty = 0.12 if position == "D" else 0.08
    other = 0.0
    other += 0.4 * penalty_save
    other += 0.3 * penalty_won
    other -= foul_penalty * fouls
    other -= 0.4 * penalty_conceded
    other += 0.05 * (minutes / 1000.0)
    other += 0.03 * matches
    age = None
    if "age_enero_2026" in row and pd.notna(row["age_enero_2026"]):
        age = float(row["age_enero_2026"])
    elif "age_jan_2026" in row and pd.notna(row["age_jan_2026"]):
        age = float(row["age_jan_2026"])
    if age is not None:
        if age < 23:
            other += 0.3
        elif age > 32:
            other -= 0.5
    price = base + 0.7 * attack + 0.3 * other
    return max(3.5, round(price, 2))


def build_players_fantasy_df(players_df: pd.DataFrame, totals_df: pd.DataFrame) -> pd.DataFrame:
    if players_df.empty or totals_df.empty:
        return pd.DataFrame()
    favorite_team_ids = {2302, 2305, 2311}
    players = players_df.copy()
    totals = totals_df.copy()
    if "player_id" in players.columns:
        players["player_id"] = _normalize_id_series(players["player_id"])
    if "PLAYER_ID" in totals.columns:
        totals["PLAYER_ID"] = _normalize_id_series(totals["PLAYER_ID"])
    fantasy_df = players.merge(
        totals,
        left_on="player_id",
        right_on="PLAYER_ID",
        how="left",
    )
    if "position" not in fantasy_df.columns and "POSITION" in fantasy_df.columns:
        fantasy_df["position"] = fantasy_df["POSITION"]
    for source, target in [
        ("GOALS", "goals"),
        ("ASSISTS", "assists"),
        ("SAVES", "saves"),
        ("FOULS", "fouls"),
        ("PENALTYWON", "penaltywon"),
        ("PENALTYSAVE", "penaltysave"),
        ("PENALTYCONCEDED", "penaltyconceded"),
        ("MINUTESPLAYED", "minutesplayed"),
        ("MATCHES_PLAYED", "matches_played"),
    ]:
        if source in fantasy_df.columns:
            fantasy_df[target] = pd.to_numeric(fantasy_df[source], errors="coerce").fillna(0)
        else:
            fantasy_df[target] = 0
    fantasy_df = fantasy_df[fantasy_df["minutesplayed"] > 10].copy()
    fantasy_df["goals_pm"] = _safe_per_match(fantasy_df["goals"], fantasy_df["matches_played"])
    fantasy_df["assists_pm"] = _safe_per_match(fantasy_df["assists"], fantasy_df["matches_played"])
    fantasy_df["saves_pm"] = _safe_per_match(fantasy_df["saves"], fantasy_df["matches_played"])
    fantasy_df["fouls_pm"] = _safe_per_match(fantasy_df["fouls"], fantasy_df["matches_played"])
    fantasy_df["penaltywon_pm"] = _safe_per_match(fantasy_df["penaltywon"], fantasy_df["matches_played"])
    fantasy_df["penaltysave_pm"] = _safe_per_match(fantasy_df["penaltysave"], fantasy_df["matches_played"])
    fantasy_df["penaltyconceded_pm"] = _safe_per_match(fantasy_df["penaltyconceded"], fantasy_df["matches_played"])
    fantasy_df["price"] = fantasy_df.apply(calculate_price, axis=1)
    fantasy_df["is_valid"] = fantasy_df["minutesplayed"] >= 90
    valid_players = fantasy_df[fantasy_df["is_valid"]].copy()
    invalid_players = fantasy_df[~fantasy_df["is_valid"]].copy()
    min_price_all = 5.0
    max_price_all = 9.8
    if not valid_players.empty:
        bonus_mask = pd.Series(False, index=valid_players.index)
        if (
            "team_id" in valid_players.columns
            and "matches_played" in valid_players.columns
            and "minutesplayed" in valid_players.columns
        ):
            team_id_num = pd.to_numeric(valid_players["team_id"], errors="coerce")
            matches_num = pd.to_numeric(valid_players["matches_played"], errors="coerce").fillna(0)
            minutes_num = pd.to_numeric(valid_players["minutesplayed"], errors="coerce").fillna(0)
            bonus_mask = (
                team_id_num.isin(favorite_team_ids)
                & (matches_num > 30)
                & (minutes_num > 1600)
            )
            if bonus_mask.any() and "position" in valid_players.columns:
                pos_upper = valid_players["position"].astype(str).str.strip().str.upper()
                top_bonus = pd.Series(False, index=valid_players.index)
                for pos in ["G", "D", "M", "F"]:
                    pos_mask = bonus_mask & (pos_upper == pos)
                    if not pos_mask.any():
                        continue
                    top_idx = (
                        valid_players.loc[pos_mask, "price"]
                        .sort_values(ascending=False)
                        .head(2)
                        .index
                    )
                    top_bonus.loc[top_idx] = True
                bonus_mask = top_bonus
            valid_players.loc[bonus_mask, "price"] = valid_players.loc[bonus_mask, "price"] + 1.0
        valid_players["price"] = _remap_prices_by_position_quantiles(
            valid_players["price"],
            valid_players["position"],
            valid_players["minutesplayed"],
            min_price_all=min_price_all,
            max_price_all=max_price_all,
        )
        valid_players["price"] = valid_players["price"].clip(min_price_all, max_price_all)
        valid_players.loc[bonus_mask, "price"] = valid_players.loc[bonus_mask, "price"] + 1.0
        valid_players["price"] = valid_players["price"].clip(min_price_all, max_price_all)
        pos_upper = valid_players["position"].astype(str).str.strip().str.upper()
        m_mask = pos_upper == "M"
        d_mask = pos_upper == "D"
        valid_players.loc[m_mask, "price"] = valid_players.loc[m_mask, "price"].clip(upper=8.9)
        valid_players.loc[d_mask, "price"] = valid_players.loc[d_mask, "price"].clip(upper=7.9)
        valid_players["price"] = _stretch_goalkeeper_prices(
            valid_players["price"],
            valid_players["position"],
            target_max=6.6,
            min_price=5.5,
        )
    invalid_players["price"] = min_price_all
    fantasy_df = pd.concat([valid_players, invalid_players], ignore_index=True)
    fantasy_df["price"] = fantasy_df["price"].clip(min_price_all, max_price_all)
    fantasy_df["price"] = fantasy_df["price"].round(1)
    fantasy_df["player_id"] = _normalize_id_series(fantasy_df["player_id"])
    if "team_id" in fantasy_df.columns:
        fantasy_df["team_id"] = _normalize_id_series(fantasy_df["team_id"])
    fantasy_df = fantasy_df.dropna(subset=["player_id", "position"])
    fantasy_df = fantasy_df.drop_duplicates(subset=["player_id"])
    fantasy_df = _round_float_columns(fantasy_df, decimals=2)
    fantasy_df["price"] = fantasy_df["price"].round(1)
    fantasy_df = apply_price_outlier_corrections(fantasy_df)
    correction_stats = fantasy_df.attrs.get("price_corrections", {})
    fantasy_df["price"] = fantasy_df["price"].round(1)
    keep_cols = [
        c
        for c in [
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
        if c in fantasy_df.columns
    ]
    result = fantasy_df[keep_cols].copy()
    if correction_stats:
        result.attrs["price_corrections"] = correction_stats
    return result


@st.cache_data
def load_player_rows() -> pd.DataFrame:
    all_stats = load_all_player_stats()
    if all_stats.empty:
        return pd.DataFrame()
    cols_required = [c for c in ["NAME", "PLAYER_ID", "POSITION", "TEAM_ID", "DATEOFBIRTH"] if c in all_stats.columns]
    if not cols_required:
        return pd.DataFrame()
    cols_keep = cols_required + [
        c for c in ["SHORT_NAME", "SHORTNAME", "AGE_JAN_2026"] if c in all_stats.columns
    ]
    df = all_stats[cols_keep].copy()
    df = df.dropna(subset=cols_required)
    if "PLAYER_ID" in df.columns:
        df = df.drop_duplicates(subset=["PLAYER_ID"])
    else:
        df = df.drop_duplicates()
    df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data
def build_matches_schema(df_master: pd.DataFrame, normalize_date: bool = True) -> pd.DataFrame:
    if df_master.empty:
        return pd.DataFrame()
    cols = [
        "match_id",
        "round_number",
        "season",
        "home_id",
        "away_id",
        "home",
        "away",
        "home_score",
        "away_score",
        "resultado_final",
        "fecha",
        "estadio",
        "ciudad",
        "arbitro",
    ]
    cols = [c for c in cols if c in df_master.columns]
    result = df_master[cols].copy()
    if normalize_date and "fecha" in result.columns:
        result["fecha"] = _normalize_match_datetime(result["fecha"]).astype("string")
    return result


@st.cache_data
def build_teams_schema(df_teams: pd.DataFrame) -> pd.DataFrame:
    if df_teams.empty:
        return pd.DataFrame()
    work = df_teams.copy()
    work = _coalesce_columns(work, "team_id", ["team_id", "teamId", "team id", "id", "ID_Equipo", "ID Equipo"])
    work = _coalesce_columns(
        work,
        "short_name",
        ["team_name", "team", "name", "equipo", "club", "Nombre_Corto", "Nombre corto"],
    )
    work = _coalesce_columns(work, "full_name", ["Nombre_Completo", "Nombre completo", "nombre_completo"])
    work = _coalesce_columns(
        work,
        "team_colors",
        ["team_colors", "team_color", "colors", "color", "colores", "Color"],
    )
    work = _coalesce_columns(
        work,
        "is_altitude_team",
        ["Es_Equipo_Altura", "Es Equipo Altura", "equipo_altura"],
    )
    work = _coalesce_columns(
        work,
        "competitiveness_level",
        ["Nivel_Competitividad", "Nivel Competitividad"],
    )
    work = _coalesce_columns(
        work,
        "stadium_id",
        ["ID_Estadio_Principal", "ID Estadio Principal"],
    )
    work = _coalesce_columns(
        work,
        "stadium_name_city",
        ["Nombre_Estadio / Ciudad", "Nombre Estadio / Ciudad", "Nombre_Estadio_Ciudad"],
    )
    work = _coalesce_columns(work, "province", ["Provincia_Equipo", "Provincia Equipo", "provincia"])
    work = _coalesce_columns(work, "department", ["Departamento", "departamento"])
    work = _coalesce_columns(work, "region", ["Region", "Regi\u00f3n", "region", "regi\u00f3n"])
    cols = [
        c
        for c in [
            "team_id",
            "short_name",
            "full_name",
            "team_colors",
            "is_altitude_team",
            "competitiveness_level",
            "stadium_id",
            "stadium_name_city",
            "province",
            "department",
            "region",
        ]
        if c in work.columns
    ]
    if not cols:
        return pd.DataFrame()
    return work[cols].copy()


@st.cache_data
def build_player_match_schema(df_player_stats: pd.DataFrame) -> pd.DataFrame:
    if df_player_stats.empty:
        return pd.DataFrame()
    cols = [
        "MATCH_ID",
        "PLAYER_ID",
        "NAME",
        "TEAM_ID",
        "POSITION",
        "MINUTESPLAYED",
        "GOALS",
        "GOALASSIST",
        "YELLOWCARDS",
        "REDCARDS",
        "SAVES",
        "FOULS",
        "PENALTYWON",
        "PENALTYSAVE",
        "PENALTYCONCEDED",
        "RATING",
    ]
    cols = [c for c in cols if c in df_player_stats.columns]
    return df_player_stats[cols].copy()


@st.cache_data
def build_player_totals_schema(df_player_match: pd.DataFrame) -> pd.DataFrame:
    if df_player_match.empty:
        return pd.DataFrame()
    if "PLAYER_ID" not in df_player_match.columns or "MATCH_ID" not in df_player_match.columns:
        return pd.DataFrame()
    work = df_player_match.copy()
    work["PLAYER_ID"] = _normalize_id_series(work["PLAYER_ID"])
    work["MATCH_ID"] = _normalize_id_series(work["MATCH_ID"])
    goals_col = next((c for c in ["GOALS", "GOAL"] if c in work.columns), None)
    assists_col = next((c for c in ["GOALASSIST", "ASSISTS", "ASSIST"] if c in work.columns), None)
    saves_col = next((c for c in ["SAVES", "SAVE"] if c in work.columns), None)
    fouls_col = next((c for c in ["FOULS", "FOUL"] if c in work.columns), None)
    minutes_col = next((c for c in ["MINUTESPLAYED", "MINUTES_PLAYED", "MINUTES"] if c in work.columns), None)
    penalty_won_col = next((c for c in ["PENALTYWON", "PENALTY_WON"] if c in work.columns), None)
    penalty_save_col = next((c for c in ["PENALTYSAVE", "PENALTY_SAVE"] if c in work.columns), None)
    penalty_conceded_col = next((c for c in ["PENALTYCONCEDED", "PENALTY_CONCEDED"] if c in work.columns), None)
    if goals_col is None or assists_col is None:
        return pd.DataFrame()
    if saves_col is None:
        work["SAVES"] = 0
        saves_col = "SAVES"
    if fouls_col is None:
        work["FOULS"] = 0
        fouls_col = "FOULS"
    if minutes_col is None:
        work["MINUTESPLAYED"] = 0
        minutes_col = "MINUTESPLAYED"
    if penalty_won_col is None:
        work["PENALTYWON"] = 0
        penalty_won_col = "PENALTYWON"
    if penalty_save_col is None:
        work["PENALTYSAVE"] = 0
        penalty_save_col = "PENALTYSAVE"
    if penalty_conceded_col is None:
        work["PENALTYCONCEDED"] = 0
        penalty_conceded_col = "PENALTYCONCEDED"
    work[goals_col] = pd.to_numeric(work[goals_col], errors="coerce").fillna(0)
    work[assists_col] = pd.to_numeric(work[assists_col], errors="coerce").fillna(0)
    work[saves_col] = pd.to_numeric(work[saves_col], errors="coerce").fillna(0)
    work[fouls_col] = pd.to_numeric(work[fouls_col], errors="coerce").fillna(0)
    work[minutes_col] = pd.to_numeric(work[minutes_col], errors="coerce").fillna(0)
    work[penalty_won_col] = pd.to_numeric(work[penalty_won_col], errors="coerce").fillna(0)
    work[penalty_save_col] = pd.to_numeric(work[penalty_save_col], errors="coerce").fillna(0)
    work[penalty_conceded_col] = pd.to_numeric(work[penalty_conceded_col], errors="coerce").fillna(0)
    totals = (
        work.dropna(subset=["PLAYER_ID"])
        .groupby("PLAYER_ID", as_index=False)
        .agg(
            GOALS=(goals_col, "sum"),
            ASSISTS=(assists_col, "sum"),
            SAVES=(saves_col, "sum"),
            FOULS=(fouls_col, "sum"),
            MINUTESPLAYED=(minutes_col, "sum"),
            PENALTYWON=(penalty_won_col, "sum"),
            PENALTYSAVE=(penalty_save_col, "sum"),
            PENALTYCONCEDED=(penalty_conceded_col, "sum"),
            MATCHES_PLAYED=("MATCH_ID", "nunique"),
        )
        .sort_values("PLAYER_ID")
    )
    return totals


@st.cache_data
def build_player_team_schema(df_player_stats: pd.DataFrame) -> pd.DataFrame:
    if df_player_stats.empty:
        return pd.DataFrame()
    cols = [c for c in ["PLAYER_ID", "TEAM_ID", "NAME", "POSITION"] if c in df_player_stats.columns]
    if not cols:
        return pd.DataFrame()
    df = df_player_stats[cols].copy()
    if "PLAYER_ID" in df.columns:
        df["PLAYER_ID"] = _normalize_id_series(df["PLAYER_ID"])
    if "TEAM_ID" in df.columns:
        df["TEAM_ID"] = _normalize_id_series(df["TEAM_ID"])
    drop_subset = [c for c in ["PLAYER_ID", "TEAM_ID"] if c in df.columns]
    if "POSITION" in df.columns:
        drop_subset.append("POSITION")
    df = df.dropna(subset=drop_subset)
    if "TEAM_ID" in df.columns:
        df = df[~df["TEAM_ID"].astype(str).str.strip().str.lower().isin(["nan", "none", ""])]
    if "POSITION" in df.columns:
        df = df[~df["POSITION"].astype(str).str.strip().str.lower().isin(["nan", "none", ""])]
    dedupe_cols = [c for c in ["PLAYER_ID", "TEAM_ID", "POSITION"] if c in df.columns]
    if dedupe_cols:
        return df.drop_duplicates(subset=dedupe_cols)
    return df


@st.cache_data
def build_player_transfer_schema(
    player_team_df: pd.DataFrame,
    players_df: pd.DataFrame,
    teams_df: pd.DataFrame,
) -> pd.DataFrame:
    if player_team_df.empty:
        return pd.DataFrame()
    work = player_team_df.copy()
    if "PLAYER_ID" in work.columns:
        work["PLAYER_ID"] = _normalize_id_series(work["PLAYER_ID"])
    if "TEAM_ID" in work.columns:
        work["TEAM_ID"] = _normalize_id_series(work["TEAM_ID"])
    transfer_ids = (
        work.dropna(subset=["PLAYER_ID", "TEAM_ID"])
        .groupby("PLAYER_ID")["TEAM_ID"]
        .nunique()
    )
    transfer_ids = transfer_ids[transfer_ids > 1].index
    transfer_df = work[work["PLAYER_ID"].isin(transfer_ids)].copy()
    if not players_df.empty and "player_id" in players_df.columns:
        players_lookup = players_df.copy()
        players_lookup["player_id"] = _normalize_id_series(players_lookup["player_id"])
        transfer_df = transfer_df.merge(
            players_lookup,
            left_on="PLAYER_ID",
            right_on="player_id",
            how="left",
            suffixes=("", "_players"),
        )
    if not teams_df.empty and "team_id" in teams_df.columns:
        teams_lookup = teams_df.copy()
        teams_lookup["team_id"] = _normalize_id_series(teams_lookup["team_id"])
        transfer_df = transfer_df.merge(
            teams_lookup,
            left_on="TEAM_ID",
            right_on="team_id",
            how="left",
            suffixes=("", "_teams"),
        )
    return transfer_df


def main() -> None:
    st.title("Fantasy Liga 1 2026 - Dataframes base")
    st.caption("Visualizacion de esquemas previos a exportar a parquet.")

    df_master = load_master()
    if df_master.empty:
        st.stop()

    matches_df = build_matches_schema(df_master, normalize_date=True)  # Parquet export: matches_df
    teams_source_df = load_alkagrone_teams()
    teams_df = build_teams_schema(teams_source_df)  # Parquet export: teams_df
    player_stats_df = load_all_player_stats()
    players_df = load_player_rows()  # Parquet export: players_df
    player_match_df = build_player_match_schema(player_stats_df)  # Parquet export: player_match_df
    player_totals_df = build_player_totals_schema(player_match_df)  # Parquet export: player_totals_df
    player_team_df = build_player_team_schema(player_stats_df)  # Parquet export: player_team_df
    players_fantasy_df = build_players_fantasy_df(players_df, player_totals_df)  # Parquet export: players_fantasy_df
    player_transfer_df = build_player_transfer_schema(  # Parquet export: player_transfer_df
        player_team_df,
        players_df,
        teams_df,
    )
    players_df = _apply_price_corrections_to_players(players_df, players_fantasy_df)
    team_stats_df = load_team_stats()  # Parquet export: team_stats_df

    tab_esquemas, tab_parquets, tab_cruce, tab_partidos = st.tabs(
        ["Esquemas", "Precios fantasy", "Cruce info", "Detalle partido"]
    )

    with tab_esquemas:
        if st.button("Exportar parquets a data/Liga 1 Peru/2025/parquets"):
            with st.spinner("Exportando parquets..."):
                saved, errors = export_parquet_tables(
                    {
                        "matches": matches_df,
                        "teams": teams_df,
                        "players": players_df,
                        "player_match": player_match_df,
                        "player_totals": player_totals_df,
                        "players_fantasy": players_fantasy_df,
                        "player_team": player_team_df,
                        "player_transfer": player_transfer_df,
                        "team_stats": team_stats_df,
                    },
                    PARQUET_DIR,
                )
            if saved:
                st.success(f"Parquets exportados: {len(saved)}")
                st.write([str(path) for path in saved])
            if errors:
                st.error("Errores al exportar algunos parquets:")
                st.write(errors)
        render_schema_section("Matches", df_master, matches_df)
        render_schema_section("Teams", teams_source_df, teams_df)
        render_schema_section("Players", player_stats_df, players_df)
        render_schema_section("Player Match Stats", player_stats_df, player_match_df)
        render_schema_section("Player Totals", player_match_df, player_totals_df)
        render_schema_section("Player Team", player_stats_df, player_team_df)
        render_schema_section("Player Transfers", player_team_df, player_transfer_df)
        render_schema_section("Team Match Stats", team_stats_df, team_stats_df)

    with tab_parquets:
        st.subheader("Parquets Liga 1 2025")
        players_parquet = load_parquet_table("players")
        totals_parquet = load_parquet_table("player_totals")
        matches_parquet = load_parquet_table("player_match")

        st.caption("players")
        st.dataframe(players_parquet, use_container_width=True)
        st.caption("player_totals")
        st.dataframe(totals_parquet, use_container_width=True)
        st.caption("player_match")
        st.dataframe(matches_parquet, use_container_width=True)

        st.subheader("Precios calculados")
        prices_df = build_players_fantasy_df(players_parquet, totals_parquet)
        if prices_df.empty:
            st.info("No hay datos suficientes para calcular precios.")
        else:
            st.dataframe(prices_df, use_container_width=True)
            price_bins = [-float("inf"), 5.0, 6.0, 7.0, 8.0, 9.0, float("inf")]
            price_labels = ["<5", "5-5.9", "6-6.9", "7-7.9", "8-8.9", "9+"]
            price_range = pd.cut(prices_df["price"], bins=price_bins, labels=price_labels, right=False)

            st.caption("Conteo por rango de precio")
            range_counts = (
                price_range.value_counts()
                .reindex(price_labels, fill_value=0)
                .rename_axis("rango")
                .reset_index(name="count")
            )
            st.dataframe(range_counts, use_container_width=True, hide_index=True)

            if "position" in prices_df.columns:
                st.caption("Conteo por posicion y rango")
                pos_range = (
                    prices_df.assign(rango=price_range)
                    .groupby(["position", "rango"], dropna=False)
                    .size()
                    .reset_index(name="count")
                )
                pos_range_pivot = pos_range.pivot(index="position", columns="rango", values="count").fillna(0).astype(int)
                pos_range_pivot = pos_range_pivot.reindex(columns=price_labels, fill_value=0)
                st.dataframe(pos_range_pivot, use_container_width=True)

                st.caption("Promedio y mediana por posicion")
                pos_stats = (
                    prices_df.groupby("position")["price"]
                    .agg(mean="mean", median="median", count="count")
                    .reset_index()
                )
                st.dataframe(pos_stats, use_container_width=True, hide_index=True)

            correction_stats = prices_df.attrs.get("price_corrections", {})
            if correction_stats:
                st.write(f"Ajustes aplicados: {correction_stats.get('total', 0)}")
                by_position = correction_stats.get("by_position", {})
                if by_position:
                    by_pos_df = (
                        pd.Series(by_position)
                        .rename_axis("position")
                        .reset_index(name="count")
                    )
                    st.dataframe(by_pos_df, use_container_width=True, hide_index=True)

            if "price" in prices_df.columns:
                below_min = int((prices_df["price"] < 5.0).sum())
                st.write(f"Precios < 5.0: {below_min}")

    with tab_cruce:
        st.subheader("Resumen por equipo")
        matches_cruce = build_matches_schema(df_master, normalize_date=False)
        if matches_cruce.empty or teams_df.empty:
            st.info("No hay datos suficientes para resumir equipos.")
            st.stop()

        matches_cruce = matches_cruce.copy()
        teams_cruce = teams_df.copy()
        if "home_id" in matches_cruce.columns:
            matches_cruce["home_id"] = _normalize_id_series(matches_cruce["home_id"])
        if "away_id" in matches_cruce.columns:
            matches_cruce["away_id"] = _normalize_id_series(matches_cruce["away_id"])
        if "match_id" in matches_cruce.columns:
            matches_cruce["match_id"] = _normalize_id_series(matches_cruce["match_id"])
        if "team_id" in teams_cruce.columns:
            teams_cruce["team_id"] = _normalize_id_series(teams_cruce["team_id"])

        teams_cruce["label"] = teams_cruce["team_id"]
        if "short_name" in teams_cruce.columns:
            teams_cruce["label"] = teams_cruce["team_id"] + " - " + teams_cruce["short_name"].fillna("")
        elif "full_name" in teams_cruce.columns:
            teams_cruce["label"] = teams_cruce["team_id"] + " - " + teams_cruce["full_name"].fillna("")

        options = teams_cruce.sort_values("label")["label"].dropna().tolist()
        selected_label = st.selectbox("Equipo", options=options, index=0 if options else None)

        if not selected_label:
            st.stop()

        selected_team_id = selected_label.split(" - ")[0]
        team_row = teams_cruce[teams_cruce["team_id"] == selected_team_id]
        st.caption("Ficha del equipo")
        st.dataframe(team_row, use_container_width=True)

        if "home_id" in matches_cruce.columns and "away_id" in matches_cruce.columns:
            team_matches = matches_cruce[
                (matches_cruce["home_id"] == selected_team_id) | (matches_cruce["away_id"] == selected_team_id)
            ].copy()
        else:
            team_matches = pd.DataFrame()

        st.caption("Resumen de partidos")
        st.write(f"Partidos: {len(team_matches)}")

        if not team_matches.empty:
            home_count = (team_matches["home_id"] == selected_team_id).sum()
            away_count = (team_matches["away_id"] == selected_team_id).sum()
            st.write(f"Home: {home_count} | Away: {away_count}")

            if "home_score" in team_matches.columns and "away_score" in team_matches.columns:
                home_mask = team_matches["home_id"] == selected_team_id
                away_mask = team_matches["away_id"] == selected_team_id
                goals_for = team_matches.loc[home_mask, "home_score"].sum() + team_matches.loc[away_mask, "away_score"].sum()
                goals_against = team_matches.loc[home_mask, "away_score"].sum() + team_matches.loc[away_mask, "home_score"].sum()
                st.write(f"Goles a favor: {goals_for} | Goles en contra: {goals_against}")

            cols_show = [
                c
                for c in [
                    "match_id",
                    "round_number",
                    "home",
                    "away",
                    "home_score",
                    "away_score",
                    "resultado_final",
                    "fecha",
                ]
                if c in team_matches.columns
            ]
            st.dataframe(team_matches[cols_show], use_container_width=True)

        st.subheader("Resumen por jugador")
        if player_match_df.empty:
            st.info("No hay datos suficientes para resumir jugadores.")
            st.stop()

        player_matches_df = player_match_df.copy()
        if "PLAYER_ID" in player_matches_df.columns:
            player_matches_df["PLAYER_ID"] = _normalize_id_series(player_matches_df["PLAYER_ID"])
        if "MATCH_ID" in player_matches_df.columns:
            player_matches_df["MATCH_ID"] = _normalize_id_series(player_matches_df["MATCH_ID"])

        if "NAME" in player_matches_df.columns:
            player_labels_df = player_matches_df[["PLAYER_ID", "NAME"]].dropna().drop_duplicates()
            player_labels_df["label"] = player_labels_df["PLAYER_ID"] + " - " + player_labels_df["NAME"].astype(str)
        else:
            player_labels_df = player_matches_df[["PLAYER_ID"]].dropna().drop_duplicates()
            player_labels_df["label"] = player_labels_df["PLAYER_ID"]
        player_options = player_labels_df.sort_values("label")["label"].tolist()
        selected_player_label = st.selectbox("Jugador", options=player_options, index=0 if player_options else None)

        if not selected_player_label:
            st.stop()

        selected_player_id = selected_player_label.split(" - ")[0]
        player_cols = [c for c in ["PLAYER_ID", "NAME", "TEAM_ID", "POSITION"] if c in player_matches_df.columns]
        player_row = player_matches_df[player_matches_df["PLAYER_ID"] == selected_player_id][player_cols].drop_duplicates()
        if "TEAM_ID" in player_row.columns:
            player_row = player_row[~player_row["TEAM_ID"].astype(str).str.strip().str.lower().isin(["nan", "none", ""])]
        st.caption("Ficha del jugador")
        st.dataframe(player_row, use_container_width=True)

        player_rows = player_matches_df[player_matches_df["PLAYER_ID"] == selected_player_id]
        if not player_rows.empty and "MATCH_ID" in player_rows.columns:
            player_match_list = pd.merge(
                matches_cruce,
                player_rows,
                left_on="match_id",
                right_on="MATCH_ID",
                how="inner",
            )
        else:
            player_match_list = pd.DataFrame()

        st.caption("Partidos del jugador")
        st.write(f"Partidos: {len(player_match_list)}")
        if not player_match_list.empty:
            cols_player_show = [
                c
                for c in [
                    "match_id",
                    "round_number",
                    "home",
                    "away",
                    "home_score",
                    "away_score",
                    "resultado_final",
                    "fecha",
                    "MINUTESPLAYED",
                    "GOALS",
                    "GOALASSIST",
                    "YELLOWCARDS",
                    "REDCARDS",
                    "RATING",
                ]
                if c in player_match_list.columns
            ]
            st.dataframe(player_match_list[cols_player_show], use_container_width=True)

        st.subheader("Jugadores transferidos")
        if player_transfer_df.empty:
            st.info("No hay datos suficientes para detectar transferencias.")
            st.stop()

        st.caption("Jugadores con mas de un TEAM_ID en player team")
        if "PLAYER_ID" in player_transfer_df.columns:
            st.write(f"Total: {player_transfer_df['PLAYER_ID'].nunique()}")
        cols_transfer = [
            c
            for c in [
                "PLAYER_ID",
                "TEAM_ID",
                "NAME",
                "POSITION",
                "team_id",
                "short_name",
                "full_name",
            ]
            if c in player_transfer_df.columns
        ]
        st.dataframe(player_transfer_df[cols_transfer], use_container_width=True)

    with tab_partidos:
        equipos = pd.unique(pd.concat([df_master["home"], df_master["away"]], ignore_index=True).dropna()).tolist()
        equipos = sorted(equipos)
        match_ids = df_master["match_id"].astype(str).tolist()
        match_id = st.text_input("match_id", value=match_ids[0] if match_ids else "")
        eq_sel = st.selectbox("Filtrar por equipo (home o away)", options=["(todos)"] + equipos, index=0)

        if eq_sel != "(todos)":
            df_filtrado = df_master[(df_master["home"] == eq_sel) | (df_master["away"] == eq_sel)]
            st.dataframe(df_filtrado, use_container_width=True)

        if match_id and match_id not in match_ids:
            st.warning("El match_id no esta en el maestro. Aun asi, intentare cargar los detalles.")

        if st.button("Cargar detalles"):
            details = load_details(match_id)
            if not details:
                st.stop()
            st.subheader("Resumen maestro")
            row = df_master[df_master["match_id"].astype(str) == str(match_id)]
            if not row.empty:
                st.dataframe(row, use_container_width=True)
            st.subheader("Hojas del archivo Sofascore")
            tabs = st.tabs(list(details.keys()))
            for tab, (sheet, df) in zip(tabs, details.items()):
                with tab:
                    st.write(f"Hoja: {sheet}")
                    st.dataframe(df, use_container_width=True)



if __name__ == "__main__":
    main()
