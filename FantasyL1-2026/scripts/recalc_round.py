from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.append(str(BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.services.scoring import recalc_round_points  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Recalculate points and prices for a round.")
    parser.add_argument("round_number", type=int, help="Round number to recalc")
    parser.add_argument("--no-prices", action="store_true", help="Skip price updates")
    parser.add_argument(
        "--no-history", action="store_true", help="Skip price_history upsert"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = recalc_round_points(
            db,
            round_number=args.round_number,
            apply_prices=not args.no_prices,
            write_price_history=not args.no_history,
        )
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
