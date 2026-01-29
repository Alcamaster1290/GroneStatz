from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import ActionLog, FantasyTeam, League, LeagueMember
from app.schemas.ranking import LeagueCreateIn, LeagueJoinIn, LeagueOut
from app.services.action_log import log_action
from app.services.fantasy import get_or_create_fantasy_team, get_or_create_season

router = APIRouter(prefix="/leagues", tags=["leagues"])


def _generate_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _get_member_league(db: Session, fantasy_team_id: int) -> League | None:
    return (
        db.execute(
            select(League)
            .join(LeagueMember, LeagueMember.league_id == League.id)
            .where(LeagueMember.fantasy_team_id == fantasy_team_id)
        )
        .scalars()
        .first()
    )


def _get_member_league_row(
    db: Session, fantasy_team_id: int
) -> tuple[League, LeagueMember] | None:
    return (
        db.execute(
            select(League, LeagueMember)
            .join(LeagueMember, LeagueMember.league_id == League.id)
            .where(LeagueMember.fantasy_team_id == fantasy_team_id)
        )
        .first()
    )


def _get_league_members(db: Session, league_id: int) -> list[LeagueMember]:
    return (
        db.execute(
            select(LeagueMember)
            .where(LeagueMember.league_id == league_id)
            .order_by(LeagueMember.joined_at)
        )
        .scalars()
        .all()
    )


def _transfer_owner_or_delete(db: Session, league: League) -> tuple[bool, int | None]:
    members = _get_league_members(db, league.id)
    if not members:
        db.execute(
            update(ActionLog).where(ActionLog.league_id == league.id).values(league_id=None)
        )
        db.execute(delete(League).where(League.id == league.id))
        db.commit()
        return True, None

    new_owner = members[0].fantasy_team_id
    if league.owner_fantasy_team_id != new_owner:
        db.execute(
            update(League)
            .where(League.id == league.id)
            .values(owner_fantasy_team_id=new_owner)
        )
        db.commit()
        db.refresh(league)
    else:
        db.commit()
    return False, new_owner


@router.post("", response_model=LeagueOut)
def create_league(
    payload: LeagueCreateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> LeagueOut:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)

    existing = _get_member_league(db, team.id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_in_league")

    code = _generate_code()
    for _ in range(5):
        exists = db.execute(select(League).where(League.code == code)).scalar_one_or_none()
        if not exists:
            break
        code = _generate_code()
    else:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="code_generation_failed")

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="name_required")

    league = League(
        code=code,
        name=name,
        owner_fantasy_team_id=team.id,
        is_public=False,
    )
    db.add(league)
    db.flush()
    db.add(LeagueMember(league_id=league.id, fantasy_team_id=team.id))
    db.commit()
    db.refresh(league)

    log_action(
        db,
        category="league",
        action="create",
        actor_user_id=user.id,
        league_id=league.id,
        fantasy_team_id=team.id,
        details={"name": league.name, "code": league.code},
    )

    return LeagueOut(
        id=league.id,
        code=league.code,
        name=league.name,
        owner_fantasy_team_id=league.owner_fantasy_team_id,
        is_admin=True,
    )


@router.post("/join", response_model=LeagueOut)
def join_league(
    payload: LeagueJoinIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> LeagueOut:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)

    existing = _get_member_league(db, team.id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_in_league")

    code = payload.code.strip().upper()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="code_required")

    league = db.execute(select(League).where(League.code == code)).scalar_one_or_none()
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league_not_found")

    db.add(LeagueMember(league_id=league.id, fantasy_team_id=team.id))
    db.commit()
    if not league.owner_fantasy_team_id:
        league.owner_fantasy_team_id = team.id
        db.commit()

    log_action(
        db,
        category="league",
        action="join",
        actor_user_id=user.id,
        league_id=league.id,
        fantasy_team_id=team.id,
        details={"code": league.code},
    )
    return LeagueOut(
        id=league.id,
        code=league.code,
        name=league.name,
        owner_fantasy_team_id=league.owner_fantasy_team_id,
        is_admin=league.owner_fantasy_team_id == team.id,
    )


@router.get("/me", response_model=LeagueOut)
def get_my_league(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> LeagueOut:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)
    league = _get_member_league(db, team.id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league_not_found")
    return LeagueOut(
        id=league.id,
        code=league.code,
        name=league.name,
        owner_fantasy_team_id=league.owner_fantasy_team_id,
        is_admin=league.owner_fantasy_team_id == team.id,
    )


@router.post("/leave")
def leave_league(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)

    row = _get_member_league_row(db, team.id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league_not_found")
    league, membership = row

    db.execute(
        delete(LeagueMember).where(
            LeagueMember.league_id == league.id,
            LeagueMember.fantasy_team_id == team.id,
        )
    )

    if league.owner_fantasy_team_id == team.id:
        deleted, new_owner = _transfer_owner_or_delete(db, league)
        log_action(
            db,
            category="league",
            action="leave",
            actor_user_id=user.id,
            league_id=None if deleted else league.id,
            fantasy_team_id=team.id,
            details={"deleted": deleted, "new_owner": new_owner},
        )
        return {"ok": True, "league_deleted": deleted}

    db.commit()
    log_action(
        db,
        category="league",
        action="leave",
        actor_user_id=user.id,
        league_id=league.id,
        fantasy_team_id=team.id,
    )
    return {"ok": True, "league_deleted": False}


@router.delete("/members/{fantasy_team_id}")
def remove_member(
    fantasy_team_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)
    league = _get_member_league(db, team.id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league_not_found")

    if league.owner_fantasy_team_id != team.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_league_admin")

    if fantasy_team_id == team.id:
        return leave_league(db=db, user=user)

    membership = (
        db.execute(
            select(LeagueMember)
            .where(
                LeagueMember.league_id == league.id,
                LeagueMember.fantasy_team_id == fantasy_team_id,
            )
        )
        .scalars()
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member_not_found")

    db.execute(
        delete(LeagueMember).where(
            LeagueMember.league_id == league.id,
            LeagueMember.fantasy_team_id == fantasy_team_id,
        )
    )
    db.commit()
    log_action(
        db,
        category="league",
        action="remove_member",
        actor_user_id=user.id,
        league_id=league.id,
        fantasy_team_id=team.id,
        target_fantasy_team_id=fantasy_team_id,
    )
    return {"ok": True}
