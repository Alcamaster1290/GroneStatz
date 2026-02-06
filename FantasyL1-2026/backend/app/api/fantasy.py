from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    FantasyLineup,
    FantasyLineupSlot,
    FantasyTeam,
    FantasyTeamPlayer,
    FantasyTransfer,
    PlayerCatalog,
    PriceMovement,
    PlayerRoundStat,
    PointsRound,
    Round,
    Team,
)
from app.schemas.fantasy import (
    FantasyTeamCreate,
    FantasyTeamOut,
    FantasyTeamPlayerOut,
    FavoriteTeamUpdateIn,
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
    get_latest_round,
    get_or_create_fantasy_team,
    get_or_create_season,
    get_next_open_round,
    get_round_by_number,
    replace_squad,
    upsert_lineup_slots,
)
from app.services.validation import validate_lineup, validate_squad, validate_transfer

router = APIRouter(prefix="/fantasy", tags=["fantasy"])


def _round_price(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _sort_key_by_bought_round(
    bought_round_id: int | None,
    player_id: int,
) -> tuple[int, int, int]:
    return (
        1 if bought_round_id is None else 0,
        -(bought_round_id or 0),
        player_id,
    )


def _canonicalize_team_rows(
    rows: list[tuple[PlayerCatalog, FantasyTeamPlayer]],
) -> list[tuple[PlayerCatalog, FantasyTeamPlayer]]:
    if len(rows) <= 15:
        return rows
    return sorted(
        rows,
        key=lambda row: _sort_key_by_bought_round(
            row[1].bought_round_id,
            row[1].player_id,
        ),
    )[:15]


def _canonicalize_team_player_ids(
    db: Session,
    fantasy_team_id: int,
) -> list[int]:
    rows = (
        db.execute(
            select(FantasyTeamPlayer.player_id, FantasyTeamPlayer.bought_round_id).where(
                FantasyTeamPlayer.fantasy_team_id == fantasy_team_id
            )
        )
        .all()
    )
    if len(rows) <= 15:
        return [player_id for player_id, _ in rows]
    rows_sorted = sorted(
        rows,
        key=lambda row: _sort_key_by_bought_round(row.bought_round_id, row.player_id),
    )
    return [player_id for player_id, _ in rows_sorted[:15]]


def _resolve_effective_budget_cap(
    base_budget_cap: float,
    market_price_delta: float | None,
) -> float:
    base_cap = _round_price(base_budget_cap)
    if market_price_delta is None or market_price_delta <= 0:
        return float(base_cap)

    boosted_cap = _round_price(Decimal("100.0") + Decimal(str(market_price_delta)))
    return float(boosted_cap if boosted_cap > base_cap else base_cap)


def _get_pending_round_market_delta_total(
    db: Session,
    season_id: int,
    fantasy_team_id: int,
    round_obj: Round | None,
) -> float | None:
    prev_closed_stmt = select(Round).where(
        Round.season_id == season_id,
        Round.is_closed.is_(True),
    )
    if round_obj and not round_obj.is_closed:
        prev_closed_stmt = prev_closed_stmt.where(
            Round.round_number < round_obj.round_number
        )

    prev_closed_round = (
        db.execute(
            prev_closed_stmt
            .order_by(Round.round_number.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if not prev_closed_round:
        return None

    player_ids = _canonicalize_team_player_ids(db, fantasy_team_id)
    if not player_ids:
        return 0.0

    delta_total = (
        db.execute(
            select(func.coalesce(func.sum(PriceMovement.delta), 0)).where(
                PriceMovement.season_id == season_id,
                PriceMovement.round_id == prev_closed_round.id,
                PriceMovement.player_id.in_(player_ids),
            )
        ).scalar()
        or 0
    )
    return float(_round_price(delta_total))


def _get_previous_closed_round(
    db: Session,
    season_id: int,
    pending_round_number: int,
) -> Round | None:
    return (
        db.execute(
            select(Round)
            .where(
                Round.season_id == season_id,
                Round.is_closed.is_(True),
                Round.round_number < pending_round_number,
            )
            .order_by(Round.round_number.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def _get_round_lineup_player_ids(
    db: Session,
    fantasy_team_id: int,
    round_id: int,
) -> set[int]:
    lineup = db.execute(
        select(FantasyLineup.id).where(
            FantasyLineup.fantasy_team_id == fantasy_team_id,
            FantasyLineup.round_id == round_id,
        )
    ).scalar_one_or_none()
    if lineup is None:
        return set()
    player_ids = (
        db.execute(
            select(FantasyLineupSlot.player_id).where(
                FantasyLineupSlot.lineup_id == lineup,
                FantasyLineupSlot.player_id.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    return {int(player_id) for player_id in player_ids if player_id is not None}


def _find_transfer_that_removed_player(
    db: Session,
    fantasy_team_id: int,
    round_id: int,
    player_id: int,
) -> FantasyTransfer | None:
    return (
        db.execute(
            select(FantasyTransfer)
            .where(
                FantasyTransfer.fantasy_team_id == fantasy_team_id,
                FantasyTransfer.round_id == round_id,
                FantasyTransfer.out_player_id == player_id,
            )
            .order_by(FantasyTransfer.created_at, FantasyTransfer.id)
            .limit(1)
        )
        .scalars()
        .first()
    )


def _build_team_response(
    db: Session, fantasy_team_id: int, round_number: Optional[int] = None
) -> FantasyTeamOut:
    team = db.execute(select(FantasyTeam).where(FantasyTeam.id == fantasy_team_id)).scalar_one()
    round_obj = (
        get_round_by_number(db, team.season_id, round_number)
        if round_number
        else get_current_round(db, team.season_id)
    )

    rows = (
        db.execute(
            select(PlayerCatalog, FantasyTeamPlayer)
            .join(FantasyTeamPlayer, FantasyTeamPlayer.player_id == PlayerCatalog.player_id)
            .where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id)
        )
        .all()
    )
    rows = _canonicalize_team_rows(rows)
    points_map = {}
    total_points_map = {}
    totals_stats_map = {}
    round_stats_map = {}
    price_delta_map: dict[int, float] = {}
    market_price_delta_total: float | None = None
    market_price_delta_from_round: int | None = None
    market_price_delta_to_round: int | None = None
    if rows:
        player_ids = [player.player_id for player, _ in rows]
        total_points_rows = db.execute(
            select(PointsRound.player_id, func.coalesce(func.sum(PointsRound.points), 0))
            .where(
                PointsRound.season_id == team.season_id,
                PointsRound.player_id.in_(player_ids),
            )
            .group_by(PointsRound.player_id)
        ).all()
        total_points_map = {player_id: float(points) for player_id, points in total_points_rows}
        totals_stats_rows = db.execute(
            select(
                PlayerRoundStat.player_id,
                func.coalesce(func.sum(PlayerRoundStat.clean_sheets), 0),
                func.coalesce(func.sum(PlayerRoundStat.goals_conceded), 0),
            )
            .where(
                PlayerRoundStat.season_id == team.season_id,
                PlayerRoundStat.player_id.in_(player_ids),
            )
            .group_by(PlayerRoundStat.player_id)
        ).all()
        totals_stats_map = {
            player_id: {
                "clean_sheets": int(clean_sheets or 0),
                "goals_conceded": int(goals_conceded or 0),
            }
            for player_id, clean_sheets, goals_conceded in totals_stats_rows
        }
        if round_obj:
            points_rows = db.execute(
                select(PointsRound.player_id, PointsRound.points).where(
                    PointsRound.season_id == team.season_id,
                    PointsRound.round_id == round_obj.id,
                    PointsRound.player_id.in_(player_ids),
                )
            ).all()
            points_map = {player_id: float(points) for player_id, points in points_rows}
            round_stats_rows = (
                db.execute(
                    select(
                        PlayerRoundStat.player_id,
                        PlayerRoundStat.goals,
                        PlayerRoundStat.assists,
                        PlayerRoundStat.saves,
                    ).where(
                        PlayerRoundStat.season_id == team.season_id,
                        PlayerRoundStat.round_id == round_obj.id,
                        PlayerRoundStat.player_id.in_(player_ids),
                    )
                )
                .all()
            )
            round_stats_map = {
                player_id: {
                    "goals": int(goals or 0),
                    "assists": int(assists or 0),
                    "saves": int(saves or 0),
                }
                for player_id, goals, assists, saves in round_stats_rows
            }

            if not round_obj.is_closed:
                prev_closed_round = (
                    db.execute(
                        select(Round)
                        .where(
                            Round.season_id == team.season_id,
                            Round.is_closed.is_(True),
                            Round.round_number < round_obj.round_number,
                        )
                        .order_by(Round.round_number.desc())
                        .limit(1)
                    )
                    .scalars()
                    .first()
                )
                if prev_closed_round:
                    movement_rows = db.execute(
                        select(PriceMovement.player_id, PriceMovement.delta).where(
                            PriceMovement.season_id == team.season_id,
                            PriceMovement.round_id == prev_closed_round.id,
                            PriceMovement.player_id.in_(player_ids),
                        )
                    ).all()
                    price_delta_map = {
                        player_id: float(delta or 0)
                        for player_id, delta in movement_rows
                    }
                    total_delta = sum(price_delta_map.values())
                    market_price_delta_total = float(
                        Decimal(str(total_delta)).quantize(
                            Decimal("0.1"),
                            rounding=ROUND_HALF_UP,
                        )
                    )
                    market_price_delta_from_round = prev_closed_round.round_number
                    market_price_delta_to_round = round_obj.round_number

    squad = []
    for player, team_player in rows:
        totals = totals_stats_map.get(player.player_id)
        round_stats = round_stats_map.get(player.player_id)
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
                goals_round=round_stats["goals"] if round_stats else None,
                assists_round=round_stats["assists"] if round_stats else None,
                saves_round=round_stats["saves"] if round_stats else None,
                points_round=points_map.get(player.player_id),
                points_total=total_points_map.get(player.player_id, 0.0),
                price_delta=price_delta_map.get(player.player_id)
                if market_price_delta_total is not None
                else None,
                clean_sheets=totals["clean_sheets"] if totals else 0,
                goals_conceded=totals["goals_conceded"] if totals else 0,
            )
        )

    cap_delta_total = _get_pending_round_market_delta_total(
        db,
        team.season_id,
        fantasy_team_id,
        round_obj,
    )
    effective_budget_cap = _resolve_effective_budget_cap(float(team.budget_cap), cap_delta_total)
    budget_used = sum(float(team_player.bought_price) for _, team_player in rows)
    budget_left = effective_budget_cap - budget_used
    club_counts = get_club_counts(db, fantasy_team_id)

    return FantasyTeamOut(
        id=team.id,
        name=team.name,
        favorite_team_id=team.favorite_team_id,
        budget_cap=effective_budget_cap,
        budget_used=budget_used,
        budget_left=budget_left,
        club_counts=club_counts,
        market_price_delta=market_price_delta_total,
        market_price_delta_from_round=market_price_delta_from_round,
        market_price_delta_to_round=market_price_delta_to_round,
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
    current_round = get_current_round(db, season.id)
    market_delta_total = _get_pending_round_market_delta_total(
        db, season.id, team.id, current_round
    )
    effective_budget_cap = _resolve_effective_budget_cap(
        float(team.budget_cap),
        market_delta_total,
    )
    errors = validate_squad(db, payload.player_ids, budget_cap=effective_budget_cap)
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)

    round_id = current_round.id if current_round else None
    replace_squad(db, team.id, payload.player_ids, bought_round_id=round_id)
    return ValidationResult(ok=True, errors=[])


@router.put("/team/favorite", response_model=FantasyTeamOut)
def update_favorite_team(
    payload: FavoriteTeamUpdateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> FantasyTeamOut:
    season = get_or_create_season(db)
    team = get_or_create_fantasy_team(db, user.id, season.id)
    exists = db.execute(select(Team.id).where(Team.id == payload.team_id)).scalar_one_or_none()
    if not exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_not_found")
    team.favorite_team_id = payload.team_id
    db.commit()
    return _build_team_response(db, team.id)


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
        round_obj = get_latest_round(db, season.id)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    lineup = ensure_lineup(db, team.id, round_obj.id)
    slots = (
        db.execute(select(FantasyLineupSlot).where(FantasyLineupSlot.lineup_id == lineup.id))
        .scalars()
        .all()
    )
    slots_sorted = sorted(slots, key=lambda s: s.slot_index)
    player_ids = [slot.player_id for slot in slots_sorted if slot.player_id is not None]
    player_map = {}
    injured_map: dict[int, bool] = {}
    points_map: dict[int, float] = {}
    if player_ids:
        players = (
            db.execute(select(PlayerCatalog).where(PlayerCatalog.player_id.in_(player_ids)))
            .scalars()
            .all()
        )
        player_map = {player.player_id: player for player in players}
        injured_map = {player.player_id: bool(player.is_injured) for player in players}
        points_rows = db.execute(
            select(PointsRound.player_id, PointsRound.points).where(
                PointsRound.season_id == season.id,
                PointsRound.round_id == round_obj.id,
                PointsRound.player_id.in_(player_ids),
            )
        ).all()
        points_map = {player_id: float(points or 0) for player_id, points in points_rows}

    starter_ids = {
        slot.player_id for slot in slots_sorted if slot.player_id is not None and slot.is_starter
    }
    captain_id = lineup.captain_player_id
    vice_captain_id = lineup.vice_captain_player_id
    captain_points = points_map.get(captain_id, 0.0) if captain_id else 0.0
    vice_points = points_map.get(vice_captain_id, 0.0) if vice_captain_id else 0.0
    captain_injured = injured_map.get(captain_id, False) if captain_id else False
    vice_injured = injured_map.get(vice_captain_id, False) if vice_captain_id else False
    bonus_player_id: int | None = None
    if captain_id in starter_ids and not captain_injured and captain_points != 0:
        bonus_player_id = captain_id
    elif vice_captain_id in starter_ids and not vice_injured and vice_points != 0:
        bonus_player_id = vice_captain_id

    def resolve_points(player_id: int | None) -> float | None:
        if player_id is None:
            return None
        if player_id in points_map:
            return points_map[player_id]
        return 0.0 if round_obj.is_closed else None

    return LineupOut(
        lineup_id=lineup.id,
        round_number=round_obj.round_number,
        is_closed=round_obj.is_closed,
        captain_player_id=lineup.captain_player_id,
        vice_captain_player_id=lineup.vice_captain_player_id,
        slots=[
            {
                "slot_index": slot.slot_index,
                "is_starter": slot.is_starter,
                "role": slot.role,
                "player_id": slot.player_id,
                "points_round": resolve_points(slot.player_id),
                "points_with_bonus": (
                    None
                    if (points_round := resolve_points(slot.player_id)) is None
                    else points_round * 3
                    if slot.player_id == bonus_player_id
                    else points_round
                ),
                "player": (
                    {
                        "player_id": player.player_id,
                        "name": player.name,
                        "short_name": player.short_name,
                        "position": player.position,
                        "team_id": player.team_id,
                        "price_current": float(player.price_current),
                        "is_injured": bool(player.is_injured),
                    }
                    if (player := player_map.get(slot.player_id)) is not None
                    else None
                ),
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
    if round_obj.is_closed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="round_closed")

    lineup = ensure_lineup(db, team.id, round_obj.id)
    if payload.reset:
        db.execute(delete(FantasyLineupSlot).where(FantasyLineupSlot.lineup_id == lineup.id))
        lineup.captain_player_id = None
        lineup.vice_captain_player_id = None
        db.commit()
        return ValidationResult(ok=True, errors=[])
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
    return ValidationResult(ok=True, errors=[])


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

    market_delta_total = _get_pending_round_market_delta_total(
        db, season.id, team.id, round_obj
    )
    effective_budget_cap = _resolve_effective_budget_cap(
        float(team.budget_cap),
        market_delta_total,
    )

    restored_transfer: FantasyTransfer | None = None
    if not round_obj.is_closed:
        previous_closed_round = _get_previous_closed_round(
            db,
            season.id,
            round_obj.round_number,
        )
        if previous_closed_round is not None:
            previous_lineup_ids = _get_round_lineup_player_ids(
                db,
                team.id,
                previous_closed_round.id,
            )
            if payload.in_player_id in previous_lineup_ids:
                restored_transfer = _find_transfer_that_removed_player(
                    db,
                    team.id,
                    round_obj.id,
                    payload.in_player_id,
                )

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
    if restored_transfer is not None:
        transfer_fee = 0.0

    errors = validate_transfer(
        db,
        team.id,
        round_obj.id,
        payload.out_player_id,
        payload.in_player_id,
        budget_cap=effective_budget_cap,
        transfer_fee_override=transfer_fee,
    )
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)

    out_team_player = db.execute(
        select(FantasyTeamPlayer).where(
            FantasyTeamPlayer.fantasy_team_id == team.id,
            FantasyTeamPlayer.player_id == payload.out_player_id,
        )
    ).scalar_one_or_none()
    if out_team_player is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="out_player_not_in_squad")

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
    transfer: FantasyTransfer | None = None
    if restored_transfer is None:
        transfer = FantasyTransfer(
            fantasy_team_id=team.id,
            round_id=round_obj.id,
            out_player_id=payload.out_player_id,
            in_player_id=payload.in_player_id,
            out_price=float(out_player.price_current),
            in_price=float(in_player.price_current),
        )
        db.add(transfer)
    else:
        db.delete(restored_transfer)

    realized_gain = Decimal(str(out_player.price_current)) - Decimal(
        str(out_team_player.bought_price)
    )
    cap_delta = realized_gain - Decimal(str(transfer_fee))
    cap_base = _round_price(max(float(team.budget_cap), effective_budget_cap))
    if cap_delta != 0 or cap_base != _round_price(team.budget_cap):
        new_cap = cap_base + cap_delta
        team.budget_cap = new_cap.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    db.commit()

    if transfer is None:
        return TransferOut(
            id=0,
            fantasy_team_id=team.id,
            round_id=round_obj.id,
            out_player_id=payload.out_player_id,
            in_player_id=payload.in_player_id,
            out_price=float(out_player.price_current),
            in_price=float(in_player.price_current),
            created_at=datetime.now(timezone.utc),
        )

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
        round_obj = get_latest_round(db, season.id)
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
