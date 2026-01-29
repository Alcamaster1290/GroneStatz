from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import ActionLog


def log_action(
    db: Session,
    *,
    category: str,
    action: str,
    actor_user_id: Optional[int] = None,
    league_id: Optional[int] = None,
    fantasy_team_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
    target_fantasy_team_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    payload = json.dumps(details, ensure_ascii=False) if details else None
    db.add(
        ActionLog(
            category=category,
            action=action,
            actor_user_id=actor_user_id,
            league_id=league_id,
            fantasy_team_id=fantasy_team_id,
            target_user_id=target_user_id,
            target_fantasy_team_id=target_fantasy_team_id,
            details=payload,
        )
    )
    db.commit()
