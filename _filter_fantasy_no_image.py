from pathlib import Path
import pandas as pd

base = Path.cwd()
parquets_dir = base / "gronestats" / "data" / "Liga 1 Peru" / "2025" / "parquets" / "normalized"
fantasy_path = parquets_dir / "players_fantasy.parquet"
img_dir = base / "FantasyL1-2026" / "frontend" / "public" / "images" / "players"

if not fantasy_path.exists():
    raise SystemExit(f"Missing {fantasy_path}")
if not img_dir.exists():
    raise SystemExit(f"Missing {img_dir}")

fantasy = pd.read_parquet(fantasy_path)
if "player_id" not in fantasy.columns:
    raise SystemExit("players_fantasy.parquet missing player_id")

png_ids = set()
for p in img_dir.glob("*.png"):
    try:
        png_ids.add(int(p.stem))
    except ValueError:
        continue

before = len(fantasy)
kept = fantasy[fantasy["player_id"].astype("Int64").isin(png_ids)].copy()
after = len(kept)

backup_path = fantasy_path.with_suffix(".parquet.bak")
fantasy.to_parquet(backup_path, index=False)
kept.to_parquet(fantasy_path, index=False)

print(f"removed_no_image={before - after} kept={after} backup={backup_path}")
