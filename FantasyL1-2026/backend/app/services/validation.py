from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FantasyTeamPlayer, FantasyTransfer, PlayerCatalog

POSITIONS = {"G", "D", "M", "F"}


class ValidationError(Exception):
    def __init__(self, errors: List[str]):
        super().__init__("validation failed")
        self.errors = errors


def validate_squad(db: Session, player_ids: Iterable[int], budget_cap: float = 100.0) -> List[str]:
    ids = list(player_ids)
    errors: List[str] = []

    if len(ids) != 15:
        errors.append("squad_must_have_15_players")

    if len(set(ids)) != len(ids):
        errors.append("squad_has_duplicate_players")

    players = (
        db.execute(select(PlayerCatalog).where(PlayerCatalog.player_id.in_(ids))).scalars().all()
    )
    found_ids = {p.player_id for p in players}
    missing = sorted(set(ids) - found_ids)
    if missing:
        errors.append("players_not_found: " + ",".join(str(pid) for pid in missing))
        return errors

    positions = Counter(p.position for p in players)
    if positions.get("G", 0) != 2:
        errors.append("squad_must_have_2_goalkeepers")

    d_count = positions.get("D", 0)
    m_count = positions.get("M", 0)
    f_count = positions.get("F", 0)

    if d_count < 3 or d_count > 6:
        errors.append("squad_defenders_out_of_range")
    if m_count < 3 or m_count > 6:
        errors.append("squad_midfielders_out_of_range")
    if f_count < 1 or f_count > 3:
        errors.append("squad_forwards_out_of_range")

    invalid_positions = [p.player_id for p in players if p.position not in POSITIONS]
    if invalid_positions:
        errors.append("players_with_invalid_position")

    team_counts = Counter(p.team_id for p in players)
    if any(count > 3 for count in team_counts.values()):
        errors.append("max_3_players_per_team")

    def _round_price(value: float | Decimal) -> Decimal:
        try:
            raw = Decimal(str(value))
        except Exception:
            raw = Decimal("0")
        return raw.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    total_price = sum(_round_price(p.price_current) for p in players)
    cap_value = _round_price(budget_cap)
    if total_price - cap_value > Decimal("0.0001"):
        errors.append("budget_exceeded")

    return errors


def validate_lineup(
    db: Session,
    fantasy_team_id: int,
    slots: list,
) -> List[str]:
    errors: List[str] = []

    if len(slots) != 15:
        errors.append("lineup_must_have_15_slots")
        return errors

    slot_indexes = [s.slot_index for s in slots]
    if len(set(slot_indexes)) != 15:
        errors.append("lineup_slot_index_duplicate")

    starters = [s for s in slots if s.is_starter]
    bench = [s for s in slots if not s.is_starter]
    if len(starters) != 11 or len(bench) != 4:
        errors.append("lineup_requires_11_starters_and_4_bench")

    if any(s.player_id is None for s in slots):
        errors.append("lineup_has_empty_slots")

    player_ids = [s.player_id for s in slots if s.player_id is not None]
    if len(set(player_ids)) != len(player_ids):
        errors.append("lineup_has_duplicate_players")

    squad_ids = (
        db.execute(
            select(FantasyTeamPlayer.player_id).where(
                FantasyTeamPlayer.fantasy_team_id == fantasy_team_id
            )
        )
        .scalars()
        .all()
    )
    squad_set = set(squad_ids)
    missing = [pid for pid in player_ids if pid not in squad_set]
    if missing:
        errors.append("lineup_players_not_in_squad")

    players = (
        db.execute(select(PlayerCatalog).where(PlayerCatalog.player_id.in_(player_ids))).scalars().all()
    )
    by_id = {p.player_id: p for p in players}

    starter_positions = Counter()
    for slot in starters:
        if slot.player_id is None:
            continue
        player = by_id.get(slot.player_id)
        if not player:
            continue
        starter_positions[player.position] += 1

    if starter_positions.get("G", 0) < 1:
        errors.append("lineup_starters_need_goalkeeper")
    if starter_positions.get("G", 0) > 1:
        errors.append("lineup_starters_max_1_goalkeeper")
    if starter_positions.get("D", 0) < 1:
        errors.append("lineup_starters_need_defender")
    if starter_positions.get("M", 0) < 1:
        errors.append("lineup_starters_need_midfielder")
    if starter_positions.get("F", 0) < 1:
        errors.append("lineup_starters_need_forward")
    if starter_positions.get("F", 0) > 4:
        errors.append("lineup_starters_max_4_forwards")

    return errors


def validate_transfer(
    db: Session,
    fantasy_team_id: int,
    round_id: int,
    out_player_id: int,
    in_player_id: int,
    budget_cap: float = 100.0,
) -> List[str]:
    errors: List[str] = []

    existing_count = (
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
    total_fee = max(0, existing_count) * 0.5

    squad_ids = (
        db.execute(
            select(FantasyTeamPlayer.player_id).where(
                FantasyTeamPlayer.fantasy_team_id == fantasy_team_id
            )
        )
        .scalars()
        .all()
    )

    if out_player_id not in squad_ids:
        errors.append("out_player_not_in_squad")
    if in_player_id in squad_ids:
        errors.append("in_player_already_in_squad")

    if errors:
        return errors

    new_ids = [pid for pid in squad_ids if pid != out_player_id] + [in_player_id]
    effective_cap = float(budget_cap) - float(total_fee)
    errors.extend(validate_squad(db, new_ids, budget_cap=effective_cap))

    return errors
