from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    FantasyTeam,
    FantasyTeamPlayer,
    Fixture,
    PlayerCatalog,
    PlayerMatchStat,
    PlayerRoundStat,
    PointsRound,
    Round,
    Team,
)
from app.schemas.catalog import (
    FixtureOut,
    MatchPlayerStatOut,
    PlayerCatalogOut,
    PlayerMatchOut,
    PlayerStatsOut,
    RoundOut,
    TeamOut,
)
from app.services.fantasy import get_current_round, get_or_create_season
from app.services.scoring import calc_match_points

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/players", response_model=List[PlayerCatalogOut])
def list_players(
    position: Optional[str] = None,
    team_id: Optional[int] = None,
    q: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[PlayerCatalogOut]:
    season = get_or_create_season(db)
    round_obj = get_current_round(db, season.id)
    stats_subq = (
        select(
            PlayerMatchStat.player_id.label("player_id"),
            func.coalesce(func.sum(PlayerMatchStat.goals), 0).label("goals"),
            func.coalesce(func.sum(PlayerMatchStat.assists), 0).label("assists"),
            func.coalesce(func.sum(PlayerMatchStat.minutesplayed), 0).label("minutesplayed"),
            func.coalesce(func.sum(PlayerMatchStat.saves), 0).label("saves"),
            func.coalesce(func.sum(PlayerMatchStat.fouls), 0).label("fouls"),
        )
        .where(PlayerMatchStat.season_id == season.id)
        .group_by(PlayerMatchStat.player_id)
        .subquery()
    )
    points_total_subq = (
        select(
            PointsRound.player_id.label("player_id"),
            func.coalesce(func.sum(PointsRound.points), 0).label("points_total"),
        )
        .where(PointsRound.season_id == season.id)
        .group_by(PointsRound.player_id)
        .subquery()
    )
    totals_stats_subq = (
        select(
            PlayerRoundStat.player_id.label("player_id"),
            func.coalesce(func.sum(PlayerRoundStat.clean_sheets), 0).label("clean_sheets_total"),
            func.coalesce(func.sum(PlayerRoundStat.goals_conceded), 0).label("goals_conceded_total"),
        )
        .where(PlayerRoundStat.season_id == season.id)
        .group_by(PlayerRoundStat.player_id)
        .subquery()
    )

    query = (
        select(
            PlayerCatalog,
            stats_subq.c.goals,
            stats_subq.c.assists,
            stats_subq.c.minutesplayed,
            stats_subq.c.saves,
            stats_subq.c.fouls,
            func.coalesce(points_total_subq.c.points_total, 0).label("points_total"),
            func.coalesce(totals_stats_subq.c.clean_sheets_total, 0).label("clean_sheets_total"),
            func.coalesce(totals_stats_subq.c.goals_conceded_total, 0).label("goals_conceded_total"),
        )
        .outerjoin(stats_subq, PlayerCatalog.player_id == stats_subq.c.player_id)
        .outerjoin(points_total_subq, PlayerCatalog.player_id == points_total_subq.c.player_id)
        .outerjoin(totals_stats_subq, PlayerCatalog.player_id == totals_stats_subq.c.player_id)
    )
    if position:
        query = query.where(PlayerCatalog.position == position)
    if team_id:
        query = query.where(PlayerCatalog.team_id == team_id)
    if q:
        query = query.where(PlayerCatalog.name.ilike(f"%{q}%"))
    if max_price is not None:
        query = query.where(PlayerCatalog.price_current <= max_price)
    if min_price is not None:
        query = query.where(PlayerCatalog.price_current >= min_price)

    query = query.order_by(PlayerCatalog.name).limit(limit).offset(offset)
    rows = db.execute(query).all()
    points_map = {}
    if rows and round_obj:
        player_ids = [row[0].player_id for row in rows]
        points_rows = db.execute(
            select(PointsRound.player_id, PointsRound.points).where(
                PointsRound.season_id == season.id,
                PointsRound.round_id == round_obj.id,
                PointsRound.player_id.in_(player_ids),
            )
        ).all()
        points_map = {player_id: float(points) for player_id, points in points_rows}
    results: List[PlayerCatalogOut] = []
    for row in rows:
        player = row[0]
        goals = row[1] if row[1] is not None else player.goals
        assists = row[2] if row[2] is not None else player.assists
        minutesplayed = row[3] if row[3] is not None else player.minutesplayed
        saves = row[4] if row[4] is not None else player.saves
        fouls = row[5] if row[5] is not None else player.fouls

        points_total = float(row[6] or 0)
        clean_sheets_total = int(row[7] or 0)
        goals_conceded_total = int(row[8] or 0)
        results.append(
            PlayerCatalogOut(
                player_id=player.player_id,
                name=player.name,
                short_name=player.short_name,
                position=player.position,
                team_id=player.team_id,
                price_current=float(player.price_current),
                is_injured=bool(player.is_injured),
                minutesplayed=int(minutesplayed or 0),
                matches_played=player.matches_played,
                goals=int(goals or 0),
                assists=int(assists or 0),
                saves=int(saves or 0),
                fouls=int(fouls or 0),
                points_round=points_map.get(player.player_id),
                points_total=points_total,
                clean_sheets=clean_sheets_total,
                goals_conceded=goals_conceded_total,
                updated_at=player.updated_at,
            )
        )

    return results


@router.get("/teams", response_model=List[TeamOut])
def list_teams(db: Session = Depends(get_db)) -> List[TeamOut]:
    teams = db.execute(select(Team).order_by(Team.name_short)).scalars().all()
    return [TeamOut(id=t.id, name_short=t.name_short, name_full=t.name_full) for t in teams]


@router.get("/player-stats", response_model=List[PlayerStatsOut])
def list_player_stats(
    position: Optional[str] = None,
    team_id: Optional[int] = None,
    q: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[PlayerStatsOut]:
    season = get_or_create_season(db)
    total_teams = (
        db.execute(select(func.count(FantasyTeam.id)).where(FantasyTeam.season_id == season.id))
        .scalar()
        or 0
    )

    stats_subq = (
        select(
            PlayerMatchStat.player_id.label("player_id"),
            func.coalesce(func.sum(PlayerMatchStat.goals), 0).label("goals"),
            func.coalesce(func.sum(PlayerMatchStat.assists), 0).label("assists"),
            func.coalesce(func.sum(PlayerMatchStat.minutesplayed), 0).label("minutesplayed"),
            func.coalesce(func.sum(PlayerMatchStat.saves), 0).label("saves"),
            func.coalesce(func.sum(PlayerMatchStat.fouls), 0).label("fouls"),
            func.coalesce(func.sum(PlayerMatchStat.yellow_cards), 0).label("yellow_cards"),
            func.coalesce(func.sum(PlayerMatchStat.red_cards), 0).label("red_cards"),
        )
        .where(PlayerMatchStat.season_id == season.id)
        .group_by(PlayerMatchStat.player_id)
        .subquery()
    )

    selected_subq = (
        select(
            FantasyTeamPlayer.player_id.label("player_id"),
            func.count(FantasyTeamPlayer.fantasy_team_id).label("selected_count"),
        )
        .join(FantasyTeam, FantasyTeam.id == FantasyTeamPlayer.fantasy_team_id)
        .where(FantasyTeam.season_id == season.id)
        .group_by(FantasyTeamPlayer.player_id)
        .subquery()
    )

    query = (
        select(
            PlayerCatalog,
            stats_subq.c.goals,
            stats_subq.c.assists,
            stats_subq.c.minutesplayed,
            stats_subq.c.saves,
            stats_subq.c.fouls,
            stats_subq.c.yellow_cards,
            stats_subq.c.red_cards,
            func.coalesce(selected_subq.c.selected_count, 0).label("selected_count"),
        )
        .outerjoin(stats_subq, PlayerCatalog.player_id == stats_subq.c.player_id)
        .outerjoin(selected_subq, PlayerCatalog.player_id == selected_subq.c.player_id)
    )
    if position:
        query = query.where(PlayerCatalog.position == position)
    if team_id:
        query = query.where(PlayerCatalog.team_id == team_id)
    if q:
        query = query.where(PlayerCatalog.name.ilike(f"%{q}%"))
    if max_price is not None:
        query = query.where(PlayerCatalog.price_current <= max_price)
    if min_price is not None:
        query = query.where(PlayerCatalog.price_current >= min_price)

    query = (
        query.order_by(func.coalesce(selected_subq.c.selected_count, 0).desc(), PlayerCatalog.name)
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(query).all()
    points_round_map: dict[int, list[dict[str, float | int]]] = {}
    if rows:
        player_ids = [row[0].player_id for row in rows]
        points_rows = db.execute(
            select(PointsRound.player_id, Round.round_number, PointsRound.points)
            .join(Round, PointsRound.round_id == Round.id)
            .where(
                PointsRound.season_id == season.id,
                PointsRound.player_id.in_(player_ids),
            )
            .order_by(Round.round_number)
        ).all()
        for player_id, round_number, points in points_rows:
            points_round_map.setdefault(player_id, []).append(
                {"round_number": int(round_number), "points": float(points or 0)}
            )

    results: List[PlayerStatsOut] = []
    for row in rows:
        player = row[0]
        selected_count = int(row[8] or 0)
        selected_percent = (selected_count / total_teams * 100) if total_teams > 0 else 0.0
        results.append(
            PlayerStatsOut(
                player_id=player.player_id,
                name=player.name,
                short_name=player.short_name,
                position=player.position,
                team_id=player.team_id,
                price_current=float(player.price_current),
                is_injured=bool(player.is_injured),
                selected_count=selected_count,
                selected_percent=selected_percent,
                goals=int(row[1] or 0),
                assists=int(row[2] or 0),
                minutesplayed=int(row[3] or 0),
                saves=int(row[4] or 0),
                fouls=int(row[5] or 0),
                yellow_cards=int(row[6] or 0),
                red_cards=int(row[7] or 0),
                rounds=points_round_map.get(player.player_id, []),
            )
        )

    return results


@router.get("/fixtures", response_model=List[FixtureOut])
def list_fixtures(
    round_number: Optional[int] = None, db: Session = Depends(get_db)
) -> List[FixtureOut]:
    query = select(Fixture, Round.round_number).join(Round, Fixture.round_id == Round.id)
    if round_number is not None:
        query = query.where(Round.round_number == round_number)
    rows = db.execute(query).all()
    return [
        FixtureOut(
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


@router.get("/rounds", response_model=List[RoundOut])
def list_rounds(db: Session = Depends(get_db)) -> List[RoundOut]:
    season = get_or_create_season(db)
    rows = (
        db.execute(
            select(Round.round_number, Round.is_closed, Round.starts_at, Round.ends_at)
            .where(Round.season_id == season.id)
            .order_by(Round.round_number)
        )
        .all()
    )
    pending_round = next((row[0] for row in rows if not row[1]), None)
    return [
        RoundOut(
            round_number=row[0],
            is_closed=row[1],
            status=(
                "Cerrada"
                if row[1]
                else ("Pendiente" if pending_round == row[0] else "Proximamente")
            ),
            starts_at=row[2],
            ends_at=row[3],
        )
        for row in rows
    ]


@router.get("/match-stats", response_model=List[MatchPlayerStatOut])
def list_match_stats(
    match_id: int = Query(..., ge=1), db: Session = Depends(get_db)
) -> List[MatchPlayerStatOut]:
    season = get_or_create_season(db)
    fixture_row = (
        db.execute(
            select(Fixture, Round.round_number)
            .join(Round, Fixture.round_id == Round.id)
            .where(Fixture.season_id == season.id, Fixture.match_id == match_id)
        )
        .first()
    )
    if not fixture_row:
        return []

    fixture, _round_number = fixture_row

    stats_rows = (
        db.execute(
            select(PlayerMatchStat, PlayerCatalog)
            .join(PlayerCatalog, PlayerCatalog.player_id == PlayerMatchStat.player_id)
            .where(
                PlayerMatchStat.season_id == season.id,
                PlayerMatchStat.match_id == match_id,
            )
        )
        .all()
    )
    results: List[MatchPlayerStatOut] = []
    for stat, player in stats_rows:
        points, clean_sheet_value, conceded = calc_match_points(player, stat, fixture)
        results.append(
            MatchPlayerStatOut(
                match_id=stat.match_id,
                player_id=player.player_id,
                name=player.name,
                short_name=player.short_name,
                position=player.position,
                team_id=player.team_id,
                minutesplayed=int(stat.minutesplayed or 0),
                goals=int(stat.goals or 0),
                assists=int(stat.assists or 0),
                saves=int(stat.saves or 0),
                fouls=int(stat.fouls or 0),
                yellow_cards=int(getattr(stat, "yellow_cards", 0) or 0),
                red_cards=int(getattr(stat, "red_cards", 0) or 0),
                clean_sheet=clean_sheet_value,
                goals_conceded=conceded,
                points=float(points),
            )
        )

    return results


@router.get("/player-matches", response_model=List[PlayerMatchOut])
def list_player_matches(
    player_id: int = Query(..., ge=1), db: Session = Depends(get_db)
) -> List[PlayerMatchOut]:
    season = get_or_create_season(db)
    player = (
        db.execute(select(PlayerCatalog).where(PlayerCatalog.player_id == player_id))
        .scalars()
        .first()
    )
    if not player:
        return []

    fixtures_rows = (
        db.execute(
            select(Fixture, Round.round_number)
            .join(Round, Fixture.round_id == Round.id)
            .where(
                Fixture.season_id == season.id,
                (Fixture.home_team_id == player.team_id)
                | (Fixture.away_team_id == player.team_id),
            )
            .order_by(Fixture.kickoff_at, Fixture.match_id)
        )
        .all()
    )

    stats_rows = (
        db.execute(
            select(PlayerMatchStat)
            .where(
                PlayerMatchStat.season_id == season.id,
                PlayerMatchStat.player_id == player_id,
            )
        )
        .scalars()
        .all()
    )
    stats_map = {row.match_id: row for row in stats_rows}

    results: List[PlayerMatchOut] = []
    for fixture, round_number in fixtures_rows:
        stat = stats_map.get(fixture.match_id)
        clean_sheet_value: int | None = None
        goals_conceded_value: int | None = None
        points_value: float | None = None
        if stat:
            points_value, clean_sheet_value, goals_conceded_value = calc_match_points(
                player, stat, fixture
            )
        results.append(
            PlayerMatchOut(
                match_id=fixture.match_id,
                round_number=round_number,
                kickoff_at=fixture.kickoff_at,
                status=fixture.status,
                home_team_id=fixture.home_team_id,
                away_team_id=fixture.away_team_id,
                home_score=fixture.home_score,
                away_score=fixture.away_score,
                minutesplayed=int(stat.minutesplayed or 0) if stat else None,
                goals=int(stat.goals or 0) if stat else None,
                assists=int(stat.assists or 0) if stat else None,
                saves=int(stat.saves or 0) if stat else None,
                fouls=int(stat.fouls or 0) if stat else None,
                yellow_cards=int(getattr(stat, "yellow_cards", 0) or 0) if stat else None,
                red_cards=int(getattr(stat, "red_cards", 0) or 0) if stat else None,
                clean_sheet=clean_sheet_value,
                goals_conceded=goals_conceded_value,
                points=float(points_value) if points_value is not None else None,
            )
        )

    return results
