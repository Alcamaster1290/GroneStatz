from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import FantasyLineup, FantasyLineupSlot, FantasyTeam, League, LeagueMember, PlayerCatalog, Round
from app.schemas.ranking import PublicLineupOut, RankingOut
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


@router.get("/team/{fantasy_team_id}/lineup", response_model=PublicLineupOut)
def get_team_lineup(
    fantasy_team_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> PublicLineupOut:
    season = get_or_create_season(db)
    team = (
        db.execute(
            select(FantasyTeam).where(
                FantasyTeam.id == fantasy_team_id,
                FantasyTeam.season_id == season.id,
            )
        )
        .scalars()
        .first()
    )
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team_not_found")

    lineup = (
        db.execute(
            select(FantasyLineup)
            .where(FantasyLineup.fantasy_team_id == fantasy_team_id)
            .order_by(FantasyLineup.round_id.desc())
        )
        .scalars()
        .first()
    )
    if not lineup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lineup_not_found")

    round_number = (
        db.execute(select(Round.round_number).where(Round.id == lineup.round_id))
        .scalars()
        .first()
    )
    slots_rows = (
        db.execute(
            select(FantasyLineupSlot, PlayerCatalog)
            .outerjoin(PlayerCatalog, FantasyLineupSlot.player_id == PlayerCatalog.player_id)
            .where(FantasyLineupSlot.lineup_id == lineup.id)
        )
        .all()
    )
    slots: list[dict] = []
    for slot, player in slots_rows:
        slots.append(
            {
                "slot_index": slot.slot_index,
                "is_starter": slot.is_starter,
                "role": slot.role,
                "player_id": slot.player_id,
                "player": (
                    {
                        "player_id": player.player_id,
                        "name": player.name,
                        "short_name": player.short_name,
                        "position": player.position,
                        "team_id": player.team_id,
                        "is_injured": bool(player.is_injured),
                    }
                    if player is not None
                    else None
                ),
            }
        )

    slots_sorted = sorted(slots, key=lambda item: item["slot_index"])
    return PublicLineupOut(
        fantasy_team_id=team.id,
        team_name=team.name or f"Equipo {team.id}",
        round_number=round_number or 0,
        captain_player_id=lineup.captain_player_id,
        vice_captain_player_id=lineup.vice_captain_player_id,
        slots=slots_sorted,
    )
