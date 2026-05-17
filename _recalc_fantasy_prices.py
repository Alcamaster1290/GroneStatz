from pathlib import Path
import pandas as pd
import importlib.util
import sys

base = Path.cwd()
parquets_dir = base / "gronestats" / "data" / "Liga 1 Peru" / "2025" / "parquets" / "normalized"
players_path = parquets_dir / "players.parquet"
fantasy_path = parquets_dir / "players_fantasy.parquet"

if not players_path.exists() or not fantasy_path.exists():
    raise SystemExit(f"Missing parquets: {players_path.exists()} {fantasy_path.exists()}")

module_path = base / "gronestats" / "processing" / "st_create_parquets.py"
spec = importlib.util.spec_from_file_location("st_create_parquets", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules["st_create_parquets"] = module
spec.loader.exec_module(module)

calculate_price = module.calculate_price
apply_price_outlier_corrections = module.apply_price_outlier_corrections
_round_float_columns = module._round_float_columns
_stretch_goalkeeper_prices = module._stretch_goalkeeper_prices
_remap_prices_by_position_quantiles = module._remap_prices_by_position_quantiles

players = pd.read_parquet(players_path)
fantasy = pd.read_parquet(fantasy_path)

fantasy = fantasy.copy()
players = players.copy()

for col in ["minutesplayed", "matches_played", "goals", "assists", "saves", "fouls", "penaltywon", "penaltysave", "penaltyconceded", "rating"]:
    if col not in fantasy.columns and col in players.columns:
        fantasy[col] = players.set_index("player_id")[col].reindex(fantasy["player_id"]).values

fantasy["price_raw"] = fantasy.apply(calculate_price, axis=1)

team_id_num = pd.to_numeric(fantasy.get("team_id"), errors="coerce")
favorite_team_ids = {2302, 2305, 2311}
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
fantasy.loc[bonus_mask, "price_raw"] = fantasy.loc[bonus_mask, "price_raw"] + 1.0

min_price_all = 5.0
max_price_all = 9.8
minutes_for_price = pd.to_numeric(fantasy.get("minutesplayed"), errors="coerce")
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

m_mask = fantasy.get("position").eq("M")
d_mask = fantasy.get("position").eq("D")
if "price" in fantasy.columns:
    fantasy.loc[m_mask, "price"] = fantasy.loc[m_mask, "price"].clip(upper=8.9)
    fantasy.loc[d_mask, "price"] = fantasy.loc[d_mask, "price"].clip(upper=7.9)
fantasy["price"] = _stretch_goalkeeper_prices(fantasy["price"], fantasy.get("position"))
fantasy["price"] = fantasy["price"].round(1)
fantasy = fantasy.drop(columns=["price_raw"], errors="ignore")
fantasy = _round_float_columns(fantasy, decimals=2)
fantasy["price"] = fantasy["price"].round(1)
fantasy = apply_price_outlier_corrections(fantasy)
fantasy["price"] = fantasy["price"].round(1)

if "price" not in players.columns:
    players["price"] = pd.NA
price_map = fantasy[["player_id", "price"]].dropna(subset=["player_id"]).drop_duplicates(subset=["player_id"])
players = players.merge(price_map, on="player_id", how="left", suffixes=("", "_fantasy"))
if "price_fantasy" in players.columns:
    players["price"] = players["price_fantasy"].combine_first(players["price"])
    players = players.drop(columns=["price_fantasy"])

fantasy.to_parquet(fantasy_path, index=False)
players.to_parquet(players_path, index=False)

print("recalc_ok", len(fantasy), len(players))
