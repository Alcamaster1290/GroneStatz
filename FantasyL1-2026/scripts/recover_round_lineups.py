from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.append(str(BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.services.round_recovery import recover_round_lineups_from_market  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit/recover lineups from market snapshot for a round."
    )
    parser.add_argument(
        "--round",
        dest="round_number",
        type=int,
        default=1,
        help="Target round number (default: 1)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to DB. Without this flag it runs as dry-run.",
    )
    parser.add_argument(
        "--skip-recalc",
        action="store_true",
        help="Skip player points recalc after recovery.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = recover_round_lineups_from_market(
            db,
            round_number=args.round_number,
            apply=bool(args.apply),
            recalc_player_points=not args.skip_recalc,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
