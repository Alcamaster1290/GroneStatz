from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    FantasyLineup,
    FantasyLineupSlot,
    FantasyTeam,
    FantasyTeamPlayer,
    League,
    LeagueMember,
    PlayerCatalog,
    PointsRound,
    Round,
)
from app.schemas.ranking import PublicLineupOut, PublicMarketOut, RankingOut
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
    round_number: int | None = Query(default=None, ge=1),
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

    rounds = (
        db.execute(
            select(Round).where(Round.season_id == season.id).order_by(Round.round_number)
        )
        .scalars()
        .all()
    )
    if not rounds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    pending_round_number = next((round.round_number for round in rounds if not round.is_closed), None)
    closed_rounds = [round.round_number for round in rounds if round.is_closed]
    allowed_rounds = {
        round.round_number
        for round in rounds
        if round.is_closed or (pending_round_number and round.round_number == pending_round_number)
    }

    if round_number is None:
        round_number = pending_round_number or (max(closed_rounds) if closed_rounds else None)
    if round_number is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")
    if round_number not in allowed_rounds:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="round_not_allowed")

    round_obj = next((round for round in rounds if round.round_number == round_number), None)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    lineup = (
        db.execute(
            select(FantasyLineup)
            .where(
                FantasyLineup.fantasy_team_id == fantasy_team_id,
                FantasyLineup.round_id == round_obj.id,
            )
        )
        .scalars()
        .first()
    )
    if not lineup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lineup_not_found")

    round_number = round_obj.round_number
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


@router.get("/team/{fantasy_team_id}/market", response_model=PublicMarketOut)
def get_team_market(
    fantasy_team_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> PublicMarketOut:
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

    rows = (
        db.execute(
            select(PlayerCatalog, FantasyTeamPlayer)
            .join(FantasyTeamPlayer, FantasyTeamPlayer.player_id == PlayerCatalog.player_id)
            .where(FantasyTeamPlayer.fantasy_team_id == team.id)
        )
        .all()
    )
    if not rows:
        return PublicMarketOut(fantasy_team_id=team.id, team_name=team.name or f"Equipo {team.id}", players=[])

    player_ids = [player.player_id for player, _ in rows]
    points_rows = (
        db.execute(
            select(PointsRound.player_id, func.coalesce(func.sum(PointsRound.points), 0))
            .where(
                PointsRound.season_id == season.id,
                PointsRound.player_id.in_(player_ids),
            )
            .group_by(PointsRound.player_id)
        )
        .all()
    )
    points_map = {player_id: float(points) for player_id, points in points_rows}

    players = [
        {
            "player_id": player.player_id,
            "name": player.name,
            "short_name": player.short_name,
            "position": player.position,
            "team_id": player.team_id,
            "is_injured": bool(player.is_injured),
            "price_current": float(player.price_current),
            "bought_price": float(team_player.bought_price),
            "points_total": points_map.get(player.player_id, 0.0),
        }
        for player, team_player in rows
    ]
    players_sorted = sorted(players, key=lambda item: (item["position"] or "", item["name"] or ""))

    return PublicMarketOut(
        fantasy_team_id=team.id,
        team_name=team.name or f"Equipo {team.id}",
        players=players_sorted,
    )
