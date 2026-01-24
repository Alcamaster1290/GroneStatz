from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models import FantasyTeam, FantasyTeamPlayer, PlayerCatalog, Round, Season, User
from app.schemas.admin import AdminTeamOut, AdminTeamPlayerOut
from app.services.data_pipeline import ingest_parquets_to_duckdb, sync_duckdb_to_postgres
from app.services.fantasy import ensure_round, get_or_create_season

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


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
