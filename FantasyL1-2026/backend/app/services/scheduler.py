from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Fixture, Round
from app.services.action_log import log_action
from app.services.fantasy import get_or_create_season
from app.services.push_notifications import run_round_deadline_reminders
from app.services.scoring import recalc_round_points

logger = logging.getLogger(__name__)


async def _scheduler_loop(interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            with SessionLocal() as db:
                run_round_deadline_reminders(db, dry_run=False)
                season = get_or_create_season(db)
                rounds = (
                    db.execute(
                        select(Round)
                        .where(Round.season_id == season.id, Round.is_closed.is_(False))
                        .order_by(Round.round_number)
                    )
                    .scalars()
                    .all()
                )
                if not rounds:
                    continue

                round_ids = [r.id for r in rounds]
                all_fixtures = (
                    db.execute(
                        select(Fixture.round_id, Fixture.status).where(
                            Fixture.season_id == season.id,
                            Fixture.round_id.in_(round_ids),
                        )
                    )
                    .all()
                )
                fixtures_by_round: dict[int, list[str]] = {}
                for r_id, status in all_fixtures:
                    fixtures_by_round.setdefault(r_id, []).append(status)

                for round_obj in rounds:
                    fixtures = fixtures_by_round.get(round_obj.id, [])
                    if not fixtures:
                        continue
                    if any(status != "Finalizado" for status in fixtures):
                        continue

                    recalc_round_points(db, round_number=round_obj.round_number)
                    round_obj.is_closed = True
                    if round_obj.ends_at is None:
                        round_obj.ends_at = datetime.now(timezone.utc)
                    db.commit()
                    log_action(
                        db,
                        category="round",
                        action="auto_close",
                        details={"round_number": round_obj.round_number},
                    )
        except Exception:
            logger.exception("scheduler_loop_error")
            # keep scheduler alive
            continue


def start_scheduler() -> asyncio.Task | None:
    settings = get_settings()
    enabled = str(getattr(settings, "SCHEDULER_ENABLED", "true")).lower() in {"1", "true", "yes"}
    if not enabled:
        return None
    interval = int(getattr(settings, "SCHEDULER_INTERVAL_SECONDS", 300))
    return asyncio.create_task(_scheduler_loop(interval))
