from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import FantasyTeam, League, LeagueMember
from app.schemas.ranking import RankingOut
from app.services.fantasy import get_or_create_fantasy_team, get_or_create_season
from app.services.ranking import build_rankings

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get("/general", response_model=RankingOut)
def ranking_general(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> RankingOut:
    season = get_or_create_season(db)
    team_ids = (
        db.execute(select(FantasyTeam.id).where(FantasyTeam.season_id == season.id))
        .scalars()
        .all()
    )
    return build_rankings(db, team_ids)


@router.get("/league", response_model=RankingOut)
def ranking_league(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> RankingOut:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)
    league = (
        db.execute(
            select(League)
            .join(LeagueMember, LeagueMember.league_id == League.id)
            .where(LeagueMember.fantasy_team_id == team.id)
        )
        .scalars()
        .first()
    )
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league_not_found")

    team_ids = (
        db.execute(
            select(LeagueMember.fantasy_team_id).where(LeagueMember.league_id == league.id)
        )
        .scalars()
        .all()
    )
    return build_rankings(db, team_ids)
