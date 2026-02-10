from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    FantasyLineup,
    FantasyLineupSlot,
    FantasyTeam,
    FantasyTeamPlayer,
    PlayerCatalog,
    PointsRound,
    PriceMovement,
    Round,
)
from app.schemas.ranking import RankingEntryOut, RankingOut, RankingRoundOut
from app.services.fantasy import get_or_create_season


def build_rankings(db: Session, team_ids: List[int]) -> RankingOut:
    if not team_ids:
        return RankingOut(round_numbers=[], entries=[])

    season = get_or_create_season(db)

    team_rows = (
        db.execute(
            select(FantasyTeam.id, FantasyTeam.name, FantasyTeam.favorite_team_id)
            .where(FantasyTeam.season_id == season.id, FantasyTeam.id.in_(team_ids))
        )
        .all()
    )
    team_map = {row[0]: row[1] or "Sin nombre" for row in team_rows}
    favorite_map = {row[0]: row[2] for row in team_rows}

    round_rows = (
        db.execute(
            select(Round.round_number, Round.is_closed)
            .where(Round.season_id == season.id)
            .order_by(Round.round_number)
        )
        .all()
    )
    pending_round = next((row[0] for row in round_rows if not row[1]), None)
    if pending_round is None:
        round_numbers = [row[0] for row in round_rows]
    else:
        round_numbers = [
            row[0]
            for row in round_rows
            if row[1] or row[0] == pending_round
        ]

    lineup_rows = (
        db.execute(
            select(
                FantasyLineup.id,
                FantasyLineup.fantasy_team_id,
                Round.round_number,
                FantasyLineup.captain_player_id,
                FantasyLineup.vice_captain_player_id,
            )
            .join(Round, Round.id == FantasyLineup.round_id)
            .where(
                FantasyLineup.fantasy_team_id.in_(team_ids),
                Round.season_id == season.id,
                Round.round_number.in_(round_numbers) if round_numbers else True,
            )
        )
        .all()
    )

    lineup_ids = [row[0] for row in lineup_rows]
    slot_rows = []
    if lineup_ids:
        slot_rows = (
            db.execute(
                select(
                    FantasyLineupSlot.lineup_id,
                    FantasyLineupSlot.player_id,
                    func.coalesce(PointsRound.points, 0).label("points"),
                )
                .join(FantasyLineup, FantasyLineupSlot.lineup_id == FantasyLineup.id)
                .join(Round, Round.id == FantasyLineup.round_id)
                .outerjoin(
                    PointsRound,
                    (PointsRound.round_id == FantasyLineup.round_id)
                    & (PointsRound.player_id == FantasyLineupSlot.player_id)
                    & (PointsRound.season_id == season.id),
                )
                .where(
                    FantasyLineupSlot.is_starter.is_(True),
                    FantasyLineupSlot.lineup_id.in_(lineup_ids),
                )
            )
            .all()
        )

    player_ids = {row[1] for row in slot_rows if row[1] is not None}
    injury_map: Dict[int, bool] = {}
    if player_ids:
        injury_rows = (
            db.execute(
                select(PlayerCatalog.player_id, PlayerCatalog.is_injured).where(
                    PlayerCatalog.player_id.in_(player_ids)
                )
            )
            .all()
        )
        injury_map = {player_id: bool(is_injured) for player_id, is_injured in injury_rows}

    lineup_player_points: Dict[int, Dict[int, float]] = {}
    lineup_totals: Dict[int, float] = {}
    for lineup_id, player_id, points in slot_rows:
        if player_id is None:
            continue
        lineup_points = lineup_player_points.setdefault(lineup_id, {})
        lineup_points[player_id] = lineup_points.get(player_id, 0.0) + float(points)
        lineup_totals[lineup_id] = lineup_totals.get(lineup_id, 0.0) + float(points)

    points_map: Dict[Tuple[int, int], float] = {}
    for lineup_id, team_id, round_number, captain_id, vice_id in lineup_rows:
        total = lineup_totals.get(lineup_id, 0.0)
        player_points = lineup_player_points.get(lineup_id, {})

        def eligible(player_id: int | None) -> bool:
            if not player_id:
                return False
            if player_points.get(player_id, 0.0) == 0:
                return False
            if injury_map.get(player_id, False):
                return False
            return True

        if eligible(captain_id):
            total += 2 * player_points.get(captain_id, 0.0)
        elif eligible(vice_id):
            total += 2 * player_points.get(vice_id, 0.0)

        points_map[(team_id, round_number)] = total

    delta_rows = (
        db.execute(
            select(
                FantasyLineup.fantasy_team_id,
                Round.round_number,
                func.coalesce(func.sum(PriceMovement.delta), 0).label("delta"),
            )
            .join(Round, Round.id == FantasyLineup.round_id)
            .join(FantasyLineupSlot, FantasyLineupSlot.lineup_id == FantasyLineup.id)
            .outerjoin(
                PriceMovement,
                (PriceMovement.round_id == FantasyLineup.round_id)
                & (PriceMovement.player_id == FantasyLineupSlot.player_id)
                & (PriceMovement.season_id == season.id),
            )
            .where(
                FantasyLineup.fantasy_team_id.in_(team_ids),
                Round.season_id == season.id,
                Round.round_number.in_(round_numbers) if round_numbers else True,
            )
            .group_by(FantasyLineup.fantasy_team_id, Round.round_number)
        )
        .all()
    )

    # points_map populated above
    delta_map: Dict[Tuple[int, int], float] = {
        (team_id, round_number): float(delta)
        for team_id, round_number, delta in delta_rows
    }

    def _round_tenth(value: float | Decimal) -> float:
        return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

    def _sort_key_by_bought_round(
        bought_round_id: int | None,
        player_id: int,
    ) -> tuple[int, int, int]:
        return (
            1 if bought_round_id is None else 0,
            -(bought_round_id or 0),
            player_id,
        )

    # For pending round, budget delta must match Team tab logic:
    # previous closed round movements over current 15-player squad.
    pending_delta_map: Dict[int, float] = {}
    closed_rounds = [row[0] for row in round_rows if row[1]]
    previous_closed_round_number = (
        max((r for r in closed_rounds if pending_round is None or r < pending_round), default=None)
        if pending_round is not None
        else None
    )
    if pending_round is not None and previous_closed_round_number is not None:
        previous_closed_round_id = db.execute(
            select(Round.id).where(
                Round.season_id == season.id,
                Round.round_number == previous_closed_round_number,
            )
        ).scalar_one_or_none()
        if previous_closed_round_id is not None:
            # Prefer the previous closed lineup to freeze delta; fallback to squad.
            lineup_rows = (
                db.execute(
                    select(FantasyLineup.id, FantasyLineup.fantasy_team_id)
                    .where(
                        FantasyLineup.fantasy_team_id.in_(team_ids),
                        FantasyLineup.round_id == previous_closed_round_id,
                    )
                ).all()
            )
            lineup_ids = [row[0] for row in lineup_rows]
            slots_map: Dict[int, List[int]] = {}
            if lineup_ids:
                slot_rows = (
                    db.execute(
                        select(FantasyLineupSlot.lineup_id, FantasyLineupSlot.player_id)
                        .where(
                            FantasyLineupSlot.lineup_id.in_(lineup_ids),
                            FantasyLineupSlot.player_id.is_not(None),
                        )
                    ).all()
                )
                lineup_to_team = {lineup_id: team_id for lineup_id, team_id in lineup_rows}
                for lineup_id, player_id in slot_rows:
                    if player_id is None:
                        continue
                    team_id = lineup_to_team.get(lineup_id)
                    if team_id is None:
                        continue
                    slots_map.setdefault(team_id, []).append(int(player_id))

            players_by_team: Dict[int, list[tuple[int, int | None]]] = {}
            if len(slots_map) < len(team_ids):
                team_player_rows = db.execute(
                    select(
                        FantasyTeamPlayer.fantasy_team_id,
                        FantasyTeamPlayer.player_id,
                        FantasyTeamPlayer.bought_round_id,
                    )
                    .join(
                        PlayerCatalog,
                        PlayerCatalog.player_id == FantasyTeamPlayer.player_id,
                    )
                    .where(FantasyTeamPlayer.fantasy_team_id.in_(team_ids))
                ).all()
                for team_id_row, player_id, bought_round_id in team_player_rows:
                    players_by_team.setdefault(team_id_row, []).append((player_id, bought_round_id))

            canonical_player_ids_by_team: Dict[int, List[int]] = {}
            all_player_ids: set[int] = set()
            for team_id in team_ids:
                if team_id in slots_map and slots_map[team_id]:
                    player_ids = slots_map[team_id][:15]
                else:
                    rows = players_by_team.get(team_id, [])
                    rows_sorted = sorted(
                        rows,
                        key=lambda row: _sort_key_by_bought_round(row[1], row[0]),
                    )[:15]
                    player_ids = [player_id for player_id, _ in rows_sorted]
                canonical_player_ids_by_team[team_id] = player_ids
                all_player_ids.update(player_ids)

            movement_map: Dict[int, float] = {}
            if all_player_ids:
                movement_rows = db.execute(
                    select(PriceMovement.player_id, PriceMovement.delta).where(
                        PriceMovement.season_id == season.id,
                        PriceMovement.round_id == previous_closed_round_id,
                        PriceMovement.player_id.in_(all_player_ids),
                    )
                ).all()
                movement_map = {
                    player_id: float(delta or 0)
                    for player_id, delta in movement_rows
                }

            for team_id in team_ids:
                # Keep pending-round delta aligned with Team tab behavior:
                # sum movement once per player id in the canonical 15-player squad.
                unique_player_ids = set(canonical_player_ids_by_team.get(team_id, []))
                total_delta = sum(
                    movement_map.get(player_id, 0.0)
                    for player_id in unique_player_ids
                )
                pending_delta_map[team_id] = _round_tenth(total_delta)

    captain_map: Dict[int, int | None] = {}
    target_round = max(closed_rounds) if closed_rounds else pending_round
    if target_round is not None:
        lineup_rows = (
            db.execute(
                select(FantasyLineup.fantasy_team_id, FantasyLineup.captain_player_id)
                .join(Round, Round.id == FantasyLineup.round_id)
                .where(
                    FantasyLineup.fantasy_team_id.in_(team_ids),
                    Round.round_number == target_round,
                    Round.season_id == season.id,
                )
            )
            .all()
        )
        captain_map = {team_id: captain_id for team_id, captain_id in lineup_rows}

    if not round_numbers:
        round_numbers = sorted({round_number for _, round_number in points_map.keys()})

    entries: List[RankingEntryOut] = []
    for team_id in team_ids:
        rounds: List[RankingRoundOut] = []
        cumulative = 0.0
        for round_number in round_numbers:
            points = points_map.get((team_id, round_number), 0.0)
            if pending_round is not None and round_number == pending_round:
                delta = pending_delta_map.get(team_id, 0.0)
            else:
                delta = delta_map.get((team_id, round_number), 0.0)
            cumulative += points
            rounds.append(
                RankingRoundOut(
                    round_number=round_number,
                    points=points,
                    cumulative=cumulative,
                    price_delta=delta,
                )
            )
        entries.append(
            RankingEntryOut(
                fantasy_team_id=team_id,
                team_name=team_map.get(team_id, "Sin nombre"),
                total_points=cumulative,
                captain_player_id=captain_map.get(team_id),
                favorite_team_id=favorite_map.get(team_id),
                rounds=rounds,
            )
        )

    def _sort_key(entry: RankingEntryOut):
        valid_rounds = sum(1 for round_item in entry.rounds if round_item.points > 0)
        latest_delta = entry.rounds[-1].price_delta if entry.rounds else 0.0
        return (
            -entry.total_points,
            -valid_rounds,
            -latest_delta,
        )

    entries.sort(key=_sort_key)
    return RankingOut(round_numbers=round_numbers, entries=entries)
