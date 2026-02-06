from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    FantasyLineup,
    FantasyLineupSlot,
    FantasyTeam,
    FantasyTeamPlayer,
    FantasyTransfer,
    PlayerCatalog,
    PointsRound,
    Round,
)
from app.services.fantasy import DEFAULT_SLOTS, ensure_lineup, get_or_create_season, get_round_by_number
from app.services.scoring import recalc_round_points


@dataclass
class RecoveryTeamResult:
    fantasy_team_id: int
    user_id: int
    team_name: str | None
    status: str
    detail: str | None = None
    recovered_from_round: int | None = None

    def as_dict(self) -> dict:
        return {
            "fantasy_team_id": self.fantasy_team_id,
            "user_id": self.user_id,
            "team_name": self.team_name,
            "status": self.status,
            "detail": self.detail,
            "recovered_from_round": self.recovered_from_round,
        }


def _normalize_role(role: str | None) -> str:
    text = (role or "").strip().upper()
    if text.startswith("G"):
        return "G"
    if text.startswith("D"):
        return "D"
    if text.startswith("M"):
        return "M"
    if text.startswith("F"):
        return "F"
    return ""


def _load_slots(db: Session, lineup_id: int) -> list[FantasyLineupSlot]:
    return (
        db.execute(
            select(FantasyLineupSlot)
            .where(FantasyLineupSlot.lineup_id == lineup_id)
            .order_by(FantasyLineupSlot.slot_index)
        )
        .scalars()
        .all()
    )


def _is_complete_lineup(slots: list[FantasyLineupSlot]) -> bool:
    if len(slots) != 15:
        return False
    starters = [slot for slot in slots if slot.is_starter]
    if len(starters) != 11:
        return False
    player_ids = [slot.player_id for slot in slots if slot.player_id is not None]
    if len(player_ids) != 15:
        return False
    return len(set(player_ids)) == 15


def _complete_market_count(db: Session, fantasy_team_id: int) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(FantasyTeamPlayer)
            .where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id)
        ).scalar()
        or 0
    )


def _round_market_player_ids(
    db: Session, *, fantasy_team_id: int, target_round_number: int
) -> set[int]:
    current_ids = set(
        db.execute(
            select(FantasyTeamPlayer.player_id).where(
                FantasyTeamPlayer.fantasy_team_id == fantasy_team_id
            )
        )
        .scalars()
        .all()
    )
    if not current_ids:
        return set()

    transfer_rows = (
        db.execute(
            select(
                FantasyTransfer.id,
                FantasyTransfer.out_player_id,
                FantasyTransfer.in_player_id,
                FantasyTransfer.created_at,
                Round.round_number,
            )
            .join(Round, Round.id == FantasyTransfer.round_id)
            .where(FantasyTransfer.fantasy_team_id == fantasy_team_id)
            .order_by(
                Round.round_number.desc(),
                FantasyTransfer.created_at.desc(),
                FantasyTransfer.id.desc(),
            )
        )
        .all()
    )

    for transfer_id, out_player_id, in_player_id, created_at, round_number in transfer_rows:
        _ = transfer_id, created_at
        if int(round_number) <= target_round_number:
            continue
        if in_player_id in current_ids:
            current_ids.remove(in_player_id)
        current_ids.add(out_player_id)
    return current_ids


def _choose_next_player(
    available_ids: set[int],
    *,
    role: str | None,
    position_map: Dict[int, str],
    points_map: Dict[int, float],
) -> int | None:
    if not available_ids:
        return None
    role_key = _normalize_role(role)
    if role_key:
        role_candidates = [
            player_id
            for player_id in available_ids
            if _normalize_role(position_map.get(player_id)) == role_key
        ]
    else:
        role_candidates = []
    candidates = role_candidates if role_candidates else list(available_ids)
    candidates.sort(key=lambda player_id: (-float(points_map.get(player_id, 0.0)), player_id))
    return candidates[0] if candidates else None


def _closest_complete_lineup(
    db: Session,
    *,
    season_id: int,
    fantasy_team_id: int,
    target_round_number: int,
) -> tuple[FantasyLineup, list[FantasyLineupSlot], int] | None:
    lineup_rows = (
        db.execute(
            select(FantasyLineup, Round.round_number)
            .join(Round, Round.id == FantasyLineup.round_id)
            .where(
                FantasyLineup.fantasy_team_id == fantasy_team_id,
                Round.season_id == season_id,
            )
            .order_by(
                func.abs(Round.round_number - target_round_number),
                Round.round_number,
                FantasyLineup.id,
            )
        )
        .all()
    )
    for lineup, round_number in lineup_rows:
        slots = _load_slots(db, lineup.id)
        if _is_complete_lineup(slots):
            return lineup, slots, int(round_number)
    return None


def recover_round_lineups_from_market(
    db: Session,
    *,
    round_number: int,
    apply: bool = False,
    recalc_player_points: bool = True,
) -> dict:
    season = get_or_create_season(db)
    round_obj = get_round_by_number(db, season.id, round_number)
    if not round_obj:
        raise ValueError("round_not_found")

    teams = (
        db.execute(
            select(FantasyTeam)
            .where(FantasyTeam.season_id == season.id)
            .order_by(FantasyTeam.id)
        )
        .scalars()
        .all()
    )

    results: list[RecoveryTeamResult] = []
    recovered_count = 0
    unresolved_count = 0
    market_complete_without_lineup = 0
    already_complete = 0
    lineup_market_mismatch = 0

    for team in teams:
        round_lineup = (
            db.execute(
                select(FantasyLineup).where(
                    FantasyLineup.fantasy_team_id == team.id,
                    FantasyLineup.round_id == round_obj.id,
                )
            )
            .scalars()
            .first()
        )
        existing_slots = _load_slots(db, round_lineup.id) if round_lineup else []

        market_ids = _round_market_player_ids(
            db, fantasy_team_id=team.id, target_round_number=round_number
        )

        lineup_player_ids = {
            int(slot.player_id)
            for slot in existing_slots
            if slot.player_id is not None
        }
        lineup_is_complete = bool(round_lineup and _is_complete_lineup(existing_slots))
        lineup_matches_market = (
            lineup_is_complete
            and len(market_ids) == 15
            and lineup_player_ids == market_ids
        )

        if lineup_matches_market:
            already_complete += 1
            results.append(
                RecoveryTeamResult(
                    fantasy_team_id=team.id,
                    user_id=team.user_id,
                    team_name=team.name,
                    status="lineup_ok",
                    recovered_from_round=round_number,
                )
            )
            continue

        if lineup_is_complete and lineup_player_ids != market_ids:
            lineup_market_mismatch += 1

        if len(market_ids) < 15:
            unresolved_count += 1
            results.append(
                RecoveryTeamResult(
                    fantasy_team_id=team.id,
                    user_id=team.user_id,
                    team_name=team.name,
                    status="market_incomplete",
                    detail=f"market_players={len(market_ids)}",
                )
            )
            continue

        player_rows = (
            db.execute(
                select(PlayerCatalog.player_id, PlayerCatalog.position).where(
                    PlayerCatalog.player_id.in_(market_ids)
                )
            )
            .all()
        )
        position_map = {int(player_id): str(position or "") for player_id, position in player_rows}
        if len(position_map) < 15:
            missing = sorted(market_ids.difference(position_map.keys()))
            unresolved_count += 1
            results.append(
                RecoveryTeamResult(
                    fantasy_team_id=team.id,
                    user_id=team.user_id,
                    team_name=team.name,
                    status="players_missing",
                    detail="players_not_found:" + ",".join(str(player_id) for player_id in missing),
                )
            )
            continue

        points_rows = (
            db.execute(
                select(PointsRound.player_id, PointsRound.points).where(
                    PointsRound.season_id == season.id,
                    PointsRound.round_id == round_obj.id,
                    PointsRound.player_id.in_(market_ids),
                )
            )
            .all()
        )
        round_points_map = {int(player_id): float(points or 0) for player_id, points in points_rows}

        source_round = None
        source_slots: list[FantasyLineupSlot] = []
        source_captain: int | None = None
        source_vice: int | None = None

        has_existing_players = any(slot.player_id is not None for slot in existing_slots)
        if has_existing_players:
            source_slots = existing_slots
            source_round = round_number
            if round_lineup:
                source_captain = round_lineup.captain_player_id
                source_vice = round_lineup.vice_captain_player_id
        else:
            fallback = _closest_complete_lineup(
                db,
                season_id=season.id,
                fantasy_team_id=team.id,
                target_round_number=round_number,
            )
            if fallback:
                source_lineup, source_slots, source_round = fallback
                source_captain = source_lineup.captain_player_id
                source_vice = source_lineup.vice_captain_player_id

        if not source_slots:
            complete_market_count = _complete_market_count(db, team.id)
            if complete_market_count >= 15:
                market_complete_without_lineup += 1
                status_code = "market_complete_without_lineup"
                detail = "Mercado completo, sin equipo guardado"
            else:
                status_code = "lineup_not_found"
                detail = "lineup_not_found"
            unresolved_count += 1
            results.append(
                RecoveryTeamResult(
                    fantasy_team_id=team.id,
                    user_id=team.user_id,
                    team_name=team.name,
                    status=status_code,
                    detail=detail,
                )
            )
            continue

        source_by_slot_index = {slot.slot_index: slot for slot in source_slots}
        template_slots = source_slots
        if len(template_slots) != 15:
            template_slots = [
                FantasyLineupSlot(
                    lineup_id=0,
                    slot_index=slot_index,
                    is_starter=is_starter,
                    role=role,
                    player_id=None,
                )
                for slot_index, is_starter, role in DEFAULT_SLOTS
            ]
        template_slots = sorted(template_slots, key=lambda slot: slot.slot_index)

        assigned_by_slot: dict[int, int] = {}
        used_player_ids: set[int] = set()
        for slot in template_slots:
            source_slot = source_by_slot_index.get(slot.slot_index)
            source_player_id = source_slot.player_id if source_slot else None
            if source_player_id and source_player_id in market_ids and source_player_id not in used_player_ids:
                assigned_by_slot[slot.slot_index] = source_player_id
                used_player_ids.add(source_player_id)

        available_ids = set(market_ids.difference(used_player_ids))
        for slot in template_slots:
            if slot.slot_index in assigned_by_slot:
                continue
            selected_id = _choose_next_player(
                available_ids,
                role=slot.role,
                position_map=position_map,
                points_map=round_points_map,
            )
            if selected_id is None:
                continue
            assigned_by_slot[slot.slot_index] = selected_id
            available_ids.remove(selected_id)

        if len(assigned_by_slot) != 15:
            unresolved_count += 1
            results.append(
                RecoveryTeamResult(
                    fantasy_team_id=team.id,
                    user_id=team.user_id,
                    team_name=team.name,
                    status="lineup_unrecoverable",
                    detail=f"assigned={len(assigned_by_slot)}",
                    recovered_from_round=source_round,
                )
            )
            continue

        starters = [slot for slot in template_slots if slot.is_starter]
        starter_player_ids = [
            assigned_by_slot.get(slot.slot_index)
            for slot in starters
            if assigned_by_slot.get(slot.slot_index) is not None
        ]
        starter_player_ids = [int(player_id) for player_id in starter_player_ids]

        def _choose_captain(candidates: list[int], preferred: int | None) -> int | None:
            if preferred and preferred in candidates:
                return preferred
            if not candidates:
                return None
            ordered = sorted(
                candidates,
                key=lambda player_id: (-float(round_points_map.get(player_id, 0.0)), player_id),
            )
            return ordered[0]

        captain_id = _choose_captain(starter_player_ids, source_captain)
        vice_candidates = [player_id for player_id in starter_player_ids if player_id != captain_id]
        vice_id = _choose_captain(vice_candidates, source_vice)

        if apply:
            if round_lineup is None:
                round_lineup = ensure_lineup(db, team.id, round_obj.id)
            db.execute(
                delete(FantasyLineupSlot).where(FantasyLineupSlot.lineup_id == round_lineup.id)
            )
            for slot in template_slots:
                player_id = assigned_by_slot[slot.slot_index]
                db.add(
                    FantasyLineupSlot(
                        lineup_id=round_lineup.id,
                        slot_index=slot.slot_index,
                        is_starter=bool(slot.is_starter),
                        role=slot.role,
                        player_id=player_id,
                    )
                )
            round_lineup.captain_player_id = captain_id
            round_lineup.vice_captain_player_id = vice_id
            db.commit()

        recovered_count += 1
        results.append(
            RecoveryTeamResult(
                fantasy_team_id=team.id,
                user_id=team.user_id,
                team_name=team.name,
                status="lineup_recovered",
                detail="recovered_from_market_and_nearest_lineup",
                recovered_from_round=source_round,
            )
        )

    points_recalc = None
    if recalc_player_points:
        if apply:
            points_recalc = recalc_round_points(
                db,
                round_number=round_number,
                apply_prices=False,
                write_price_history=False,
            )
        else:
            points_recalc = {
                "ok": True,
                "round_number": round_number,
                "dry_run": True,
                "note": "player_points_recalc_skipped_in_dry_run",
            }

    summary = {
        "ok": True,
        "round_number": round_number,
        "apply": bool(apply),
        "teams_scanned": len(teams),
        "already_complete": already_complete,
        "recovered": recovered_count,
        "unresolved": unresolved_count,
        "market_complete_without_lineup": market_complete_without_lineup,
        "lineup_market_mismatch": lineup_market_mismatch,
        "points_recalc": points_recalc,
        "results": [item.as_dict() for item in results],
        "executed_at": datetime.utcnow().isoformat() + "Z",
    }
    return summary
