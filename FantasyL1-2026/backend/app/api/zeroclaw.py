from __future__ import annotations

import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    Fixture,
    PlayerCatalog,
    PointsRound,
    Round,
    Team,
)
from app.services.fantasy import get_or_create_season, get_current_round

router = APIRouter(prefix="/zeroclaw", tags=["zeroclaw"])


def require_zeroclaw(x_zeroclaw_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.ZEROCLAW_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="zeroclaw_not_configured"
        )
    if not x_zeroclaw_token or not secrets.compare_digest(
        x_zeroclaw_token, settings.ZEROCLAW_API_KEY
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_zeroclaw_token"
        )


class ZeroClawStatus(BaseModel):
    season_name: str
    current_round: int
    is_closed: bool
    next_round_starts_at: Optional[str]


class ZeroClawPlayer(BaseModel):
    id: int
    name: str
    team_id: int
    position: str
    price: float
    points_total: float
    is_injured: bool


class ZeroClawTeam(BaseModel):
    id: int
    name: str
    short_name: str


class ZeroClawFixture(BaseModel):
    id: int
    round: int
    home_team_id: int
    away_team_id: int
    kickoff_at: Optional[str]
    status: str
    home_score: Optional[int]
    away_score: Optional[int]


@router.get("/status", response_model=ZeroClawStatus, dependencies=[Depends(require_zeroclaw)])
def get_status(db: Session = Depends(get_db)) -> ZeroClawStatus:
    season = get_or_create_season(db)
    current_round = get_current_round(db, season.id)
    if not current_round:
        return ZeroClawStatus(
            season_name=season.name,
            current_round=0,
            is_closed=True,
            next_round_starts_at=None,
        )
    return ZeroClawStatus(
        season_name=season.name,
        current_round=current_round.round_number,
        is_closed=current_round.is_closed,
        next_round_starts_at=current_round.starts_at.isoformat() if current_round.starts_at else None,
    )


@router.get("/players", response_model=List[ZeroClawPlayer], dependencies=[Depends(require_zeroclaw)])
def list_players(
    limit: int = 100,
    offset: int = 0,
    team_id: Optional[int] = None,
    position: Optional[str] = None,
    db: Session = Depends(get_db)
) -> List[ZeroClawPlayer]:
    season = get_or_create_season(db)

    # Calculate total points
    points_subq = (
        select(
            PointsRound.player_id.label("player_id"),
            func.coalesce(func.sum(PointsRound.points), 0).label("points_total"),
        )
        .where(PointsRound.season_id == season.id)
        .group_by(PointsRound.player_id)
        .subquery()
    )

    query = (
        select(PlayerCatalog, func.coalesce(points_subq.c.points_total, 0))
        .outerjoin(points_subq, PlayerCatalog.player_id == points_subq.c.player_id)
    )

    if team_id:
        query = query.where(PlayerCatalog.team_id == team_id)
    if position:
        query = query.where(PlayerCatalog.position == position)

    query = query.order_by(PlayerCatalog.price_current.desc()).limit(limit).offset(offset)

    rows = db.execute(query).all()
    results = []
    for player, points in rows:
        results.append(
            ZeroClawPlayer(
                id=player.player_id,
                name=player.name,
                team_id=player.team_id,
                position=player.position,
                price=float(player.price_current),
                points_total=float(points),
                is_injured=bool(player.is_injured),
            )
        )
    return results


@router.get("/teams", response_model=List[ZeroClawTeam], dependencies=[Depends(require_zeroclaw)])
def list_teams(db: Session = Depends(get_db)) -> List[ZeroClawTeam]:
    teams = db.execute(select(Team).order_by(Team.name_short)).scalars().all()
    return [
        ZeroClawTeam(id=t.id, name=t.name_full, short_name=t.name_short)
        for t in teams
    ]


@router.get("/fixtures", response_model=List[ZeroClawFixture], dependencies=[Depends(require_zeroclaw)])
def list_fixtures(
    round_number: Optional[int] = None,
    db: Session = Depends(get_db)
) -> List[ZeroClawFixture]:
    season = get_or_create_season(db)
    query = (
        select(Fixture, Round.round_number)
        .join(Round, Fixture.round_id == Round.id)
        .where(Fixture.season_id == season.id)
    )

    if round_number:
        query = query.where(Round.round_number == round_number)
    else:
        # Defaults to current round
        current_round = get_current_round(db, season.id)
        if current_round:
            query = query.where(Round.round_number == current_round.round_number)

    rows = db.execute(query).all()
    results = []
    for fixture, r_num in rows:
        results.append(
            ZeroClawFixture(
                id=fixture.id,
                round=r_num,
                home_team_id=fixture.home_team_id,
                away_team_id=fixture.away_team_id,
                kickoff_at=fixture.kickoff_at.isoformat() if fixture.kickoff_at else None,
                status=fixture.status,
                home_score=fixture.home_score,
                away_score=fixture.away_score,
            )
        )
    return results
