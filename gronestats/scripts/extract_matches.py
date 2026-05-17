"""Extract match data from SofaScore for missing matches.

Usage:
    python -m gronestats.scripts.extract_matches --season 2026
    python -m gronestats.scripts.extract_matches --season 2026 --match-ids 15714336,15714347
    python -m gronestats.scripts.extract_matches --season 2026 --dry-run
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]


def get_existing_match_ids(season: int) -> set[int]:
    raw_dir = REPO_ROOT / "gronestats" / "data" / "Liga 1 Peru" / str(season) / "raw" / "details" / "xlsx"
    if not raw_dir.exists():
        return set()
    return {
        int(p.stem.replace("Sofascore_", ""))
        for p in raw_dir.glob("Sofascore_*.xlsx")
        if p.stem.replace("Sofascore_", "").isdigit()
    }


def get_finished_match_ids(season: int) -> tuple[set[int], pd.DataFrame]:
    master_path = (
        REPO_ROOT / "gronestats" / "data" / "Liga 1 Peru" / str(season)
        / "raw" / "master" / "clean" / f"Partidos_Liga 1 Peru_{season}_limpio.xlsx"
    )
    if not master_path.exists():
        return set(), pd.DataFrame()
    master = pd.read_excel(master_path)
    finished = master.loc[master["home_score"].notna() & master["away_score"].notna()]
    ids = set(finished["match_id"].dropna().astype(int))
    return ids, master


def extract_match(match_id: int, output_dir: Path, sofascore) -> Path:
    output_path = output_dir / f"Sofascore_{match_id}.xlsx"
    mid = str(match_id)

    player_stats = pd.DataFrame()
    team_stats = pd.DataFrame()
    avg_positions = pd.DataFrame()
    shotmap = pd.DataFrame()
    momentum = pd.DataFrame()
    heatmaps = pd.DataFrame()

    try:
        player_stats = sofascore.scrape_player_match_stats(mid)
    except Exception as exc:
        print(f"  [WARN] player_stats failed for {match_id}: {exc}")

    try:
        team_stats = sofascore.scrape_team_match_stats(mid)
    except Exception as exc:
        print(f"  [WARN] team_stats failed for {match_id}: {exc}")

    try:
        avg_positions = sofascore.scrape_player_average_positions(mid)
    except Exception as exc:
        print(f"  [WARN] avg_positions failed for {match_id}: {exc}")

    try:
        shotmap = sofascore.scrape_match_shots(mid)
    except Exception as exc:
        print(f"  [WARN] shotmap failed for {match_id}: {exc}")

    try:
        momentum = sofascore.scrape_match_momentum(mid)
    except Exception as exc:
        print(f"  [WARN] momentum failed for {match_id}: {exc}")

    try:
        heatmaps_raw = sofascore.scrape_heatmaps(mid)
        if isinstance(heatmaps_raw, dict):
            rows = []
            for pid, points in heatmaps_raw.items():
                for pt in (points or []):
                    rows.append({"player_id": pid, "x": pt.get("x"), "y": pt.get("y")})
            heatmaps = pd.DataFrame(rows)
        elif isinstance(heatmaps_raw, pd.DataFrame):
            heatmaps = heatmaps_raw
    except Exception as exc:
        print(f"  [WARN] heatmaps failed for {match_id}: {exc}")

    if not isinstance(player_stats, pd.DataFrame):
        player_stats = pd.DataFrame(player_stats or [])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        if not player_stats.empty:
            player_stats.to_excel(writer, sheet_name="Player Stats", index=False)
        if not team_stats.empty:
            team_stats.to_excel(writer, sheet_name="Team Stats", index=False)
        if not avg_positions.empty:
            avg_positions.to_excel(writer, sheet_name="Average Positions", index=False)
        if not heatmaps.empty:
            heatmaps.to_excel(writer, sheet_name="Heatmaps", index=False)
        if not shotmap.empty:
            shotmap.to_excel(writer, sheet_name="Shotmap", index=False)
        if not momentum.empty:
            momentum.to_excel(writer, sheet_name="Match Momentum", index=False)

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract missing match data from SofaScore.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--match-ids", type=str, default=None, help="Comma-separated match IDs to extract")
    parser.add_argument("--delay", type=float, default=4.0, help="Seconds between API calls")
    parser.add_argument("--dry-run", action="store_true", help="Only show missing matches")
    args = parser.parse_args()

    existing = get_existing_match_ids(args.season)
    print(f"Existing XLSX files: {len(existing)}")

    if args.match_ids:
        target_ids = sorted(int(x.strip()) for x in args.match_ids.split(","))
    else:
        finished_ids, master = get_finished_match_ids(args.season)
        target_ids = sorted(finished_ids - existing)
        print(f"Finished matches in master: {len(finished_ids)}")

    print(f"Matches to extract: {len(target_ids)}")

    if not target_ids:
        print("Nothing to extract.")
        return

    if args.dry_run:
        for mid in target_ids:
            print(f"  Would extract: {mid}")
        return

    import ScraperFC as sfc
    sofascore = sfc.Sofascore()

    output_dir = REPO_ROOT / "gronestats" / "data" / "Liga 1 Peru" / str(args.season) / "raw" / "details" / "xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted = 0
    failed = []
    for i, match_id in enumerate(target_ids):
        print(f"[{i+1}/{len(target_ids)}] Extracting match {match_id}...")
        try:
            path = extract_match(match_id, output_dir, sofascore)
            print(f"  OK → {path.name}")
            extracted += 1
        except Exception as exc:
            print(f"  FAILED: {exc}")
            failed.append(match_id)

        if i < len(target_ids) - 1:
            time.sleep(args.delay)

    print(f"\nDone. Extracted: {extracted}, Failed: {len(failed)}")
    if failed:
        print(f"Failed IDs: {failed}")


if __name__ == "__main__":
    main()
