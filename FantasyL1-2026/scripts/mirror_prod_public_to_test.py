from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, text

BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    ActionLog,
    AppConfig,
    FantasyLineup,
    FantasyLineupSlot,
    FantasyTeam,
    FantasyTeamPlayer,
    FantasyTransfer,
    Fixture,
    League,
    LeagueMember,
    PasswordResetToken,
    PaymentEvent,
    PlayerCatalog,
    PlayerMatchStat,
    PointsRound,
    PriceMovement,
    PushDeviceToken,
    Round,
    RoundPushNotification,
    Season,
    Subscription,
    Team,
    User,
)


MIRROR_EMAIL_PREFIX = "prod_mirror_"
MIRROR_EMAIL_SUFFIX = "@test.local"
MIRROR_PLAYER_NAME_PREFIX = "Prod Mirror Player"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Espejar datos publicos de prod hacia DB test (ranking + rounds + fixtures)"
    )
    parser.add_argument(
        "--api-base",
        default="https://api.fantasyliga1peru.com",
        help="Base URL del API de prod/public",
    )
    parser.add_argument("--season-year", type=int, default=2026)
    parser.add_argument(
        "--last-sell-round",
        type=int,
        default=12,
        help="Valor para APERTURA_PREMIUM_LAST_SELL_ROUND en test",
    )
    parser.add_argument(
        "--player-id-base",
        type=int,
        default=990000000,
        help="Base id para players sinteticos del ranking espejado",
    )
    parser.add_argument(
        "--team-id-base",
        type=int,
        default=970000000,
        help="Base id para fantasy teams sinteticos del ranking espejado",
    )
    parser.add_argument(
        "--user-id-base",
        type=int,
        default=980000000,
        help="Base id para users sinteticos del ranking espejado",
    )
    return parser.parse_args()


def fetch_json(api_base: str, path: str, retries: int = 4) -> Any:
    url = f"{api_base.rstrip('/')}{path}"
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "fantasy-mirror-test/1.0"},
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            last_error = exc
            if attempt == retries:
                raise
    raise RuntimeError(f"fetch failed for {url}: {last_error}")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def upsert_app_config(db, key: str, value: str) -> None:
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=value))
        return
    row.value = value


def sync_rounds(db, season_id: int, rounds_payload: list[dict]) -> dict[int, Round]:
    existing_rounds = {
        rr.round_number: rr
        for rr in db.execute(select(Round).where(Round.season_id == season_id)).scalars().all()
    }
    prod_round_numbers: set[int] = set()

    for item in rounds_payload:
        rn = int(item["round_number"])
        prod_round_numbers.add(rn)
        row = existing_rounds.get(rn)
        if row is None:
            row = Round(
                season_id=season_id,
                round_number=rn,
                is_closed=bool(item.get("is_closed", False)),
            )
            db.add(row)
            db.flush()
            existing_rounds[rn] = row
        row.is_closed = bool(item.get("is_closed", False))
        row.starts_at = parse_dt(item.get("starts_at"))
        row.ends_at = parse_dt(item.get("ends_at"))

    for rn, row in existing_rounds.items():
        if rn not in prod_round_numbers:
            # Keep future rounds open in test so ranking/public views match prod semantics.
            row.is_closed = False

    db.flush()
    return existing_rounds


def cleanup_previous_mirror(db, user_ids: list[int], team_ids: list[int], player_ids: list[int]) -> None:
    if team_ids:
        lineup_ids = db.execute(
            select(FantasyLineup.id).where(FantasyLineup.fantasy_team_id.in_(team_ids))
        ).scalars().all()
        db.execute(delete(LeagueMember).where(LeagueMember.fantasy_team_id.in_(team_ids)))
        db.execute(delete(League).where(League.owner_fantasy_team_id.in_(team_ids)))
        db.query(ActionLog).filter(ActionLog.fantasy_team_id.in_(team_ids)).update(
            {ActionLog.fantasy_team_id: None},
            synchronize_session=False,
        )
        db.query(ActionLog).filter(ActionLog.target_fantasy_team_id.in_(team_ids)).update(
            {ActionLog.target_fantasy_team_id: None},
            synchronize_session=False,
        )
        if lineup_ids:
            db.execute(delete(FantasyLineupSlot).where(FantasyLineupSlot.lineup_id.in_(lineup_ids)))
        db.execute(delete(FantasyLineup).where(FantasyLineup.fantasy_team_id.in_(team_ids)))
        db.execute(delete(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id.in_(team_ids)))
        db.execute(delete(FantasyTransfer).where(FantasyTransfer.fantasy_team_id.in_(team_ids)))
        db.execute(delete(FantasyTeam).where(FantasyTeam.id.in_(team_ids)))

    if user_ids:
        db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(user_ids)))
        db.execute(delete(PaymentEvent).where(PaymentEvent.user_id.in_(user_ids)))
        db.execute(delete(Subscription).where(Subscription.user_id.in_(user_ids)))
        push_ids = db.execute(
            select(PushDeviceToken.id).where(PushDeviceToken.user_id.in_(user_ids))
        ).scalars().all()
        if push_ids:
            db.execute(delete(RoundPushNotification).where(RoundPushNotification.device_id.in_(push_ids)))
            db.execute(delete(PushDeviceToken).where(PushDeviceToken.id.in_(push_ids)))
        db.query(ActionLog).filter(ActionLog.actor_user_id.in_(user_ids)).update(
            {ActionLog.actor_user_id: None},
            synchronize_session=False,
        )
        db.query(ActionLog).filter(ActionLog.target_user_id.in_(user_ids)).update(
            {ActionLog.target_user_id: None},
            synchronize_session=False,
        )
        db.execute(delete(User).where(User.id.in_(user_ids)))

    if player_ids:
        db.execute(delete(FantasyTeamPlayer).where(FantasyTeamPlayer.player_id.in_(player_ids)))
        db.execute(delete(PointsRound).where(PointsRound.player_id.in_(player_ids)))
        db.execute(delete(PriceMovement).where(PriceMovement.player_id.in_(player_ids)))
        db.execute(delete(PlayerCatalog).where(PlayerCatalog.player_id.in_(player_ids)))


def main() -> None:
    args = parse_args()
    settings = get_settings()
    if settings.APP_ENV.strip().lower() != "test":
        raise SystemExit(
            f"Refusing to run outside test env. Current APP_ENV='{settings.APP_ENV}'."
        )

    teams_payload = fetch_json(args.api_base, "/catalog/teams")
    rounds_payload = fetch_json(args.api_base, "/catalog/rounds")
    ranking_payload = fetch_json(args.api_base, "/ranking/general")
    fixtures_by_round = {}
    match_stats_by_match: dict[int, list[dict[str, Any]]] = {}
    for r in rounds_payload:
        rn = int(r["round_number"])
        fixtures_by_round[rn] = fetch_json(
            args.api_base, f"/catalog/fixtures?round_number={rn}"
        )
        for fixture in fixtures_by_round[rn]:
            status = str(fixture.get("status") or "").strip().lower()
            if status != "finalizado":
                continue
            match_id = int(fixture["match_id"])
            match_stats_by_match[match_id] = fetch_json(
                args.api_base, f"/catalog/match-stats?match_id={match_id}"
            )

    with SessionLocal() as db:
        season = db.execute(
            select(Season).where(Season.year == args.season_year)
        ).scalar_one_or_none()
        if season is None:
            season = Season(year=args.season_year, name=f"{args.season_year} Apertura")
            db.add(season)
            db.flush()

        upsert_app_config(db, "APERTURA_PREMIUM_LAST_SELL_ROUND", str(args.last_sell_round))

        for team in teams_payload:
            team_id = int(team["id"])
            row = db.get(Team, team_id)
            if row is None:
                row = Team(id=team_id)
                db.add(row)
            row.name_short = team.get("name_short")
            row.name_full = team.get("name_full")
        db.flush()

        round_map = sync_rounds(db, season.id, rounds_payload)
        fixture_round_by_match: dict[int, int] = {}

        prod_match_ids: set[int] = set()
        for rn, fixtures in fixtures_by_round.items():
            round_row = round_map[rn]
            for item in fixtures:
                match_id = int(item["match_id"])
                prod_match_ids.add(match_id)
                fixture_round_by_match[match_id] = round_row.id
                row = db.execute(
                    select(Fixture).where(Fixture.match_id == match_id)
                ).scalar_one_or_none()
                if row is None:
                    row = Fixture(match_id=match_id, season_id=season.id, round_id=round_row.id)
                    db.add(row)
                row.season_id = season.id
                row.round_id = round_row.id
                row.home_team_id = item.get("home_team_id")
                row.away_team_id = item.get("away_team_id")
                row.kickoff_at = parse_dt(item.get("kickoff_at"))
                row.stadium = item.get("stadium")
                row.city = item.get("city")
                row.status = item.get("status") or "Programado"
                row.home_score = item.get("home_score")
                row.away_score = item.get("away_score")

        stale_fixtures = db.execute(
            select(Fixture.id, Fixture.match_id).where(Fixture.season_id == season.id)
        ).all()
        stale_ids = [fid for fid, mid in stale_fixtures if mid not in prod_match_ids]
        if stale_ids:
            db.execute(delete(Fixture).where(Fixture.id.in_(stale_ids)))

        season_round_ids = [row.id for row in round_map.values()]
        if season_round_ids:
            db.execute(
                delete(PlayerMatchStat).where(
                    PlayerMatchStat.season_id == season.id,
                    PlayerMatchStat.round_id.in_(season_round_ids),
                )
            )

        default_team_id = int(teams_payload[0]["id"]) if teams_payload else 2305

        player_seed_map: dict[int, dict[str, Any]] = {}
        for match_id, stats_rows in match_stats_by_match.items():
            if not fixture_round_by_match.get(match_id):
                continue
            for stat in stats_rows:
                player_id = int(stat.get("player_id", 0) or 0)
                if player_id <= 0:
                    continue
                position_raw = str(stat.get("position") or "M").strip().upper()
                position = position_raw[:1] if position_raw else "M"
                if position not in {"G", "D", "M", "F"}:
                    position = "M"
                team_id = int(stat.get("team_id", 0) or 0)
                if team_id <= 0:
                    team_id = default_team_id
                player_seed_map[player_id] = {
                    "player_id": player_id,
                    "name": str(stat.get("name") or f"Player {player_id}")[:120],
                    "short_name": (str(stat.get("short_name"))[:80] if stat.get("short_name") else None),
                    "position": position,
                    "team_id": team_id,
                }

        if player_seed_map:
            existing_players = set(
                db.execute(
                    select(PlayerCatalog.player_id).where(
                        PlayerCatalog.player_id.in_(list(player_seed_map.keys()))
                    )
                )
                .scalars()
                .all()
            )
            incoming_team_ids = {row["team_id"] for row in player_seed_map.values()}
            existing_teams = set(
                db.execute(select(Team.id).where(Team.id.in_(list(incoming_team_ids)))).scalars().all()
            )
            for team_id in sorted(incoming_team_ids - existing_teams):
                db.add(Team(id=team_id))
            db.flush()

            for player_id, payload in player_seed_map.items():
                existing = db.get(PlayerCatalog, player_id)
                if existing is None:
                    db.add(
                        PlayerCatalog(
                            player_id=payload["player_id"],
                            name=payload["name"],
                            short_name=payload["short_name"],
                            position=payload["position"],
                            team_id=payload["team_id"],
                            price_current=5.0,
                            minutesplayed=0,
                            matches_played=0,
                            goals=0,
                            assists=0,
                            saves=0,
                            fouls=0,
                            is_injured=False,
                        )
                    )
                else:
                    existing.name = payload["name"]
                    existing.short_name = payload["short_name"]
                    existing.position = payload["position"]
                    existing.team_id = payload["team_id"]
            db.flush()

        match_stats_rows = []
        for match_id, stats_rows in match_stats_by_match.items():
            round_id = fixture_round_by_match.get(match_id)
            if not round_id:
                continue
            for stat in stats_rows:
                player_id = int(stat.get("player_id", 0) or 0)
                if player_id <= 0:
                    continue
                match_stats_rows.append(
                    {
                        "season_id": season.id,
                        "round_id": round_id,
                        "match_id": match_id,
                        "player_id": player_id,
                        "minutesplayed": int(stat.get("minutesplayed", 0) or 0),
                        "goals": int(stat.get("goals", 0) or 0),
                        "assists": int(stat.get("assists", 0) or 0),
                        "saves": int(stat.get("saves", 0) or 0),
                        "fouls": int(stat.get("fouls", 0) or 0),
                        "yellow_cards": int(stat.get("yellow_cards", 0) or 0),
                        "red_cards": int(stat.get("red_cards", 0) or 0),
                        "clean_sheet": (int(stat["clean_sheet"]) if stat.get("clean_sheet") is not None else None),
                        "goals_conceded": (
                            int(stat["goals_conceded"])
                            if stat.get("goals_conceded") is not None
                            else None
                        ),
                    }
                )

        if match_stats_rows:
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
                match_stats_rows,
            )

        mirror_users = db.execute(
            select(User).where(
                User.email.like(f"{MIRROR_EMAIL_PREFIX}%{MIRROR_EMAIL_SUFFIX}")
            )
        ).scalars().all()
        mirror_user_ids = [u.id for u in mirror_users]
        mirror_team_ids = (
            db.execute(
                select(FantasyTeam.id).where(FantasyTeam.user_id.in_(mirror_user_ids))
            )
            .scalars()
            .all()
            if mirror_user_ids
            else []
        )
        mirror_player_ids = db.execute(
            select(PlayerCatalog.player_id).where(
                PlayerCatalog.name.like(f"{MIRROR_PLAYER_NAME_PREFIX}%")
            )
        ).scalars().all()

        cleanup_previous_mirror(db, mirror_user_ids, mirror_team_ids, mirror_player_ids)

        created_entries = 0

        for idx, entry in enumerate(ranking_payload.get("entries", []), start=1):
            user_id = args.user_id_base + idx
            team_id = args.team_id_base + idx
            player_id = args.player_id_base + idx

            db.add(
                User(
                    id=user_id,
                    email=f"{MIRROR_EMAIL_PREFIX}{idx}{MIRROR_EMAIL_SUFFIX}",
                    password_hash="x",
                )
            )
            db.flush()

            favorite_team_id = entry.get("favorite_team_id")
            if favorite_team_id is not None and db.get(Team, int(favorite_team_id)) is None:
                favorite_team_id = None

            db.add(
                FantasyTeam(
                    id=team_id,
                    user_id=user_id,
                    season_id=season.id,
                    name=(entry.get("team_name") or f"Team {idx}")[:60],
                    favorite_team_id=favorite_team_id,
                    budget_cap=100.0,
                )
            )
            db.add(
                PlayerCatalog(
                    player_id=player_id,
                    name=f"{MIRROR_PLAYER_NAME_PREFIX} {idx}",
                    short_name=f"PM{idx}",
                    position="M",
                    team_id=default_team_id,
                    price_current=5.0,
                    minutesplayed=0,
                    matches_played=0,
                    goals=0,
                    assists=0,
                    saves=0,
                    fouls=0,
                    is_injured=False,
                )
            )
            db.flush()

            for round_item in entry.get("rounds", []):
                rn = int(round_item.get("round_number", 0))
                round_row = round_map.get(rn)
                if round_row is None:
                    continue
                lineup = FantasyLineup(
                    fantasy_team_id=team_id,
                    round_id=round_row.id,
                    formation_code="DEFAULT",
                    captain_player_id=None,
                    vice_captain_player_id=None,
                )
                db.add(lineup)
                db.flush()
                db.add(
                    FantasyLineupSlot(
                        lineup_id=lineup.id,
                        slot_index=1,
                        is_starter=True,
                        role="GK",
                        player_id=player_id,
                    )
                )

                points = float(round_item.get("points", 0) or 0)
                delta = float(round_item.get("price_delta", 0) or 0)
                db.add(
                    PointsRound(
                        season_id=season.id,
                        round_id=round_row.id,
                        player_id=player_id,
                        points=points,
                    )
                )
                db.add(
                    PriceMovement(
                        season_id=season.id,
                        round_id=round_row.id,
                        player_id=player_id,
                        points=points,
                        delta=delta,
                    )
                )

            created_entries += 1

        db.commit()

    print(
        json.dumps(
            {
                "ok": True,
                "env": settings.APP_ENV,
                "season_year": args.season_year,
                "rounds_synced": len(rounds_payload),
                "fixtures_synced": sum(len(v) for v in fixtures_by_round.values()),
                "match_stats_synced": sum(len(v) for v in match_stats_by_match.values()),
                "ranking_entries_mirrored": created_entries,
                "premium_last_sell_round": args.last_sell_round,
            }
        )
    )


if __name__ == "__main__":
    main()
