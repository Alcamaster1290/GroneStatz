from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Fixture, PlayerCatalog, PlayerMatchStat
from app.services.fantasy import get_or_create_season, get_round_by_number


def _round_price(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _clamp_price(value: float, min_value: float = 4.0, max_value: float = 12.0) -> float:
    return max(min_value, min(max_value, value))


def _price_delta(points: float) -> float:
    if points > 0:
        return 0.1 * int(points // 3)
    negative_steps = int(abs(points) // 2)
    return -0.2 - (0.1 * negative_steps)


def _goals_conceded(fixture: Fixture, team_id: int | None) -> int | None:
    if team_id is None:
        return None
    if fixture.home_score is None or fixture.away_score is None:
        return None
    if fixture.home_team_id == team_id:
        return fixture.away_score
    if fixture.away_team_id == team_id:
        return fixture.home_score
    return None


def _resolve_fixture_overrides(
    player: PlayerCatalog,
    minutes: int,
    fixture: Fixture | None,
    clean_sheet_value: int | None,
    goals_conceded_value: int | None,
) -> tuple[int | None, int | None, int | None]:
    if not fixture or fixture.home_score is None or fixture.away_score is None:
        return clean_sheet_value, goals_conceded_value, None

    conceded_from_fixture = _goals_conceded(fixture, player.team_id)

    if goals_conceded_value is None or goals_conceded_value == 0:
        if conceded_from_fixture is not None:
            goals_conceded_value = conceded_from_fixture

    if clean_sheet_value is None or clean_sheet_value == 0:
        position = (player.position or "").upper()
        if position in {"G", "GK", "D", "M"} and minutes > 0:
            if conceded_from_fixture is not None:
                clean_sheet_value = 1 if conceded_from_fixture == 0 else 0

    return clean_sheet_value, goals_conceded_value, conceded_from_fixture


def calc_match_points(
    player: PlayerCatalog, stat: PlayerMatchStat, fixture: Fixture | None
) -> tuple[float, int | None, int | None]:
    minutes = int(stat.minutesplayed or 0)
    goals = int(stat.goals or 0)
    assists = int(stat.assists or 0)
    saves = int(stat.saves or 0)
    fouls = int(stat.fouls or 0)
    yellow_cards = int(getattr(stat, "yellow_cards", 0) or 0)
    red_cards = int(getattr(stat, "red_cards", 0) or 0)

    clean_sheet_flag = stat.clean_sheet if hasattr(stat, "clean_sheet") else None
    goals_conceded_override = stat.goals_conceded if hasattr(stat, "goals_conceded") else None
    clean_sheet_value = int(clean_sheet_flag) if clean_sheet_flag is not None else None
    goals_conceded_value = (
        int(goals_conceded_override) if goals_conceded_override is not None else None
    )

    clean_sheet_value, goals_conceded_value, conceded_from_fixture = _resolve_fixture_overrides(
        player,
        minutes,
        fixture,
        clean_sheet_value,
        goals_conceded_value,
    )

    conceded: int | None = goals_conceded_value
    if conceded is None and conceded_from_fixture is not None:
        conceded = conceded_from_fixture

    points = 0.0
    points += goals * 4
    points += (goals // 3) * 3
    points += assists * 3
    points -= yellow_cards * 3
    points -= red_cards * 5

    if minutes >= 90:
        points += 2
    elif minutes > 0:
        points += 1

    points -= fouls // 5

    position = (player.position or "").upper()
    if position in {"G", "GK"} and saves > 0:
        points += saves // 5
    if position in {"G", "GK"} and minutes > 0 and conceded is not None:
        points -= conceded
    if position in {"G", "GK", "D", "M"} and minutes > 0:
        if clean_sheet_value is not None:
            if clean_sheet_value == 1:
                points += 3
        elif conceded == 0:
            points += 3

    return points, clean_sheet_value, conceded


def recalc_round_points(
    db: Session,
    round_number: int,
    apply_prices: bool = True,
    write_price_history: bool = True,
) -> dict:
    season = get_or_create_season(db)
    round_obj = get_round_by_number(db, season.id, round_number)
    if not round_obj:
        raise ValueError("round_not_found")

    fixtures = db.execute(
        select(Fixture).where(Fixture.season_id == season.id, Fixture.round_id == round_obj.id)
    ).scalars()
    fixture_map = {fixture.match_id: fixture for fixture in fixtures}

    match_rows = (
        db.execute(
            select(PlayerMatchStat).where(
                PlayerMatchStat.season_id == season.id,
                PlayerMatchStat.round_id == round_obj.id,
            )
        )
        .scalars()
        .all()
    )

    if not match_rows:
        return {"ok": True, "round_number": round_number, "points_rows": 0, "prices_updated": 0}

    player_ids = {row.player_id for row in match_rows}
    players = (
        db.execute(select(PlayerCatalog).where(PlayerCatalog.player_id.in_(player_ids)))
        .scalars()
        .all()
    )
    player_map: Dict[int, PlayerCatalog] = {player.player_id: player for player in players}

    points_map: Dict[int, float] = {}
    stats_map: Dict[int, Dict[str, int]] = {}

    for row in match_rows:
        player = player_map.get(row.player_id)
        if not player:
            continue

        minutes = int(row.minutesplayed or 0)
        goals = int(row.goals or 0)
        assists = int(row.assists or 0)
        saves = int(row.saves or 0)
        fouls = int(row.fouls or 0)
        yellow_cards = int(getattr(row, "yellow_cards", 0) or 0)
        red_cards = int(getattr(row, "red_cards", 0) or 0)
        clean_sheet_flag = row.clean_sheet if hasattr(row, "clean_sheet") else None
        goals_conceded_override = row.goals_conceded if hasattr(row, "goals_conceded") else None
        clean_sheet_value = int(clean_sheet_flag) if clean_sheet_flag is not None else None
        goals_conceded_value = (
            int(goals_conceded_override) if goals_conceded_override is not None else None
        )

        stats = stats_map.setdefault(
            row.player_id,
            {
                "minutesplayed": 0,
                "goals": 0,
                "assists": 0,
                "saves": 0,
                "fouls": 0,
                "yellow_cards": 0,
                "red_cards": 0,
                "clean_sheets": 0,
                "goals_conceded": 0,
            },
        )
        stats["minutesplayed"] += minutes
        stats["goals"] += goals
        stats["assists"] += assists
        stats["saves"] += saves
        stats["fouls"] += fouls
        stats["yellow_cards"] += yellow_cards
        stats["red_cards"] += red_cards
        # Determine effective clean sheet / conceded for stats + scoring.
        fixture = fixture_map.get(row.match_id)
        clean_sheet_value, goals_conceded_value, conceded_from_fixture = _resolve_fixture_overrides(
            player,
            minutes,
            fixture,
            clean_sheet_value,
            goals_conceded_value,
        )
        conceded: int | None = goals_conceded_value
        if conceded is None and conceded_from_fixture is not None:
            conceded = conceded_from_fixture
        if minutes > 0:
            if clean_sheet_value is not None:
                if clean_sheet_value == 1:
                    stats["clean_sheets"] += 1
            elif conceded == 0:
                stats["clean_sheets"] += 1
        if conceded is not None:
            stats["goals_conceded"] += conceded

        points = 0.0
        points += goals * 4
        points += (goals // 3) * 3
        points += assists * 3
        points -= yellow_cards * 3
        points -= red_cards * 5

        if minutes >= 90:
            points += 2
        elif minutes > 0:
            points += 1

        points -= fouls // 5

        position = (player.position or "").upper()
        if position in {"G", "GK"} and saves > 0:
            points += saves // 5
        if position in {"G", "GK"} and minutes > 0 and conceded is not None:
            points -= conceded
        if position in {"G", "GK", "D", "M"} and minutes > 0:
            if clean_sheet_value is not None:
                if clean_sheet_value == 1:
                    points += 3
            elif conceded == 0:
                points += 3

        points_map[row.player_id] = points_map.get(row.player_id, 0.0) + points

    # Clear previous round aggregates for recalculation.
    db.execute(
        text("DELETE FROM points_round WHERE season_id = :season_id AND round_id = :round_id"),
        {"season_id": season.id, "round_id": round_obj.id},
    )
    db.execute(
        text("DELETE FROM player_round_stats WHERE season_id = :season_id AND round_id = :round_id"),
        {"season_id": season.id, "round_id": round_obj.id},
    )

    points_rows = [
        {
            "season_id": season.id,
            "round_id": round_obj.id,
            "player_id": player_id,
            "points": points,
        }
        for player_id, points in points_map.items()
    ]
    if points_rows:
        db.execute(
            text(
                """
                INSERT INTO points_round (season_id, round_id, player_id, points)
                VALUES (:season_id, :round_id, :player_id, :points)
                ON CONFLICT (season_id, round_id, player_id)
                DO UPDATE SET points = EXCLUDED.points
                """
            ),
            points_rows,
        )

    stats_rows = [
        {
            "season_id": season.id,
            "round_id": round_obj.id,
            "player_id": player_id,
            "minutesplayed": values["minutesplayed"],
            "goals": values["goals"],
            "assists": values["assists"],
            "saves": values["saves"],
            "fouls": values["fouls"],
            "yellow_cards": values["yellow_cards"],
            "red_cards": values["red_cards"],
            "clean_sheets": values["clean_sheets"],
            "goals_conceded": values["goals_conceded"],
        }
        for player_id, values in stats_map.items()
    ]
    if stats_rows:
        db.execute(
            text(
                """
                INSERT INTO player_round_stats (
                    season_id, round_id, player_id, minutesplayed, goals, assists, saves, fouls,
                    yellow_cards, red_cards, clean_sheets, goals_conceded, updated_at
                )
                VALUES (
                    :season_id, :round_id, :player_id, :minutesplayed, :goals, :assists, :saves, :fouls,
                    :yellow_cards, :red_cards, :clean_sheets, :goals_conceded, NOW()
                )
                ON CONFLICT (season_id, round_id, player_id)
                DO UPDATE SET
                    minutesplayed = EXCLUDED.minutesplayed,
                    goals = EXCLUDED.goals,
                    assists = EXCLUDED.assists,
                    saves = EXCLUDED.saves,
                    fouls = EXCLUDED.fouls,
                    yellow_cards = EXCLUDED.yellow_cards,
                    red_cards = EXCLUDED.red_cards,
                    clean_sheets = EXCLUDED.clean_sheets,
                    goals_conceded = EXCLUDED.goals_conceded,
                    updated_at = NOW()
                """
            ),
            stats_rows,
        )

    prices_updated = 0
    if apply_prices:
        price_rows = []
        movement_rows = []
        for player_id, points in points_map.items():
            player = player_map.get(player_id)
            if not player:
                continue
            if getattr(player, "is_injured", False):
                continue
            delta = _price_delta(points)
            current_price = float(player.price_current)
            new_price = _round_price(_clamp_price(current_price + delta))
            actual_delta = _round_price(new_price - current_price)
            if actual_delta == 0:
                continue
            price_rows.append({"player_id": player_id, "price": new_price})
            movement_rows.append(
                {
                    "season_id": season.id,
                    "round_id": round_obj.id,
                    "player_id": player_id,
                    "points": points,
                    "delta": actual_delta,
                }
            )

        if price_rows:
            db.execute(
                text("UPDATE players_catalog SET price_current = :price WHERE player_id = :player_id"),
                price_rows,
            )
            prices_updated = len(price_rows)

        if write_price_history and price_rows:
            history_rows = [
                {
                    "season_id": season.id,
                    "round_id": round_obj.id,
                    "player_id": row["player_id"],
                    "price": row["price"],
                }
                for row in price_rows
            ]
            db.execute(
                text(
                    """
                    INSERT INTO price_history (season_id, round_id, player_id, price)
                    VALUES (:season_id, :round_id, :player_id, :price)
                    ON CONFLICT (season_id, round_id, player_id)
                    DO UPDATE SET price = EXCLUDED.price
                    """
                ),
                history_rows,
            )

        if movement_rows:
            db.execute(
                text(
                    """
                    INSERT INTO price_movements (season_id, round_id, player_id, points, delta, created_at)
                    VALUES (:season_id, :round_id, :player_id, :points, :delta, NOW())
                    ON CONFLICT (season_id, round_id, player_id)
                    DO UPDATE SET
                        points = EXCLUDED.points,
                        delta = EXCLUDED.delta,
                        created_at = NOW()
                    """
                ),
                movement_rows,
            )

        if movement_rows:
            db.execute(
                text(
                    """
                    UPDATE fantasy_teams AS ft
                    SET budget_cap = ft.budget_cap + movements.delta_sum
                    FROM (
                        SELECT ftp.fantasy_team_id AS team_id, COALESCE(SUM(pm.delta), 0) AS delta_sum
                        FROM fantasy_team_players AS ftp
                        JOIN price_movements AS pm
                          ON pm.player_id = ftp.player_id
                        WHERE pm.season_id = :season_id AND pm.round_id = :round_id
                        GROUP BY ftp.fantasy_team_id
                    ) AS movements
                    WHERE ft.id = movements.team_id
                    """
                ),
                {"season_id": season.id, "round_id": round_obj.id},
            )

    db.commit()
    return {
        "ok": True,
        "round_number": round_number,
        "points_rows": len(points_rows),
        "prices_updated": prices_updated,
    }
