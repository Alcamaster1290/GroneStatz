"""Full matchday update: extract → pipeline → sync.

Usage:
    python -m gronestats.scripts.update_matchday --season 2026
    python -m gronestats.scripts.update_matchday --season 2026 --skip-extract
    python -m gronestats.scripts.update_matchday --season 2026 --skip-sync
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_step(description: str, command: list[str], cwd: Path | None = None) -> bool:
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}")
    print(f"  $ {' '.join(command)}\n")

    result = subprocess.run(command, cwd=str(cwd or REPO_ROOT))
    if result.returncode != 0:
        print(f"\n  FAILED (exit code {result.returncode})")
        return False
    print(f"\n  OK")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Full matchday update pipeline.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--match-ids", type=str, default=None, help="Comma-separated match IDs")
    parser.add_argument("--delay", type=float, default=4.0, help="Delay between SofaScore calls")
    parser.add_argument("--skip-extract", action="store_true", help="Skip SofaScore extraction")
    parser.add_argument("--skip-pipeline", action="store_true", help="Skip GroneStats pipeline")
    parser.add_argument("--skip-sync", action="store_true", help="Skip backend sync")
    parser.add_argument("--publish-target", default="fantasy", choices=["dashboard", "fantasy", "all"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    python = sys.executable
    steps_ok = True

    # Step 1: Extract missing matches from SofaScore
    if not args.skip_extract:
        extract_cmd = [
            python, "-m", "gronestats.scripts.extract_matches",
            "--season", str(args.season),
            "--delay", str(args.delay),
        ]
        if args.match_ids:
            extract_cmd += ["--match-ids", args.match_ids]
        if args.dry_run:
            extract_cmd += ["--dry-run"]

        if not run_step("Step 1: Extract matches from SofaScore", extract_cmd):
            steps_ok = False
            if not args.dry_run:
                print("\nExtraction failed. Continuing with pipeline anyway...")

    # Step 2: Run GroneStats pipeline
    if not args.skip_pipeline:
        pipeline_cmd = [
            python, "-m", "gronestats.processing.pipeline", "run",
            "--league", "Liga 1 Peru",
            "--season", str(args.season),
            "--only-missing",
            "--publish-target", args.publish_target,
        ]
        if args.dry_run:
            pipeline_cmd += ["--dry-run"]

        if not run_step("Step 2: Run GroneStats pipeline", pipeline_cmd):
            steps_ok = False
            if not args.dry_run:
                print("\nPipeline failed. Skipping sync.")
                sys.exit(1)

    # Step 3: Sync to backend
    if not args.skip_sync and not args.dry_run:
        fantasy_dir = REPO_ROOT / "FantasyL1-2026"
        sync_cmd = [
            python, str(fantasy_dir / "scripts" / "watch_parquets.py"),
            "--run-on-start",
        ]

        if not run_step("Step 3: Sync parquets to backend", sync_cmd, cwd=fantasy_dir):
            steps_ok = False

    # Summary
    print(f"\n{'='*60}")
    if args.dry_run:
        print("  DRY RUN complete. No changes made.")
    elif steps_ok:
        print("  ALL STEPS COMPLETED SUCCESSFULLY")
    else:
        print("  COMPLETED WITH WARNINGS (check output above)")
    print(f"{'='*60}")

    sys.exit(0 if steps_ok else 1)


if __name__ == "__main__":
    main()
