from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Round, Season


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed minimo para entorno test")
    parser.add_argument("--season-year", type=int, default=2026)
    parser.add_argument("--season-name", type=str, default="2026 Apertura")
    parser.add_argument("--total-rounds", type=int, default=18)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    with SessionLocal() as db:
        season = db.query(Season).filter(Season.year == args.season_year).first()
        if not season:
            season = Season(year=args.season_year, name=args.season_name)
            db.add(season)
            db.flush()

        created_rounds = 0
        for round_number in range(1, args.total_rounds + 1):
            round_row = (
                db.query(Round)
                .filter(Round.season_id == season.id, Round.round_number == round_number)
                .first()
            )
            if round_row:
                continue
            db.add(Round(season_id=season.id, round_number=round_number, is_closed=False))
            created_rounds += 1

        db.commit()
        print(
            f"[seed_test_minimum] env={settings.APP_ENV} season={season.year} "
            f"created_rounds={created_rounds} total_target={args.total_rounds}"
        )


if __name__ == "__main__":
    main()
