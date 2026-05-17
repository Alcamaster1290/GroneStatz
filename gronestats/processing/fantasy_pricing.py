from __future__ import annotations

import pandas as pd


def _round_float_columns(df: pd.DataFrame, decimals: int = 2) -> pd.DataFrame:
    if df.empty:
        return df
    float_cols = [column for column in df.columns if pd.api.types.is_float_dtype(df[column])]
    if not float_cols:
        return df
    work = df.copy()
    work[float_cols] = work[float_cols].round(decimals)
    return work


def _safe_per_match(series: pd.Series, matches: pd.Series) -> pd.Series:
    safe_matches = matches.where(matches > 0)
    return series.div(safe_matches).fillna(0)


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
        quantiles = prices_num[pos_mask].rank(pct=True, method="average")
        mapped = pd.Series(index=quantiles.index, dtype="float64")
        for q0, q1, low, high in segments:
            if q1 <= q0:
                continue
            segment_mask = (quantiles > q0) & (quantiles <= q1) if q0 > 0 else (quantiles <= q1)
            if not segment_mask.any():
                continue
            mapped.loc[segment_mask] = low + (quantiles[segment_mask] - q0) / (q1 - q0) * (high - low)
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
    if required_cols.difference(df.columns):
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
        4.0 * goals + 3.0 * assists + 1.0 * penalty_won - 1.2 * penalty_conceded - 0.3 * fouls
    ).loc[mask_f] * avail.loc[mask_f]
    performance_score.loc[mask_m] = (
        3.2 * goals + 3.2 * assists + 0.8 * penalty_won - 1.2 * penalty_conceded - 0.25 * fouls
    ).loc[mask_m] * avail.loc[mask_m]
    performance_score.loc[mask_d] = (
        4.0 * goals + 2.5 * assists + 0.6 * penalty_won - 1.2 * penalty_conceded - 0.25 * fouls
    ).loc[mask_d] * avail.loc[mask_d]
    performance_score.loc[mask_g] = (
        0.35 * saves + 1.5 * penalty_save - 1.0 * penalty_conceded - 0.1 * fouls
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
            lambda quantile: group_prices.quantile(quantile, interpolation="linear")
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
        return max(3.5, round(base + keeper, 2))

    foul_penalty = 0.12 if position == "D" else 0.08
    other = 0.4 * penalty_save + 0.3 * penalty_won - foul_penalty * fouls - 0.4 * penalty_conceded
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
