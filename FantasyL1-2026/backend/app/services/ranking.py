from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FantasyLineup, FantasyLineupSlot, FantasyTeam, PointsRound, Round
from app.schemas.ranking import RankingEntryOut, RankingOut, RankingRoundOut
from app.services.fantasy import get_current_round, get_or_create_season


def build_rankings(db: Session, team_ids: List[int]) -> RankingOut:
    if not team_ids:
        return RankingOut(round_numbers=[], entries=[])

    season = get_or_create_season(db)

    team_rows = (
        db.execute(
            select(FantasyTeam.id, FantasyTeam.name)
            .where(FantasyTeam.season_id == season.id, FantasyTeam.id.in_(team_ids))
        )
        .all()
    )
    team_map = {row[0]: row[1] or "Sin nombre" for row in team_rows}

    round_numbers = (
        db.execute(
            select(Round.round_number)
            .where(Round.season_id == season.id)
            .order_by(Round.round_number)
        )
        .scalars()
        .all()
    )

    points_rows = (
        db.execute(
            select(
                FantasyLineup.fantasy_team_id,
                Round.round_number,
                func.coalesce(func.sum(PointsRound.points), 0).label("points"),
            )
            .join(Round, Round.id == FantasyLineup.round_id)
            .join(FantasyLineupSlot, FantasyLineupSlot.lineup_id == FantasyLineup.id)
            .outerjoin(
                PointsRound,
                (PointsRound.round_id == FantasyLineup.round_id)
                & (PointsRound.player_id == FantasyLineupSlot.player_id)
                & (PointsRound.season_id == season.id),
            )
            .where(
                FantasyLineup.fantasy_team_id.in_(team_ids),
                Round.season_id == season.id,
                FantasyLineupSlot.is_starter.is_(True),
            )
            .group_by(FantasyLineup.fantasy_team_id, Round.round_number)
        )
        .all()
    )

    points_map: Dict[Tuple[int, int], float] = {
        (team_id, round_number): float(points)
        for team_id, round_number, points in points_rows
    }

    captain_map: Dict[int, int | None] = {}
    current_round = get_current_round(db, season.id)
    if current_round:
        lineup_rows = (
            db.execute(
                select(FantasyLineup.fantasy_team_id, FantasyLineup.captain_player_id).where(
                    FantasyLineup.fantasy_team_id.in_(team_ids),
                    FantasyLineup.round_id == current_round.id,
                )
            )
            .all()
        )
        captain_map = {team_id: captain_id for team_id, captain_id in lineup_rows}
    else:
        latest_rounds = (
            db.execute(
                select(
                    FantasyLineup.fantasy_team_id,
                    func.max(FantasyLineup.round_id).label("max_round_id"),
                )
                .where(FantasyLineup.fantasy_team_id.in_(team_ids))
                .group_by(FantasyLineup.fantasy_team_id)
            )
            .all()
        )
        latest_map = {team_id: round_id for team_id, round_id in latest_rounds}
        if latest_map:
            lineup_rows = (
                db.execute(
                    select(FantasyLineup.fantasy_team_id, FantasyLineup.captain_player_id).where(
                        FantasyLineup.fantasy_team_id.in_(latest_map.keys()),
                        FantasyLineup.round_id.in_(latest_map.values()),
                    )
                )
                .all()
            )
            captain_map = {team_id: captain_id for team_id, captain_id in lineup_rows}

    if not round_numbers:
        round_numbers = sorted({round_number for _, round_number, _ in points_rows})

    entries: List[RankingEntryOut] = []
    for team_id in team_ids:
        rounds: List[RankingRoundOut] = []
        cumulative = 0.0
        for round_number in round_numbers:
            points = points_map.get((team_id, round_number), 0.0)
            cumulative += points
            rounds.append(
                RankingRoundOut(
                    round_number=round_number,
                    points=points,
                    cumulative=cumulative,
                )
            )
        entries.append(
            RankingEntryOut(
                fantasy_team_id=team_id,
                team_name=team_map.get(team_id, "Sin nombre"),
                total_points=cumulative,
                captain_player_id=captain_map.get(team_id),
                rounds=rounds,
            )
        )

    entries.sort(key=lambda entry: entry.total_points, reverse=True)
    return RankingOut(round_numbers=round_numbers, entries=entries)
