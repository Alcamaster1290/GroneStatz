from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        db.execute(text("UPDATE fantasy_team_players SET bought_round_id = NULL"))
        db.execute(text("DELETE FROM fantasy_transfers"))
        db.execute(text("DELETE FROM fantasy_lineup_slots"))
        db.execute(text("DELETE FROM fantasy_lineups"))
        db.execute(text("DELETE FROM price_history"))
        db.execute(text("DELETE FROM points_round"))
        db.execute(text("DELETE FROM price_movements"))
        db.execute(text("DELETE FROM player_round_stats"))
        db.execute(text("DELETE FROM player_match_stats"))
        db.execute(text("DELETE FROM fixtures"))
        db.execute(text("DELETE FROM rounds"))
        db.commit()
        print(f"rounds_cleared env={settings.APP_ENV}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
