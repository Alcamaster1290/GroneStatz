from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    FantasyLineupSlot,
    FantasyTeam,
    FantasyTeamPlayer,
    FantasyTransfer,
    PlayerCatalog,
    PlayerRoundStat,
    PointsRound,
    Round,
)
from app.schemas.fantasy import (
    FantasyTeamCreate,
    FantasyTeamOut,
    FantasyTeamPlayerOut,
    LineupOut,
    LineupUpdateIn,
    SquadUpdateIn,
    TransferIn,
    TransferOut,
    TransferCountOut,
    ValidationResult,
)
from app.services.fantasy import (
    ensure_lineup,
    get_club_counts,
    get_current_round,
    get_or_create_fantasy_team,
    get_or_create_season,
    get_next_open_round,
    get_round_by_number,
    replace_squad,
    upsert_lineup_slots,
)
from app.services.validation import validate_lineup, validate_squad, validate_transfer

router = APIRouter(prefix="/fantasy", tags=["fantasy"])


def _build_team_response(
    db: Session, fantasy_team_id: int, round_number: Optional[int] = None
) -> FantasyTeamOut:
    team = db.execute(select(FantasyTeam).where(FantasyTeam.id == fantasy_team_id)).scalar_one()

    rows = (
        db.execute(
            select(PlayerCatalog, FantasyTeamPlayer)
            .join(FantasyTeamPlayer, FantasyTeamPlayer.player_id == PlayerCatalog.player_id)
            .where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id)
        )
        .all()
    )
    points_map = {}
    round_stats_map = {}
    if rows:
        player_ids = [player.player_id for player, _ in rows]
        round_obj = (
            get_round_by_number(db, team.season_id, round_number)
            if round_number
            else get_current_round(db, team.season_id)
        )
        if round_obj:
            points_rows = db.execute(
                select(PointsRound.player_id, PointsRound.points).where(
                    PointsRound.season_id == team.season_id,
                    PointsRound.round_id == round_obj.id,
                    PointsRound.player_id.in_(player_ids),
                )
            ).all()
            points_map = {player_id: float(points) for player_id, points in points_rows}

            stats_rows = db.execute(
                select(
                    PlayerRoundStat.player_id,
                    PlayerRoundStat.clean_sheets,
                    PlayerRoundStat.goals_conceded,
                ).where(
                    PlayerRoundStat.season_id == team.season_id,
                    PlayerRoundStat.round_id == round_obj.id,
                    PlayerRoundStat.player_id.in_(player_ids),
                )
            ).all()
            round_stats_map = {
                player_id: {
                    "clean_sheets": int(clean_sheets or 0),
                    "goals_conceded": int(goals_conceded or 0),
                }
                for player_id, clean_sheets, goals_conceded in stats_rows
            }

    squad = []
    for player, team_player in rows:
        stats = round_stats_map.get(player.player_id)
        squad.append(
            FantasyTeamPlayerOut(
                player_id=player.player_id,
                name=player.name,
                short_name=player.short_name,
                position=player.position,
                team_id=player.team_id,
                price_current=float(player.price_current),
                bought_price=float(team_player.bought_price),
                is_injured=bool(player.is_injured),
                goals=int(player.goals or 0),
                assists=int(player.assists or 0),
                saves=int(player.saves or 0),
                points_round=points_map.get(player.player_id),
                clean_sheets=stats["clean_sheets"] if stats else (0 if round_stats_map else None),
                goals_conceded=stats["goals_conceded"] if stats else (0 if round_stats_map else None),
            )
        )

    budget_used = sum(float(team_player.bought_price) for _, team_player in rows)
    budget_left = float(team.budget_cap) - budget_used
    club_counts = get_club_counts(db, fantasy_team_id)

    return FantasyTeamOut(
        id=team.id,
        name=team.name,
        budget_cap=float(team.budget_cap),
        budget_used=budget_used,
        budget_left=budget_left,
        club_counts=club_counts,
        squad=squad,
    )


@router.post("/team", response_model=FantasyTeamOut)
def create_team(
    payload: FantasyTeamCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> FantasyTeamOut:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id, name=payload.name)
    return _build_team_response(db, team.id)


@router.get("/team", response_model=FantasyTeamOut)
def get_team(
    round_number: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> FantasyTeamOut:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)
    return _build_team_response(db, team.id, round_number=round_number)


@router.put("/team/squad", response_model=ValidationResult)
def update_squad(
    payload: SquadUpdateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ValidationResult:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)
    errors = validate_squad(db, payload.player_ids, budget_cap=float(team.budget_cap))
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)

    current_round = get_current_round(db, season.id)
    round_id = current_round.id if current_round else None
    replace_squad(db, team.id, payload.player_ids, bought_round_id=round_id)
    return ValidationResult(ok=True, errors=[])


@router.get("/lineup", response_model=LineupOut)
def get_lineup(
    round_number: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> LineupOut:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)

    round_obj = get_round_by_number(db, season.id, round_number) if round_number else get_current_round(db, season.id)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    lineup = ensure_lineup(db, team.id, round_obj.id)
    slots = (
        db.execute(select(FantasyLineupSlot).where(FantasyLineupSlot.lineup_id == lineup.id))
        .scalars()
        .all()
    )
    slots_sorted = sorted(slots, key=lambda s: s.slot_index)

    return LineupOut(
        lineup_id=lineup.id,
        round_number=round_obj.round_number,
        captain_player_id=lineup.captain_player_id,
        vice_captain_player_id=lineup.vice_captain_player_id,
        slots=[
            {
                "slot_index": slot.slot_index,
                "is_starter": slot.is_starter,
                "role": slot.role,
                "player_id": slot.player_id,
            }
            for slot in slots_sorted
        ],
    )


@router.put("/lineup", response_model=ValidationResult)
def update_lineup(
    payload: LineupUpdateIn,
    round_number: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ValidationResult:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)
    round_obj = get_round_by_number(db, season.id, round_number) if round_number else get_current_round(db, season.id)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")
    notice_message = None
    if round_obj.is_closed:
        next_round = get_next_open_round(db, season.id, round_obj.round_number)
        if not next_round:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="round_closed")
        round_obj = next_round
        notice_message = (
            f"Ronda cerrada. Tu XI se guardó para la ronda {round_obj.round_number}."
        )

    lineup = ensure_lineup(db, team.id, round_obj.id)
    errors = validate_lineup(db, team.id, payload.slots)
    if not errors:
        player_ids = {slot.player_id for slot in payload.slots if slot.player_id is not None}
        starter_ids = {
            slot.player_id
            for slot in payload.slots
            if slot.player_id is not None and slot.is_starter
        }
        if payload.captain_player_id and payload.captain_player_id not in player_ids:
            errors.append("captain_not_in_lineup")
        if payload.captain_player_id and payload.captain_player_id not in starter_ids:
            errors.append("captain_not_in_starting_xi")
        if payload.vice_captain_player_id and payload.vice_captain_player_id not in player_ids:
            errors.append("vice_captain_not_in_lineup")
        if payload.vice_captain_player_id and payload.vice_captain_player_id not in starter_ids:
            errors.append("vice_captain_not_in_starting_xi")
        if (
            payload.captain_player_id
            and payload.vice_captain_player_id
            and payload.captain_player_id == payload.vice_captain_player_id
        ):
            errors.append("captain_and_vice_same_player")
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)

    upsert_lineup_slots(db, lineup.id, payload.slots)
    lineup.captain_player_id = payload.captain_player_id
    lineup.vice_captain_player_id = payload.vice_captain_player_id
    db.commit()
    return ValidationResult(ok=True, errors=[], message=notice_message)


@router.post("/transfer", response_model=TransferOut)
def transfer_player(
    payload: TransferIn,
    round_number: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> TransferOut:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)
    round_obj = get_round_by_number(db, season.id, round_number) if round_number else get_current_round(db, season.id)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    errors = validate_transfer(
        db,
        team.id,
        round_obj.id,
        payload.out_player_id,
        payload.in_player_id,
        budget_cap=float(team.budget_cap),
    )
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)

    existing_count = (
        db.execute(
            select(func.count())
            .select_from(FantasyTransfer)
            .where(
                FantasyTransfer.fantasy_team_id == team.id,
                FantasyTransfer.round_id == round_obj.id,
            )
        ).scalar()
        or 0
    )
    transfer_fee = 0.0 if existing_count == 0 else 0.5

    out_player = db.get(PlayerCatalog, payload.out_player_id)
    in_player = db.get(PlayerCatalog, payload.in_player_id)
    if not out_player or not in_player:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="player_not_found")

    db.execute(
        delete(FantasyTeamPlayer).where(
            FantasyTeamPlayer.fantasy_team_id == team.id,
            FantasyTeamPlayer.player_id == payload.out_player_id,
        )
    )
    db.add(
        FantasyTeamPlayer(
            fantasy_team_id=team.id,
            player_id=payload.in_player_id,
            bought_price=float(in_player.price_current),
            bought_round_id=round_obj.id,
            is_active=True,
        )
    )
    transfer = FantasyTransfer(
        fantasy_team_id=team.id,
        round_id=round_obj.id,
        out_player_id=payload.out_player_id,
        in_player_id=payload.in_player_id,
        out_price=float(out_player.price_current),
        in_price=float(in_player.price_current),
    )
    db.add(transfer)
    if transfer_fee > 0:
        new_cap = Decimal(str(team.budget_cap)) - Decimal(str(transfer_fee))
        team.budget_cap = new_cap.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    db.commit()
    db.refresh(transfer)

    return TransferOut(
        id=transfer.id,
        fantasy_team_id=transfer.fantasy_team_id,
        round_id=transfer.round_id,
        out_player_id=transfer.out_player_id,
        in_player_id=transfer.in_player_id,
        out_price=float(transfer.out_price),
        in_price=float(transfer.in_price),
        created_at=transfer.created_at,
    )


@router.get("/transfers/count", response_model=TransferCountOut)
def get_transfer_count(
    round_number: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> TransferCountOut:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)
    round_obj = (
        get_round_by_number(db, season.id, round_number)
        if round_number
        else get_current_round(db, season.id)
    )
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    transfers_used = (
        db.execute(
            select(func.count())
            .select_from(FantasyTransfer)
            .where(
                FantasyTransfer.fantasy_team_id == team.id,
                FantasyTransfer.round_id == round_obj.id,
            )
        ).scalar()
        or 0
    )
    next_fee = 0.0 if transfers_used == 0 else 0.5
    return TransferCountOut(
        round_number=round_obj.round_number,
        transfers_used=int(transfers_used),
        next_fee=float(next_fee),
    )
