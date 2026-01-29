from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

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
    Round,
    Season,
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
    AdminPlayerRoundStatsIn,
    AdminPlayerStatOut,
    AdminPlayerInjuryIn,
    AdminPlayerInjuryOut,
    AdminPriceMovementOut,
    AdminTeamOut,
    AdminTeamPlayerOut,
)
from app.services.data_pipeline import ingest_parquets_to_duckdb, sync_duckdb_to_postgres
from app.services.fantasy import ensure_round, get_or_create_season, get_round_by_number
from app.services.action_log import log_action
from app.services.scoring import recalc_round_points

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


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
    season = get_or_create_season(db)
    round_obj = ensure_round(db, season.id, payload.round_number)

    fixture = db.execute(select(Fixture).where(Fixture.match_id == payload.match_id)).scalar_one_or_none()
    if fixture:
        fixture.round_id = round_obj.id
        fixture.season_id = season.id
        fixture.home_team_id = payload.home_team_id
        fixture.away_team_id = payload.away_team_id
        fixture.kickoff_at = payload.kickoff_at
        fixture.stadium = payload.stadium
        fixture.city = payload.city
        if payload.status is not None:
            fixture.status = payload.status
        if payload.home_score is not None:
            fixture.home_score = payload.home_score
        if payload.away_score is not None:
            fixture.away_score = payload.away_score
    else:
        fixture = Fixture(
            season_id=season.id,
            round_id=round_obj.id,
            match_id=payload.match_id,
            home_team_id=payload.home_team_id,
            away_team_id=payload.away_team_id,
            kickoff_at=payload.kickoff_at,
            stadium=payload.stadium,
            city=payload.city,
            status=payload.status or "Programado",
            home_score=payload.home_score,
            away_score=payload.away_score,
        )
        db.add(fixture)

    db.commit()
    db.refresh(fixture)

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
    ]

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
    return {"ok": True, "count": len(rows)}


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
        fixture.home_team_id = data["home_team_id"]
    if "away_team_id" in data:
        fixture.away_team_id = data["away_team_id"]
    if "kickoff_at" in data:
        fixture.kickoff_at = data["kickoff_at"]
    if "stadium" in data:
        fixture.stadium = data["stadium"]
    if "city" in data:
        fixture.city = data["city"]
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
    return [
        AdminRoundOut(
            id=row.id,
            round_number=row.round_number,
            is_closed=row.is_closed,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
        )
        for row in rows
    ]


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
