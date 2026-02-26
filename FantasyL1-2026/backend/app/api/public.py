from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import FantasyTeam
from app.schemas.public import (
    PublicAppConfigOut,
    PublicLeaderboardEntryOut,
    PublicLeaderboardOut,
    PublicPremiumConfigOut,
)
from app.services.app_config import get_public_app_config
from app.services.premium import get_or_create_season_by_year, get_public_premium_config
from app.services.ranking import build_rankings

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/leaderboard", response_model=PublicLeaderboardOut)
def public_leaderboard(
    limit: int = Query(default=25, ge=1, le=100),
    season_year: int = Query(default=2026, ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> PublicLeaderboardOut:
    season = get_or_create_season_by_year(db, season_year)
    team_ids = (
        db.execute(select(FantasyTeam.id).where(FantasyTeam.season_id == season.id))
        .scalars()
        .all()
    )
    ranking = build_rankings(db, team_ids)
    entries = [
        PublicLeaderboardEntryOut(
            rank=index + 1,
            fantasy_team_id=entry.fantasy_team_id,
            team_name=entry.team_name,
            points_total=entry.total_points,
        )
        for index, entry in enumerate(ranking.entries[:limit])
    ]
    return PublicLeaderboardOut(season_year=season.year, limit=limit, entries=entries)


@router.get("/premium/config", response_model=PublicPremiumConfigOut)
def public_premium_config(
    season_year: int = Query(default=2026, ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> PublicPremiumConfigOut:
    return PublicPremiumConfigOut(**get_public_premium_config(db, season_year))


@router.get("/app-config", response_model=PublicAppConfigOut)
def public_app_config(db: Session = Depends(get_db)) -> PublicAppConfigOut:
    return PublicAppConfigOut(**get_public_app_config(db))
