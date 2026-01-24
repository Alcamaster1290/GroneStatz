from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Fixture, PlayerCatalog, Round, Team
from app.schemas.catalog import FixtureOut, PlayerCatalogOut, TeamOut

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/players", response_model=List[PlayerCatalogOut])
def list_players(
    position: Optional[str] = None,
    team_id: Optional[int] = None,
    q: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[PlayerCatalogOut]:
    query = select(PlayerCatalog)
    if position:
        query = query.where(PlayerCatalog.position == position)
    if team_id:
        query = query.where(PlayerCatalog.team_id == team_id)
    if q:
        query = query.where(PlayerCatalog.name.ilike(f"%{q}%"))
    if max_price is not None:
        query = query.where(PlayerCatalog.price_current <= max_price)
    if min_price is not None:
        query = query.where(PlayerCatalog.price_current >= min_price)

    query = query.order_by(PlayerCatalog.name).limit(limit).offset(offset)
    players = db.execute(query).scalars().all()
    return [
        PlayerCatalogOut(
            player_id=p.player_id,
            name=p.name,
            short_name=p.short_name,
            position=p.position,
            team_id=p.team_id,
            price_current=float(p.price_current),
            minutesplayed=p.minutesplayed,
            matches_played=p.matches_played,
            goals=p.goals,
            assists=p.assists,
            saves=p.saves,
            fouls=p.fouls,
            updated_at=p.updated_at,
        )
        for p in players
    ]


@router.get("/teams", response_model=List[TeamOut])
def list_teams(db: Session = Depends(get_db)) -> List[TeamOut]:
    teams = db.execute(select(Team).order_by(Team.name_short)).scalars().all()
    return [TeamOut(id=t.id, name_short=t.name_short, name_full=t.name_full) for t in teams]


@router.get("/fixtures", response_model=List[FixtureOut])
def list_fixtures(
    round_number: Optional[int] = None, db: Session = Depends(get_db)
) -> List[FixtureOut]:
    query = select(Fixture, Round.round_number).join(Round, Fixture.round_id == Round.id)
    if round_number is not None:
        query = query.where(Round.round_number == round_number)
    rows = db.execute(query).all()
    return [
        FixtureOut(
            id=fixture.id,
            round_number=round_no,
            match_id=fixture.match_id,
            home_team_id=fixture.home_team_id,
            away_team_id=fixture.away_team_id,
            kickoff_at=fixture.kickoff_at,
            stadium=fixture.stadium,
            city=fixture.city,
        )
        for fixture, round_no in rows
    ]
