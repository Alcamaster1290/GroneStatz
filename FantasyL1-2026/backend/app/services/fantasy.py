from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    FantasyLineup,
    FantasyLineupSlot,
    FantasyTeam,
    FantasyTeamPlayer,
    PlayerCatalog,
    Round,
    Season,
)

settings = get_settings()

DEFAULT_SLOTS = [
    (0, True, "G"),
    (1, True, "D"),
    (2, True, "D"),
    (3, True, "D"),
    (4, True, "D"),
    (5, True, "M"),
    (6, True, "M"),
    (7, True, "M"),
    (8, True, "M"),
    (9, True, "F"),
    (10, True, "F"),
    (11, False, "G"),
    (12, False, "D"),
    (13, False, "M"),
    (14, False, "F"),
]


def get_or_create_season(db: Session) -> Season:
    season = db.execute(select(Season).where(Season.year == settings.SEASON_YEAR)).scalar_one_or_none()
    if season:
        return season
    season = Season(year=settings.SEASON_YEAR, name=settings.SEASON_NAME)
    db.add(season)
    db.commit()
    db.refresh(season)
    return season


def get_round_by_number(db: Session, season_id: int, round_number: int) -> Optional[Round]:
    return db.execute(
        select(Round).where(Round.season_id == season_id, Round.round_number == round_number)
    ).scalar_one_or_none()


def get_current_round(db: Session, season_id: int) -> Optional[Round]:
    round_obj = (
        db.execute(
            select(Round)
            .where(Round.season_id == season_id, Round.is_closed.is_(False))
            .order_by(Round.round_number)
            .limit(1)
        )
        .scalars()
        .first()
    )
    return round_obj


def get_latest_round(db: Session, season_id: int) -> Optional[Round]:
    return (
        db.execute(
            select(Round)
            .where(Round.season_id == season_id)
            .order_by(Round.round_number.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def get_next_open_round(
    db: Session, season_id: int, after_round_number: int
) -> Optional[Round]:
    return (
        db.execute(
            select(Round)
            .where(
                Round.season_id == season_id,
                Round.is_closed.is_(False),
                Round.round_number > after_round_number,
            )
            .order_by(Round.round_number)
            .limit(1)
        )
        .scalars()
        .first()
    )


def ensure_round(db: Session, season_id: int, round_number: int) -> Round:
    round_obj = get_round_by_number(db, season_id, round_number)
    if round_obj:
        return round_obj
    round_obj = Round(season_id=season_id, round_number=round_number, is_closed=False)
    db.add(round_obj)
    db.commit()
    db.refresh(round_obj)
    return round_obj


def get_or_create_fantasy_team(
    db: Session,
    user_id: int,
    season_id: int,
    name: Optional[str] = None,
) -> FantasyTeam:
    team = db.execute(
        select(FantasyTeam).where(FantasyTeam.user_id == user_id, FantasyTeam.season_id == season_id)
    ).scalar_one_or_none()
    if team:
        if name and team.name != name:
            team.name = name
            db.commit()
            db.refresh(team)
        return team
    team = FantasyTeam(user_id=user_id, season_id=season_id, name=name)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def get_squad_players(db: Session, fantasy_team_id: int) -> List[PlayerCatalog]:
    return (
        db.execute(
            select(PlayerCatalog)
            .join(FantasyTeamPlayer, FantasyTeamPlayer.player_id == PlayerCatalog.player_id)
            .where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id)
        )
        .scalars()
        .all()
    )


def get_budget_used(db: Session, fantasy_team_id: int) -> float:
    rows = db.execute(
        select(FantasyTeamPlayer.bought_price)
        .where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id)
    ).scalars()
    return float(sum(rows))


def get_club_counts(db: Session, fantasy_team_id: int) -> Dict[int, int]:
    rows = db.execute(
        select(PlayerCatalog.team_id)
        .join(FantasyTeamPlayer, FantasyTeamPlayer.player_id == PlayerCatalog.player_id)
        .where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id)
    ).scalars()
    counts: Dict[int, int] = {}
    for team_id in rows:
        counts[team_id] = counts.get(team_id, 0) + 1
    return counts


def replace_squad(
    db: Session,
    fantasy_team_id: int,
    player_ids: List[int],
    bought_round_id: Optional[int] = None,
) -> None:
    players = (
        db.execute(select(PlayerCatalog).where(PlayerCatalog.player_id.in_(player_ids)))
        .scalars()
        .all()
    )
    price_map = {p.player_id: float(p.price_current) for p in players}

    db.execute(delete(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id))
    db.flush()

    for player_id in player_ids:
        db.add(
            FantasyTeamPlayer(
                fantasy_team_id=fantasy_team_id,
                player_id=player_id,
                bought_price=price_map[player_id],
                bought_round_id=bought_round_id,
                is_active=True,
            )
        )
    db.commit()


def ensure_lineup(db: Session, fantasy_team_id: int, round_id: int) -> FantasyLineup:
    lineup = db.execute(
        select(FantasyLineup).where(
            FantasyLineup.fantasy_team_id == fantasy_team_id,
            FantasyLineup.round_id == round_id,
        )
    ).scalar_one_or_none()
    if lineup:
        return lineup
    lineup = FantasyLineup(fantasy_team_id=fantasy_team_id, round_id=round_id, formation_code="DEFAULT")
    db.add(lineup)
    db.flush()

    for slot_index, is_starter, role in DEFAULT_SLOTS:
        db.add(
            FantasyLineupSlot(
                lineup_id=lineup.id,
                slot_index=slot_index,
                is_starter=is_starter,
                role=role,
                player_id=None,
            )
        )

    db.commit()
    db.refresh(lineup)
    return lineup


def upsert_lineup_slots(db: Session, lineup_id: int, slots: list) -> None:
    db.execute(delete(FantasyLineupSlot).where(FantasyLineupSlot.lineup_id == lineup_id))
    db.flush()
    for slot in slots:
        db.add(
            FantasyLineupSlot(
                lineup_id=lineup_id,
                slot_index=slot.slot_index,
                is_starter=slot.is_starter,
                role=slot.role,
                player_id=slot.player_id,
            )
        )
    db.commit()
