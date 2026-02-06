from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from app.api.deps import require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    ActionLog,
    FantasyLineup,
    FantasyLineupSlot,
    FantasyTeam,
    FantasyTeamPlayer,
    FantasyTransfer,
    Fixture,
    League,
    LeagueMember,
    PlayerCatalog,
    PlayerMatchStat,
    PasswordResetToken,
    PriceMovement,
    PointsRound,
    Round,
    Season,
    Team,
    User,
)
from app.schemas.admin import (
    AdminFixtureCreate,
    AdminFixtureOut,
    AdminFixtureUpdate,
    AdminLeagueOut,
    AdminLeagueMemberOut,
    AdminActionLogOut,
    AdminPlayerListItem,
    AdminPlayerListOut,
    AdminRoundOut,
    AdminRoundWindowUpdateIn,
    AdminPlayerRoundStatsIn,
    AdminPlayerStatOut,
    AdminPlayerInjuryIn,
    AdminPlayerInjuryOut,
    AdminMatchPlayerOut,
    AdminRoundTopPlayerOut,
    AdminPriceMovementOut,
    AdminTeamOut,
    AdminTeamPlayerOut,
    AdminTeamLineupOut,
    AdminLineupSlotOut,
    AdminLineupPlayerOut,
    AdminTransferOut,
    AdminTransferPlayerOut,
)
from app.services.data_pipeline import ingest_parquets_to_duckdb, sync_duckdb_to_postgres
from app.services.fantasy import ensure_round, get_or_create_season, get_round_by_number
from app.services.action_log import log_action
from app.services.push_notifications import run_round_deadline_reminders
from app.services.round_recovery import recover_round_lineups_from_market
from app.services.scoring import calc_match_points, recalc_round_points

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


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


def _resolve_round_for_transfer_admin(
    db: Session,
    season_id: int,
    round_number: int | None,
) -> Round | None:
    round_obj = (
        get_round_by_number(db, season_id, round_number)
        if round_number is not None
        else (
            db.execute(
                select(Round)
                .where(Round.season_id == season_id, Round.is_closed.is_(False))
                .order_by(Round.round_number)
                .limit(1)
            )
            .scalars()
            .first()
        )
    )
    if round_obj is None and round_number is None:
        round_obj = (
            db.execute(
                select(Round)
                .where(Round.season_id == season_id)
                .order_by(Round.round_number.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
    return round_obj


def _get_team_player_ids(db: Session, fantasy_team_id: int) -> set[int]:
    return set(
        db.execute(
            select(FantasyTeamPlayer.player_id).where(
                FantasyTeamPlayer.fantasy_team_id == fantasy_team_id
            )
        )
        .scalars()
        .all()
    )


def _get_team_player_ids_for_delta(db: Session, fantasy_team_id: int) -> list[int]:
    rows = (
        db.execute(
            select(FantasyTeamPlayer.player_id, FantasyTeamPlayer.bought_round_id)
            .join(
                PlayerCatalog,
                PlayerCatalog.player_id == FantasyTeamPlayer.player_id,
            )
            .where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id)
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


def _get_transfer_count_for_round(db: Session, fantasy_team_id: int, round_id: int) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(FantasyTransfer)
            .where(
                FantasyTransfer.fantasy_team_id == fantasy_team_id,
                FantasyTransfer.round_id == round_id,
            )
        ).scalar()
        or 0
    )


def _get_transfer_fee_total_for_count(transfer_count: int) -> Decimal:
    _ = transfer_count
    return Decimal("0.0")


def _ensure_squad_integrity(db: Session, fantasy_team_id: int, strict: bool) -> None:
    if not strict:
        return
    squad_count = int(
        db.execute(
            select(func.count())
            .select_from(FantasyTeamPlayer)
            .where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id)
        ).scalar()
        or 0
    )
    if squad_count != 15:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"transfer_revert_invalid_squad_size:team={fantasy_team_id}:count={squad_count}",
        )


def _recompute_team_budget_cap_for_round(
    db: Session,
    season_id: int,
    round_obj: Round,
    team: FantasyTeam,
) -> Decimal:
    if round_obj.round_number <= 1:
        team.budget_cap = _round_price(Decimal("100.0"))
        return team.budget_cap

    if round_obj.is_closed:
        return _round_price(team.budget_cap)

    prev_closed_round = (
        db.execute(
            select(Round)
            .where(
                Round.season_id == season_id,
                Round.is_closed.is_(True),
                Round.round_number < round_obj.round_number,
            )
            .order_by(Round.round_number.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )

    market_delta_total = Decimal("0.0")
    if prev_closed_round is not None:
        player_ids = _get_team_player_ids_for_delta(db, team.id)
        if player_ids:
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
            market_delta_total = _round_price(delta_total)

    transfer_count = _get_transfer_count_for_round(db, team.id, round_obj.id)
    fee_total = _get_transfer_fee_total_for_count(transfer_count)
    effective_cap = _round_price(Decimal("100.0") + market_delta_total - fee_total)
    team.budget_cap = effective_cap
    return effective_cap


def _revert_transfer_row(
    db: Session,
    transfer: FantasyTransfer,
    round_obj: Round,
    strict: bool,
) -> tuple[str, str | None]:
    team_player_ids = _get_team_player_ids(db, transfer.fantasy_team_id)
    has_in = transfer.in_player_id in team_player_ids
    has_out = transfer.out_player_id in team_player_ids

    if has_in and not has_out:
        out_player = db.get(PlayerCatalog, transfer.out_player_id)
        if out_player is None:
            reason = f"out_player_not_found:{transfer.out_player_id}"
            if strict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"transfer_revert_conflict:transfer_id={transfer.id}:{reason}",
                )
            return "skipped", reason

        db.execute(
            delete(FantasyTeamPlayer).where(
                FantasyTeamPlayer.fantasy_team_id == transfer.fantasy_team_id,
                FantasyTeamPlayer.player_id == transfer.in_player_id,
            )
        )
        db.add(
            FantasyTeamPlayer(
                fantasy_team_id=transfer.fantasy_team_id,
                player_id=transfer.out_player_id,
                bought_price=float(out_player.price_current),
                bought_round_id=round_obj.id,
                is_active=True,
            )
        )
        db.flush()
        db.delete(transfer)
        return "reverted", None

    if (not has_in) and has_out:
        # The squad was already restored manually; drop stale transfer log.
        db.delete(transfer)
        return "log_deleted", None

    reason = (
        "both_players_present"
        if has_in and has_out
        else "both_players_missing"
    )
    if strict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"transfer_revert_conflict:transfer_id={transfer.id}:{reason}",
        )
    return "skipped", reason


def _ensure_fixture_teams(
    db: Session,
    home_team_id: Optional[int],
    away_team_id: Optional[int],
) -> None:
    if home_team_id is not None and away_team_id is not None and home_team_id == away_team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="teams_must_differ")
    team_ids = [team_id for team_id in (home_team_id, away_team_id) if team_id is not None]
    if not team_ids:
        return
    existing = set(
        db.execute(select(Team.id).where(Team.id.in_(team_ids))).scalars().all()
    )
    missing = {team_id for team_id in team_ids if team_id not in existing}
    if not missing:
        return
    for team_id in sorted(missing):
        db.add(Team(id=team_id))
    db.flush()


def _parse_kickoff(value: Optional[str | datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_kickoff_at")


def _remove_team_from_league(db: Session, team_id: int) -> None:
    row = (
        db.execute(
            select(League, LeagueMember)
            .join(LeagueMember, LeagueMember.league_id == League.id)
            .where(LeagueMember.fantasy_team_id == team_id)
        )
        .first()
    )
    if not row:
        return
    league, _ = row

    db.execute(
        delete(LeagueMember).where(
            LeagueMember.league_id == league.id,
            LeagueMember.fantasy_team_id == team_id,
        )
    )

    if league.owner_fantasy_team_id == team_id:
        members = (
            db.execute(
                select(LeagueMember)
                .where(LeagueMember.league_id == league.id)
                .order_by(LeagueMember.joined_at)
            )
            .scalars()
            .all()
        )
        if not members:
            db.execute(
                update(ActionLog).where(ActionLog.league_id == league.id).values(league_id=None)
            )
            db.execute(delete(League).where(League.id == league.id))
        else:
            db.execute(
                update(League)
                .where(League.id == league.id)
                .values(owner_fantasy_team_id=members[0].fantasy_team_id)
            )


def _delete_user_data(db: Session, user: User) -> None:
    db.execute(
        update(ActionLog).where(ActionLog.actor_user_id == user.id).values(actor_user_id=None)
    )
    db.execute(
        update(ActionLog).where(ActionLog.target_user_id == user.id).values(target_user_id=None)
    )
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    teams = (
        db.execute(select(FantasyTeam).where(FantasyTeam.user_id == user.id)).scalars().all()
    )
    for team in teams:
        db.execute(
            update(ActionLog)
            .where(ActionLog.fantasy_team_id == team.id)
            .values(fantasy_team_id=None)
        )
        db.execute(
            update(ActionLog)
            .where(ActionLog.target_fantasy_team_id == team.id)
            .values(target_fantasy_team_id=None)
        )
        _remove_team_from_league(db, team.id)
        db.execute(
            delete(FantasyLineupSlot).where(
                FantasyLineupSlot.lineup_id.in_(
                    select(FantasyLineup.id).where(FantasyLineup.fantasy_team_id == team.id)
                )
            )
        )
        db.execute(delete(FantasyLineup).where(FantasyLineup.fantasy_team_id == team.id))
        db.execute(delete(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team.id))
        db.execute(delete(FantasyTransfer).where(FantasyTransfer.fantasy_team_id == team.id))
        db.execute(delete(LeagueMember).where(LeagueMember.fantasy_team_id == team.id))
        db.execute(delete(FantasyTeam).where(FantasyTeam.id == team.id))
    db.execute(delete(User).where(User.id == user.id))


@router.post("/rebuild_catalog")
def rebuild_catalog() -> dict:
    settings = get_settings()
    ingest_parquets_to_duckdb(settings)
    sync_duckdb_to_postgres(settings)
    return {"ok": True}


@router.post("/apply_prices")
def apply_prices(
    round_number: int = Query(..., ge=1),
    refresh_from_duckdb: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    season = get_or_create_season(db)
    round_obj = db.execute(
        select(Round).where(Round.season_id == season.id, Round.round_number == round_number)
    ).scalar_one_or_none()
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    db.execute(
        text(
            """
            INSERT INTO price_history (season_id, round_id, player_id, price)
            SELECT :season_id, :round_id, player_id, price_current
            FROM players_catalog
            ON CONFLICT (season_id, round_id, player_id)
            DO UPDATE SET price = EXCLUDED.price
            """
        ),
        {"season_id": season.id, "round_id": round_obj.id},
    )
    db.commit()

    if refresh_from_duckdb:
        sync_duckdb_to_postgres(get_settings())

    return {"ok": True}


@router.post("/recalc_round")
def recalc_round(
    round_number: int = Query(..., ge=1),
    apply_prices: bool = Query(default=True),
    write_price_history: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = recalc_round_points(
            db,
            round_number=round_number,
            apply_prices=apply_prices,
            write_price_history=write_price_history,
        )
        log_action(
            db,
            category="round",
            action="recalc",
            details={
                "round_number": round_number,
                "apply_prices": apply_prices,
                "write_price_history": write_price_history,
            },
        )
        return result
    except ValueError as exc:
        if str(exc) == "round_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found") from exc
        raise


@router.post("/recalc_match")
def recalc_match(
    match_id: int = Query(..., ge=1),
    apply_prices: bool = Query(default=False),
    write_price_history: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    season = get_or_create_season(db)
    fixture = (
        db.execute(
            select(Fixture).where(
                Fixture.season_id == season.id,
                Fixture.match_id == match_id,
            )
        )
        .scalars()
        .first()
    )
    if not fixture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fixture_not_found")

    round_number = db.execute(select(Round.round_number).where(Round.id == fixture.round_id)).scalar_one()
    result = recalc_round_points(
        db,
        round_number=round_number,
        apply_prices=apply_prices,
        write_price_history=write_price_history,
    )
    log_action(
        db,
        category="round",
        action="recalc_match",
        details={
            "match_id": match_id,
            "round_number": round_number,
            "apply_prices": apply_prices,
            "write_price_history": write_price_history,
        },
    )
    return result


@router.post("/rounds/status")
def set_round_status(
    round_number: int = Query(..., ge=1),
    status_value: str = Query(..., alias="status"),
    db: Session = Depends(get_db),
) -> dict:
    season = get_or_create_season(db)
    round_obj = get_round_by_number(db, season.id, round_number)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    normalized = status_value.strip().capitalize()
    if normalized not in {"Cerrada", "Pendiente", "Proximamente"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_status")

    if normalized == "Cerrada":
        round_obj.is_closed = True
        db.commit()
        return {"ok": True, "round_number": round_number, "status": "Cerrada"}

    rounds = (
        db.execute(select(Round).where(Round.season_id == season.id).order_by(Round.round_number))
        .scalars()
        .all()
    )
    if not rounds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    if normalized == "Pendiente":
        pending_round = round_number
    else:
        open_before = [round.round_number for round in rounds if not round.is_closed and round.round_number < round_number]
        if open_before:
            pending_round = min(open_before)
        else:
            previous = [round.round_number for round in rounds if round.round_number < round_number]
            if not previous:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pending_round_required")
            pending_round = max(previous)

    for round_item in rounds:
        if round_item.round_number < pending_round:
            round_item.is_closed = True
        else:
            round_item.is_closed = False

    db.commit()
    return {"ok": True, "round_number": round_number, "status": normalized, "pending_round": pending_round}


@router.post("/seed_season_rounds")
def seed_season_rounds(
    rounds: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    season = get_or_create_season(db)
    if rounds is None:
        rounds = db.execute(
            select(func.max(Round.round_number)).where(Round.season_id == season.id)
        ).scalar()
        if not rounds:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rounds_required")

    for round_number in range(1, rounds + 1):
        ensure_round(db, season.id, round_number)

    return {"ok": True, "rounds": rounds}


@router.get("/players", response_model=AdminPlayerListOut)
def list_players(db: Session = Depends(get_db)) -> AdminPlayerListOut:
    season = get_or_create_season(db)
    selected_subq = (
        select(FantasyTeamPlayer.player_id)
        .join(FantasyTeam, FantasyTeam.id == FantasyTeamPlayer.fantasy_team_id)
        .where(FantasyTeam.season_id == season.id, FantasyTeamPlayer.is_active.is_(True))
        .distinct()
        .subquery()
    )

    total = db.execute(select(func.count()).select_from(PlayerCatalog)).scalar() or 0
    injured = (
        db.execute(select(func.count()).select_from(PlayerCatalog).where(PlayerCatalog.is_injured.is_(True)))
        .scalar()
        or 0
    )
    unselected = (
        db.execute(
            select(func.count())
            .select_from(PlayerCatalog)
            .where(PlayerCatalog.player_id.not_in(select(selected_subq.c.player_id)))
        ).scalar()
        or 0
    )

    rows = (
        db.execute(
            select(
                PlayerCatalog.player_id,
                PlayerCatalog.name,
                PlayerCatalog.short_name,
                PlayerCatalog.position,
                PlayerCatalog.team_id,
                PlayerCatalog.is_injured,
            ).order_by(PlayerCatalog.name)
        )
        .all()
    )

    items = [
        AdminPlayerListItem(
            player_id=row.player_id,
            name=row.name,
            short_name=row.short_name,
            position=row.position,
            team_id=row.team_id,
            is_injured=bool(row.is_injured),
        )
        for row in rows
    ]

    return AdminPlayerListOut(total=int(total), injured=int(injured), unselected=int(unselected), items=items)


@router.get("/teams", response_model=List[AdminTeamOut])
def list_teams(
    season_year: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> List[AdminTeamOut]:
    if season_year is not None:
        season = db.execute(select(Season).where(Season.year == season_year)).scalar_one_or_none()
        if not season:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="season_not_found")
    else:
        season = get_or_create_season(db)

    team_rows = (
        db.execute(
            select(FantasyTeam, User)
            .join(User, User.id == FantasyTeam.user_id)
            .where(FantasyTeam.season_id == season.id)
            .order_by(User.email)
        )
        .all()
    )
    if not team_rows:
        return []

    team_ids = [team.id for team, _ in team_rows]
    player_rows = (
        db.execute(
            select(FantasyTeamPlayer.fantasy_team_id, PlayerCatalog, FantasyTeamPlayer)
            .join(PlayerCatalog, PlayerCatalog.player_id == FantasyTeamPlayer.player_id)
            .where(FantasyTeamPlayer.fantasy_team_id.in_(team_ids))
        )
        .all()
    )

    squad_map: Dict[int, List[AdminTeamPlayerOut]] = {team_id: [] for team_id in team_ids}
    budget_map: Dict[int, float] = {team_id: 0.0 for team_id in team_ids}
    club_map: Dict[int, Dict[int, int]] = {team_id: {} for team_id in team_ids}

    for team_id, player, team_player in player_rows:
        squad_map[team_id].append(
            AdminTeamPlayerOut(
                player_id=player.player_id,
                name=player.name,
                short_name=player.short_name,
                position=player.position,
                team_id=player.team_id,
                price_current=float(player.price_current),
                bought_price=float(team_player.bought_price),
                is_injured=bool(player.is_injured),
            )
        )
        budget_map[team_id] += float(team_player.bought_price)
        club_counts = club_map[team_id]
        club_counts[player.team_id] = club_counts.get(player.team_id, 0) + 1

    results: List[AdminTeamOut] = []
    for team, user in team_rows:
        budget_used = budget_map.get(team.id, 0.0)
        results.append(
            AdminTeamOut(
                fantasy_team_id=team.id,
                user_id=user.id,
                user_email=user.email,
                season_id=team.season_id,
                name=team.name,
                budget_cap=float(team.budget_cap),
                budget_used=budget_used,
                budget_left=float(team.budget_cap) - budget_used,
                club_counts=club_map.get(team.id, {}),
                squad=squad_map.get(team.id, []),
            )
        )

    return results


@router.get("/lineups", response_model=List[AdminTeamLineupOut])
def list_lineups(
    round_number: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> List[AdminTeamLineupOut]:
    season = get_or_create_season(db)
    if round_number is not None:
        round_obj = get_round_by_number(db, season.id, round_number)
        if not round_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")
    else:
        round_obj = (
            db.execute(
                select(Round)
                .where(Round.season_id == season.id, Round.is_closed.is_(False))
                .order_by(Round.round_number.asc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if not round_obj:
            round_obj = (
                db.execute(
                    select(Round)
                    .where(Round.season_id == season.id)
                    .order_by(Round.round_number.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
    if not round_obj:
        return []

    lineup_rows = (
        db.execute(
            select(FantasyLineup, FantasyTeam, User)
            .join(FantasyTeam, FantasyTeam.id == FantasyLineup.fantasy_team_id)
            .join(User, User.id == FantasyTeam.user_id)
            .where(
                FantasyTeam.season_id == season.id,
                FantasyLineup.round_id == round_obj.id,
            )
            .order_by(FantasyLineup.created_at.desc())
        )
        .all()
    )
    if not lineup_rows:
        return []

    lineup_ids = [lineup.id for lineup, _, _ in lineup_rows]
    slots_rows = (
        db.execute(
            select(FantasyLineupSlot, PlayerCatalog)
            .outerjoin(PlayerCatalog, FantasyLineupSlot.player_id == PlayerCatalog.player_id)
            .where(FantasyLineupSlot.lineup_id.in_(lineup_ids))
        )
        .all()
    )

    slot_map: Dict[int, List[AdminLineupSlotOut]] = {lid: [] for lid in lineup_ids}
    for slot, player in slots_rows:
        slot_map[slot.lineup_id].append(
            AdminLineupSlotOut(
                slot_index=slot.slot_index,
                is_starter=slot.is_starter,
                role=slot.role,
                player_id=slot.player_id,
                player=(
                    AdminLineupPlayerOut(
                        player_id=player.player_id,
                        name=player.name,
                        short_name=player.short_name,
                        position=player.position,
                        team_id=player.team_id,
                        is_injured=bool(player.is_injured),
                    )
                    if player is not None
                    else None
                ),
            )
        )

    results: List[AdminTeamLineupOut] = []
    for lineup, team, user in lineup_rows:
        slots_sorted = sorted(slot_map.get(lineup.id, []), key=lambda item: item.slot_index)
        results.append(
            AdminTeamLineupOut(
                fantasy_team_id=team.id,
                team_name=team.name,
                user_email=user.email,
                round_number=round_obj.round_number,
                lineup_id=lineup.id,
                created_at=lineup.created_at,
                captain_player_id=lineup.captain_player_id,
                vice_captain_player_id=lineup.vice_captain_player_id,
                slots=slots_sorted,
            )
        )

    return results


@router.put("/players/{player_id}/injury", response_model=AdminPlayerInjuryOut)
def update_player_injury(
    player_id: int,
    payload: AdminPlayerInjuryIn,
    db: Session = Depends(get_db),
) -> AdminPlayerInjuryOut:
    player = db.get(PlayerCatalog, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player_not_found")
    player.is_injured = payload.is_injured
    db.commit()
    return AdminPlayerInjuryOut(player_id=player_id, is_injured=bool(player.is_injured))


@router.get("/fixtures", response_model=List[AdminFixtureOut])
def list_fixtures(
    round_number: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> List[AdminFixtureOut]:
    season = get_or_create_season(db)
    query = (
        select(Fixture, Round.round_number)
        .join(Round, Fixture.round_id == Round.id)
        .where(Round.season_id == season.id)
        .order_by(Round.round_number, Fixture.kickoff_at.nulls_last(), Fixture.match_id)
    )
    if round_number is not None:
        query = query.where(Round.round_number == round_number)

    rows = db.execute(query).all()
    return [
        AdminFixtureOut(
            id=fixture.id,
            round_number=round_no,
            match_id=fixture.match_id,
            home_team_id=fixture.home_team_id,
            away_team_id=fixture.away_team_id,
            kickoff_at=fixture.kickoff_at,
            stadium=fixture.stadium,
            city=fixture.city,
            status=fixture.status,
            home_score=fixture.home_score,
            away_score=fixture.away_score,
        )
        for fixture, round_no in rows
    ]


@router.post("/fixtures", response_model=AdminFixtureOut)
def upsert_fixture(
    payload: AdminFixtureCreate,
    db: Session = Depends(get_db),
) -> AdminFixtureOut:
    if payload.round_number < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="round_invalid")
    if payload.match_id < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="match_id_invalid")
    season = get_or_create_season(db)
    round_obj = ensure_round(db, season.id, payload.round_number)
    _ensure_fixture_teams(db, payload.home_team_id, payload.away_team_id)
    kickoff_at = _parse_kickoff(payload.kickoff_at)
    stadium = payload.stadium.strip() if payload.stadium else None
    city = payload.city.strip() if payload.city else None

    values = {
        "season_id": season.id,
        "round_id": round_obj.id,
        "match_id": payload.match_id,
        "home_team_id": payload.home_team_id,
        "away_team_id": payload.away_team_id,
        "kickoff_at": kickoff_at,
        "stadium": stadium,
        "city": city,
        "status": payload.status or "Programado",
        "home_score": payload.home_score,
        "away_score": payload.away_score,
    }

    try:
        update_values = {k: v for k, v in values.items() if k != "match_id"}
        updated = db.execute(
            update(Fixture)
            .where(Fixture.match_id == payload.match_id)
            .values(**update_values)
        )
        if not updated.rowcount:
            next_id = db.execute(select(func.coalesce(func.max(Fixture.id), 0) + 1)).scalar_one()
            db.execute(insert(Fixture).values(id=next_id, **values))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        detail = "db_integrity_error"
        if exc.orig:
            detail = f"db_integrity_error: {exc.orig}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    except SQLAlchemyError as exc:
        db.rollback()
        detail = f"db_error: {exc}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    fixture = db.execute(select(Fixture).where(Fixture.match_id == payload.match_id)).scalar_one()

    return AdminFixtureOut(
        id=fixture.id,
        round_number=payload.round_number,
        match_id=fixture.match_id,
        home_team_id=fixture.home_team_id,
        away_team_id=fixture.away_team_id,
        kickoff_at=fixture.kickoff_at,
        stadium=fixture.stadium,
        city=fixture.city,
        status=fixture.status,
        home_score=fixture.home_score,
        away_score=fixture.away_score,
    )


@router.post("/player-stats")
def upsert_player_stats(
    payload: AdminPlayerRoundStatsIn,
    db: Session = Depends(get_db),
) -> dict:
    if not payload.items:
        return {"ok": True, "count": 0}

    season = get_or_create_season(db)
    round_obj = ensure_round(db, season.id, payload.round_number)

    match_ids = {item.match_id for item in payload.items}
    player_ids = {item.player_id for item in payload.items}

    fixtures = (
        db.execute(
            select(Fixture).where(
                Fixture.season_id == season.id,
                Fixture.match_id.in_(match_ids),
            )
        )
        .scalars()
        .all()
    )
    fixture_map = {fixture.match_id: fixture for fixture in fixtures}
    missing_matches = match_ids.difference(fixture_map.keys())
    if missing_matches:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"fixture_not_found:{sorted(missing_matches)}",
        )
    mismatch_round = [
        fixture.match_id for fixture in fixtures if fixture.round_id != round_obj.id
    ]
    if mismatch_round:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"fixture_round_mismatch:{sorted(mismatch_round)}",
        )

    players = (
        db.execute(select(PlayerCatalog).where(PlayerCatalog.player_id.in_(player_ids)))
        .scalars()
        .all()
    )
    player_map = {player.player_id: player for player in players}
    missing_players = sorted(player_ids.difference(player_map.keys()))

    rows = [
        {
            "season_id": season.id,
            "round_id": round_obj.id,
            "match_id": item.match_id,
            "player_id": item.player_id,
            "minutesplayed": item.minutesplayed or 0,
            "goals": item.goals or 0,
            "assists": item.assists or 0,
            "saves": item.saves or 0,
            "fouls": item.fouls or 0,
            "yellow_cards": item.yellow_cards or 0,
            "red_cards": item.red_cards or 0,
            "clean_sheet": item.clean_sheet,
            "goals_conceded": item.goals_conceded,
        }
        for item in payload.items
        if item.player_id in player_map
    ]

    for row in rows:
        fixture = fixture_map.get(row["match_id"])
        player = player_map.get(row["player_id"])
        if not fixture or not player:
            continue
        if fixture.home_score is None or fixture.away_score is None:
            continue
        conceded = _goals_conceded_from_fixture(fixture, player.team_id)
        if conceded is None:
            continue
        if row["goals_conceded"] in (None, 0):
            row["goals_conceded"] = conceded
        if row["clean_sheet"] in (None, 0):
            position = (player.position or "").upper()
            minutes = int(row["minutesplayed"] or 0)
            if position in {"G", "GK", "D", "M"} and minutes > 0:
                row["clean_sheet"] = 1 if conceded == 0 else 0

    db.execute(
        text(
            """
            INSERT INTO player_match_stats (
                season_id, round_id, match_id, player_id, minutesplayed, goals, assists, saves, fouls,
                yellow_cards, red_cards, clean_sheet, goals_conceded, updated_at
            )
            VALUES (
                :season_id, :round_id, :match_id, :player_id, :minutesplayed, :goals, :assists, :saves, :fouls,
                :yellow_cards, :red_cards, :clean_sheet, :goals_conceded, NOW()
            )
            ON CONFLICT (season_id, round_id, match_id, player_id)
            DO UPDATE SET
                minutesplayed = EXCLUDED.minutesplayed,
                goals = EXCLUDED.goals,
                assists = EXCLUDED.assists,
                saves = EXCLUDED.saves,
                fouls = EXCLUDED.fouls,
                yellow_cards = EXCLUDED.yellow_cards,
                red_cards = EXCLUDED.red_cards,
                clean_sheet = EXCLUDED.clean_sheet,
                goals_conceded = EXCLUDED.goals_conceded,
                updated_at = NOW()
            """
        ),
        rows,
    )
    db.commit()
    log_action(
        db,
        category="stats",
        action="upsert",
        details={"round_number": payload.round_number, "count": len(rows)},
    )
    response = {"ok": True, "count": len(rows)}
    if missing_players:
        response["skipped_missing_players"] = missing_players
    return response


@router.get("/player-stats", response_model=List[AdminPlayerStatOut])
def list_player_stats(
    round_number: int = Query(..., ge=1),
    match_id: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> List[AdminPlayerStatOut]:
    season = get_or_create_season(db)
    round_obj = get_round_by_number(db, season.id, round_number)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    query = select(PlayerMatchStat).where(
        PlayerMatchStat.season_id == season.id,
        PlayerMatchStat.round_id == round_obj.id,
    )
    if match_id is not None:
        query = query.where(PlayerMatchStat.match_id == match_id)
    rows = db.execute(query).scalars().all()
    return [
        AdminPlayerStatOut(
            round_number=round_number,
            match_id=row.match_id,
            player_id=row.player_id,
            minutesplayed=row.minutesplayed,
            goals=row.goals,
            assists=row.assists,
            saves=row.saves,
            fouls=row.fouls,
            yellow_cards=row.yellow_cards,
            red_cards=row.red_cards,
            clean_sheet=row.clean_sheet,
            goals_conceded=row.goals_conceded,
        )
        for row in rows
    ]


def _goals_conceded_from_fixture(fixture: Fixture | None, team_id: int | None) -> int | None:
    if fixture is None or team_id is None:
        return None
    if fixture.home_score is None or fixture.away_score is None:
        return None
    if fixture.home_team_id == team_id:
        return fixture.away_score
    if fixture.away_team_id == team_id:
        return fixture.home_score
    return None


def _calc_match_points(
    player: PlayerCatalog,
    stat: PlayerMatchStat,
    fixture: Fixture | None,
) -> tuple[float, int | None, int | None]:
    return calc_match_points(player, stat, fixture)


@router.get("/match-stats", response_model=List[AdminMatchPlayerOut])
def list_match_stats(
    match_id: int = Query(..., ge=1),
    round_number: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> List[AdminMatchPlayerOut]:
    season = get_or_create_season(db)
    round_obj = None
    if round_number is not None:
        round_obj = get_round_by_number(db, season.id, round_number)
        if not round_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    fixture_query = select(Fixture).where(
        Fixture.season_id == season.id, Fixture.match_id == match_id
    )
    if round_obj is not None:
        fixture_query = fixture_query.where(Fixture.round_id == round_obj.id)
    fixture = db.execute(fixture_query).scalar_one_or_none()

    query = select(PlayerMatchStat).where(
        PlayerMatchStat.season_id == season.id,
        PlayerMatchStat.match_id == match_id,
    )
    if round_obj is not None:
        query = query.where(PlayerMatchStat.round_id == round_obj.id)
    rows = db.execute(query).scalars().all()
    if not rows:
        return []

    player_ids = {row.player_id for row in rows}
    players = (
        db.execute(select(PlayerCatalog).where(PlayerCatalog.player_id.in_(player_ids)))
        .scalars()
        .all()
    )
    player_map = {player.player_id: player for player in players}

    results: List[AdminMatchPlayerOut] = []
    for row in rows:
        player = player_map.get(row.player_id)
        if not player:
            continue
        points, clean_sheet_value, conceded = _calc_match_points(player, row, fixture)
        results.append(
            AdminMatchPlayerOut(
                match_id=match_id,
                player_id=row.player_id,
                name=player.name,
                short_name=player.short_name,
                position=player.position,
                team_id=player.team_id,
                minutesplayed=int(row.minutesplayed or 0),
                goals=int(row.goals or 0),
                assists=int(row.assists or 0),
                saves=int(row.saves or 0),
                fouls=int(row.fouls or 0),
                yellow_cards=int(getattr(row, "yellow_cards", 0) or 0),
                red_cards=int(getattr(row, "red_cards", 0) or 0),
                clean_sheet=clean_sheet_value,
                goals_conceded=conceded,
                points=float(points),
            )
        )

    return sorted(results, key=lambda item: (-(item.points or 0), item.name))


@router.get("/rounds/top_players", response_model=List[AdminRoundTopPlayerOut])
def list_round_top_players(
    round_number: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> List[AdminRoundTopPlayerOut]:
    season = get_or_create_season(db)
    round_obj = get_round_by_number(db, season.id, round_number)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    points_rows = db.execute(
        select(
            PointsRound.player_id,
            func.coalesce(func.sum(PointsRound.points), 0).label("points"),
        )
        .where(
            PointsRound.season_id == season.id,
            PointsRound.round_id == round_obj.id,
        )
        .group_by(PointsRound.player_id)
        .order_by(text("points DESC"))
        .limit(10)
    ).all()

    if not points_rows:
        return []

    player_ids = [row[0] for row in points_rows]
    players = (
        db.execute(select(PlayerCatalog).where(PlayerCatalog.player_id.in_(player_ids)))
        .scalars()
        .all()
    )
    player_map = {player.player_id: player for player in players}

    results: List[AdminRoundTopPlayerOut] = []
    for player_id, points in points_rows:
        player = player_map.get(player_id)
        if not player:
            continue
        results.append(
            AdminRoundTopPlayerOut(
                player_id=player_id,
                name=player.name,
                short_name=player.short_name,
                position=player.position,
                team_id=player.team_id,
                points=float(points or 0),
            )
        )

    return results


@router.get("/price-movements", response_model=List[AdminPriceMovementOut])
def list_price_movements(
    round_number: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> List[AdminPriceMovementOut]:
    season = get_or_create_season(db)
    query = (
        select(PriceMovement, PlayerCatalog, Round.round_number)
        .join(PlayerCatalog, PlayerCatalog.player_id == PriceMovement.player_id)
        .join(Round, Round.id == PriceMovement.round_id)
        .where(PriceMovement.season_id == season.id)
        .order_by(Round.round_number, PriceMovement.delta.desc(), PlayerCatalog.name)
    )
    if round_number is not None:
        query = query.where(Round.round_number == round_number)

    rows = db.execute(query).all()
    return [
        AdminPriceMovementOut(
            round_number=round_no,
            player_id=player.player_id,
            name=player.name,
            short_name=player.short_name,
            position=player.position,
            team_id=player.team_id,
            price_current=float(player.price_current),
            points=float(movement.points),
            delta=float(movement.delta),
        )
        for movement, player, round_no in rows
    ]


@router.get("/transfers", response_model=List[AdminTransferOut])
def list_transfers(
    round_number: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> List[AdminTransferOut]:
    season = get_or_create_season(db)
    out_player = aliased(PlayerCatalog)
    in_player = aliased(PlayerCatalog)
    query = (
        select(
            FantasyTransfer,
            FantasyTeam,
            User,
            Round.round_number,
            out_player,
            in_player,
        )
        .join(FantasyTeam, FantasyTeam.id == FantasyTransfer.fantasy_team_id)
        .join(User, User.id == FantasyTeam.user_id)
        .join(Round, Round.id == FantasyTransfer.round_id)
        .join(out_player, out_player.player_id == FantasyTransfer.out_player_id)
        .join(in_player, in_player.player_id == FantasyTransfer.in_player_id)
        .where(FantasyTeam.season_id == season.id)
        .order_by(FantasyTransfer.created_at.desc())
    )
    if round_number is not None:
        query = query.where(Round.round_number == round_number)

    rows = db.execute(query).all()
    if not rows:
        return []

    current_budget_map = {
        team.id: float(team.budget_cap)
        for _, team, _, _, _, _ in rows
    }

    sorted_by_time = sorted(rows, key=lambda row: row[0].created_at, reverse=True)

    results: List[AdminTransferOut] = []
    for transfer, team, user, round_no, out_p, in_p in sorted_by_time:
        fee = 0.0
        budget_after = current_budget_map.get(team.id, 0.0)
        results.append(
            AdminTransferOut(
                id=transfer.id,
                fantasy_team_id=team.id,
                team_name=team.name,
                user_email=user.email,
                round_number=round_no,
                created_at=transfer.created_at,
                out_player=(
                    AdminTransferPlayerOut(
                        player_id=out_p.player_id,
                        name=out_p.name,
                        short_name=out_p.short_name,
                        position=out_p.position,
                        team_id=out_p.team_id,
                    )
                    if out_p
                    else None
                ),
                in_player=(
                    AdminTransferPlayerOut(
                        player_id=in_p.player_id,
                        name=in_p.name,
                        short_name=in_p.short_name,
                        position=in_p.position,
                        team_id=in_p.team_id,
                    )
                    if in_p
                    else None
                ),
                out_price=float(transfer.out_price),
                in_price=float(transfer.in_price),
                out_price_current=float(out_p.price_current),
                in_price_current=float(in_p.price_current),
                transfer_fee=fee,
                budget_after=budget_after,
            )
        )
    return results


@router.post("/transfers/restore")
def restore_transfers_for_round(
    round_number: Optional[int] = Query(default=None, ge=1),
    reimburse_fees: bool = Query(default=True),
    revert_squad: bool = Query(default=True),
    strict: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    season = get_or_create_season(db)
    round_obj = _resolve_round_for_transfer_admin(db, season.id, round_number)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    transfers = (
        db.execute(
            select(FantasyTransfer)
            .where(FantasyTransfer.round_id == round_obj.id)
            .order_by(FantasyTransfer.created_at.desc(), FantasyTransfer.id.desc())
        )
        .scalars()
        .all()
    )
    if not transfers:
        return {
            "ok": True,
            "round_number": round_obj.round_number,
            "transfers_deleted": 0,
            "teams_affected": 0,
            "swaps_reverted": 0,
            "logs_deleted": 0,
            "skipped": 0,
            "fees_reimbursed_total": 0.0,
            "teams_reimbursed": 0,
            "teams_recomputed": 0,
            "note": "no_transfers_found",
        }

    original_count_by_team: Dict[int, int] = {}
    for transfer in transfers:
        original_count_by_team[transfer.fantasy_team_id] = (
            original_count_by_team.get(transfer.fantasy_team_id, 0) + 1
        )

    deleted_count_by_team: Dict[int, int] = {}
    affected_team_ids: set[int] = set()
    swaps_reverted = 0
    logs_deleted = 0
    skipped = 0
    skipped_details: List[dict] = []

    if revert_squad:
        for transfer in transfers:
            affected_team_ids.add(transfer.fantasy_team_id)
            status_label, reason = _revert_transfer_row(
                db,
                transfer,
                round_obj,
                strict=strict,
            )
            if status_label == "reverted":
                swaps_reverted += 1
                deleted_count_by_team[transfer.fantasy_team_id] = (
                    deleted_count_by_team.get(transfer.fantasy_team_id, 0) + 1
                )
            elif status_label == "log_deleted":
                logs_deleted += 1
                deleted_count_by_team[transfer.fantasy_team_id] = (
                    deleted_count_by_team.get(transfer.fantasy_team_id, 0) + 1
                )
            else:
                skipped += 1
                skipped_details.append(
                    {
                        "transfer_id": transfer.id,
                        "fantasy_team_id": transfer.fantasy_team_id,
                        "reason": reason or "unknown",
                    }
                )
    else:
        transfer_ids = [transfer.id for transfer in transfers]
        db.execute(delete(FantasyTransfer).where(FantasyTransfer.id.in_(transfer_ids)))
        for transfer in transfers:
            affected_team_ids.add(transfer.fantasy_team_id)
            deleted_count_by_team[transfer.fantasy_team_id] = (
                deleted_count_by_team.get(transfer.fantasy_team_id, 0) + 1
            )
        logs_deleted = len(transfer_ids)

    teams_recomputed = 0
    fees_reimbursed_total = Decimal("0.0")
    teams_reimbursed = 0

    team_ids_to_update = sorted(affected_team_ids)
    teams = (
        db.execute(select(FantasyTeam).where(FantasyTeam.id.in_(team_ids_to_update)))
        .scalars()
        .all()
        if team_ids_to_update
        else []
    )
    teams_by_id = {team.id: team for team in teams}

    for team_id in team_ids_to_update:
        _ensure_squad_integrity(db, team_id, strict=strict)

    if not round_obj.is_closed:
        for team_id in team_ids_to_update:
            team = teams_by_id.get(team_id)
            if not team:
                continue
            _recompute_team_budget_cap_for_round(db, season.id, round_obj, team)
            teams_recomputed += 1
    elif reimburse_fees:
        for team_id, before_count in original_count_by_team.items():
            deleted_count = deleted_count_by_team.get(team_id, 0)
            if deleted_count <= 0:
                continue
            after_count = max(0, before_count - deleted_count)
            fee_before = _get_transfer_fee_total_for_count(before_count)
            fee_after = _get_transfer_fee_total_for_count(after_count)
            reimbursed = fee_before - fee_after
            if reimbursed <= 0:
                continue
            team = teams_by_id.get(team_id)
            if not team:
                continue
            team.budget_cap = _round_price(Decimal(str(team.budget_cap)) + reimbursed)
            fees_reimbursed_total += reimbursed
            teams_reimbursed += 1

    db.commit()

    return {
        "ok": True,
        "round_number": round_obj.round_number,
        "transfers_deleted": int(sum(deleted_count_by_team.values())),
        "teams_affected": len(team_ids_to_update),
        "swaps_reverted": swaps_reverted,
        "logs_deleted": logs_deleted,
        "skipped": skipped,
        "skipped_details": skipped_details,
        "revert_squad": bool(revert_squad),
        "strict": bool(strict),
        "fees_reimbursed_total": float(_round_price(fees_reimbursed_total)),
        "teams_reimbursed": teams_reimbursed,
        "teams_recomputed": teams_recomputed,
    }


@router.post("/transfers/{transfer_id}/revert")
def revert_transfer_by_id(
    transfer_id: int,
    strict: bool = Query(default=True),
    reimburse_fees: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    season = get_or_create_season(db)
    row = (
        db.execute(
            select(FantasyTransfer, Round)
            .join(Round, Round.id == FantasyTransfer.round_id)
            .join(FantasyTeam, FantasyTeam.id == FantasyTransfer.fantasy_team_id)
            .where(
                FantasyTransfer.id == transfer_id,
                Round.season_id == season.id,
                FantasyTeam.season_id == season.id,
            )
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transfer_not_found")

    transfer, round_obj = row
    team = db.get(FantasyTeam, transfer.fantasy_team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team_not_found")

    before_count = _get_transfer_count_for_round(db, team.id, round_obj.id)
    status_label, reason = _revert_transfer_row(
        db,
        transfer,
        round_obj,
        strict=strict,
    )

    if status_label == "skipped":
        db.commit()
        return {
            "ok": False,
            "transfer_id": transfer_id,
            "status": "skipped",
            "reason": reason or "unknown",
        }

    _ensure_squad_integrity(db, team.id, strict=strict)

    fees_reimbursed_total = Decimal("0.0")
    if not round_obj.is_closed:
        _recompute_team_budget_cap_for_round(db, season.id, round_obj, team)
    elif reimburse_fees:
        after_count = max(0, before_count - 1)
        fee_before = _get_transfer_fee_total_for_count(before_count)
        fee_after = _get_transfer_fee_total_for_count(after_count)
        reimbursed = fee_before - fee_after
        if reimbursed > 0:
            team.budget_cap = _round_price(Decimal(str(team.budget_cap)) + reimbursed)
            fees_reimbursed_total = reimbursed

    db.commit()

    return {
        "ok": True,
        "transfer_id": transfer_id,
        "round_number": round_obj.round_number,
        "fantasy_team_id": team.id,
        "status": status_label,
        "fees_reimbursed_total": float(_round_price(fees_reimbursed_total)),
    }


@router.put("/fixtures/{fixture_id}", response_model=AdminFixtureOut)
def update_fixture(
    fixture_id: int,
    payload: AdminFixtureUpdate,
    db: Session = Depends(get_db),
) -> AdminFixtureOut:
    fixture = db.execute(select(Fixture).where(Fixture.id == fixture_id)).scalar_one_or_none()
    if not fixture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fixture_not_found")

    data = payload.model_dump(exclude_unset=True)

    if "match_id" in data and data["match_id"] is not None:
        existing = (
            db.execute(
                select(Fixture).where(Fixture.match_id == data["match_id"], Fixture.id != fixture_id)
            )
            .scalars()
            .first()
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="match_id_exists")
        fixture.match_id = data["match_id"]

    if "round_number" in data and data["round_number"] is not None:
        season = get_or_create_season(db)
        round_obj = ensure_round(db, season.id, data["round_number"])
        fixture.round_id = round_obj.id
        fixture.season_id = season.id

    if "home_team_id" in data:
        _ensure_fixture_teams(db, data.get("home_team_id"), None)
        fixture.home_team_id = data["home_team_id"]
    if "away_team_id" in data:
        _ensure_fixture_teams(db, None, data.get("away_team_id"))
        fixture.away_team_id = data["away_team_id"]
    if "kickoff_at" in data:
        fixture.kickoff_at = _parse_kickoff(data["kickoff_at"])
    if "stadium" in data:
        fixture.stadium = data["stadium"].strip() if data["stadium"] else None
    if "city" in data:
        fixture.city = data["city"].strip() if data["city"] else None
    if "home_score" in data:
        fixture.home_score = data["home_score"]
    if "away_score" in data:
        fixture.away_score = data["away_score"]
    if "status" in data and data["status"] is not None:
        fixture.status = data["status"]

    db.commit()
    db.refresh(fixture)

    round_number = db.execute(select(Round.round_number).where(Round.id == fixture.round_id)).scalar_one()

    return AdminFixtureOut(
        id=fixture.id,
        round_number=round_number,
        match_id=fixture.match_id,
        home_team_id=fixture.home_team_id,
        away_team_id=fixture.away_team_id,
        kickoff_at=fixture.kickoff_at,
        stadium=fixture.stadium,
        city=fixture.city,
        status=fixture.status,
        home_score=fixture.home_score,
        away_score=fixture.away_score,
    )


@router.get("/rounds", response_model=List[AdminRoundOut])
def list_rounds(db: Session = Depends(get_db)) -> List[AdminRoundOut]:
    season = get_or_create_season(db)
    rows = (
        db.execute(
            select(Round).where(Round.season_id == season.id).order_by(Round.round_number)
        )
        .scalars()
        .all()
    )
    pending_round = next((row.round_number for row in rows if not row.is_closed), None)
    return [
        AdminRoundOut(
            id=row.id,
            round_number=row.round_number,
            is_closed=row.is_closed,
            status=(
                "Cerrada"
                if row.is_closed
                else ("Pendiente" if pending_round == row.round_number else "Proximamente")
            ),
            starts_at=row.starts_at,
            ends_at=row.ends_at,
        )
        for row in rows
    ]


@router.put("/rounds/{round_number}/window")
def update_round_window(
    round_number: int,
    payload: AdminRoundWindowUpdateIn,
    db: Session = Depends(get_db),
) -> dict:
    season = get_or_create_season(db)
    round_obj = get_round_by_number(db, season.id, round_number)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="window_update_required")

    starts_at = data.get("starts_at", round_obj.starts_at)
    ends_at = data.get("ends_at", round_obj.ends_at)
    if starts_at is not None and ends_at is not None and ends_at <= starts_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_round_window")

    if "starts_at" in data:
        round_obj.starts_at = data["starts_at"]
    if "ends_at" in data:
        round_obj.ends_at = data["ends_at"]

    db.commit()
    db.refresh(round_obj)

    log_action(
        db,
        category="round",
        action="window_update",
        details={
            "round_number": round_number,
            "starts_at": round_obj.starts_at.isoformat() if round_obj.starts_at else None,
            "ends_at": round_obj.ends_at.isoformat() if round_obj.ends_at else None,
        },
    )
    return {
        "ok": True,
        "round_number": round_number,
        "starts_at": round_obj.starts_at,
        "ends_at": round_obj.ends_at,
    }


@router.post("/rounds/close")
def close_round(
    round_number: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    season = get_or_create_season(db)
    round_obj = get_round_by_number(db, season.id, round_number)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")
    round_obj.is_closed = True
    if round_obj.ends_at is None:
        round_obj.ends_at = func.now()
    db.commit()
    log_action(
        db,
        category="round",
        action="close",
        details={"round_number": round_number},
    )
    return {"ok": True, "round_number": round_number}


@router.post("/notifications/round-reminders/run")
def run_round_reminders(
    dry_run: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    result = run_round_deadline_reminders(db, dry_run=dry_run)
    log_action(
        db,
        category="notifications",
        action="run_round_reminders",
        details=result,
    )
    return {"ok": True, **result}


@router.post("/rounds/{round_number}/recover-lineups")
def recover_round_lineups(
    round_number: int,
    dry_run: bool = Query(default=True),
    recalc_player_points: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = recover_round_lineups_from_market(
            db,
            round_number=round_number,
            apply=not dry_run,
            recalc_player_points=recalc_player_points,
        )
    except ValueError as exc:
        if str(exc) == "round_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found") from exc
        raise
    log_action(
        db,
        category="round_recovery",
        action="recover_lineups",
        details={
            "round_number": round_number,
            "dry_run": dry_run,
            "recalc_player_points": recalc_player_points,
            "summary": {
                "teams_scanned": result.get("teams_scanned"),
                "already_complete": result.get("already_complete"),
                "recovered": result.get("recovered"),
                "unresolved": result.get("unresolved"),
                "market_complete_without_lineup": result.get("market_complete_without_lineup"),
            },
        },
    )
    return result


@router.post("/rounds/open")
def open_round(
    round_number: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    season = get_or_create_season(db)
    round_obj = get_round_by_number(db, season.id, round_number)
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="round_not_found")
    round_obj.is_closed = False
    if round_obj.starts_at is None:
        round_obj.starts_at = func.now()
    db.commit()
    log_action(
        db,
        category="round",
        action="open",
        details={"round_number": round_number},
    )
    return {"ok": True, "round_number": round_number}


@router.get("/leagues", response_model=List[AdminLeagueOut])
def list_leagues(db: Session = Depends(get_db)) -> List[AdminLeagueOut]:
    leagues = (
        db.execute(select(League).order_by(League.created_at.desc()))
        .scalars()
        .all()
    )
    if not leagues:
        return []

    league_ids = [league.id for league in leagues]
    member_rows = (
        db.execute(
            select(LeagueMember, FantasyTeam, User)
            .join(FantasyTeam, FantasyTeam.id == LeagueMember.fantasy_team_id)
            .join(User, User.id == FantasyTeam.user_id)
            .where(LeagueMember.league_id.in_(league_ids))
            .order_by(LeagueMember.joined_at)
        )
        .all()
    )
    member_map: Dict[int, List[AdminLeagueMemberOut]] = {league_id: [] for league_id in league_ids}
    for member, team, user in member_rows:
        member_map[member.league_id].append(
            AdminLeagueMemberOut(
                fantasy_team_id=team.id,
                team_name=team.name,
                user_email=user.email,
                joined_at=member.joined_at,
            )
        )

    return [
        AdminLeagueOut(
            id=league.id,
            code=league.code,
            name=league.name,
            owner_fantasy_team_id=league.owner_fantasy_team_id,
            created_at=league.created_at,
            members=member_map.get(league.id, []),
        )
        for league in leagues
    ]


@router.get("/logs", response_model=List[AdminActionLogOut])
def list_logs(
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[AdminActionLogOut]:
    query = (
        select(ActionLog, User)
        .outerjoin(User, User.id == ActionLog.actor_user_id)
        .order_by(ActionLog.created_at.desc())
        .limit(limit)
    )
    if category:
        query = query.where(ActionLog.category == category)
    rows = db.execute(query).all()
    return [
        AdminActionLogOut(
            id=log.id,
            category=log.category,
            action=log.action,
            created_at=log.created_at,
            actor_user_id=log.actor_user_id,
            actor_email=user.email if user else None,
            league_id=log.league_id,
            fantasy_team_id=log.fantasy_team_id,
            target_user_id=log.target_user_id,
            target_fantasy_team_id=log.target_fantasy_team_id,
            details=log.details,
        )
        for log, user in rows
    ]


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
    user_email = user.email
    _delete_user_data(db, user)
    db.commit()
    log_action(
        db,
        category="admin",
        action="delete_user",
        details={"user_id": user_id, "email": user_email},
    )
    return {"ok": True, "user_id": user_id}
