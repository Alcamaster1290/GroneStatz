from __future__ import annotations

import argparse
import json
import sys
from datetime import timezone
from pathlib import Path
from typing import Any

import pandas as pd


MASTER_COLUMNS = [
    "match_id",
    "round_number",
    "tournament",
    "season",
    "home_id",
    "away_id",
    "home",
    "away",
    "home_score",
    "away_score",
    "resultado_final",
    "fecha",
    "estadio",
    "ciudad",
    "arbitro",
    "status",
]

TEAM_COLUMNS = [
    "team_id",
    "short_name",
    "full_name",
    "team_colors",
    "is_altitude_team",
    "competitiveness_level",
    "stadium_id",
    "stadium_name_city",
    "province",
    "department",
    "region",
]

PLAYER_STATS_COLUMNS = [
    "match_id",
    "player_id",
    "name",
    "short_name",
    "team_id",
    "position",
    "minutesplayed",
    "goals",
    "assists",
    "yellowcards",
    "redcards",
    "saves",
    "fouls",
    "penaltywon",
    "penaltysave",
    "penaltyconceded",
    "clean_sheet",
    "goals_conceded",
    "rating",
]

SHEET_COVERAGE_COLUMNS = [
    "match_id",
    "source_file",
    "workbook_exists",
    "read_error",
    "has_player_stats",
    "rows_player_stats",
    "has_team_stats",
    "rows_team_stats",
    "has_average_positions",
    "rows_average_positions",
    "has_heatmaps",
    "rows_heatmaps",
    "has_shotmap",
    "rows_shotmap",
    "has_momentum",
    "rows_momentum",
]

EMPTY_STAGE_TABLES = (
    "team_stats_raw",
    "average_positions_raw",
    "heatmaps_raw",
    "shotmap_raw",
    "momentum_raw",
)


def _format_match_datetime(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert(timezone.utc).tz_localize(None)
    return stamp.strftime("%d/%m/%Y %H:%M")


def _result_label(home_score: object, away_score: object) -> str | None:
    if home_score is None or pd.isna(home_score) or away_score is None or pd.isna(away_score):
        return None
    return f"{int(home_score)} - {int(away_score)}"


def _write_stage_table(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def export_fantasy_bridge(
    *,
    fantasy_root: Path,
    season_year: int,
    master_raw_out: Path,
    master_clean_out: Path,
    teams_out: Path,
    bridge_dir: Path,
) -> dict[str, Any]:
    backend_dir = fantasy_root / "backend"
    if not backend_dir.exists():
        raise FileNotFoundError(f"fantasy_backend_not_found: {backend_dir}")

    sys.path.insert(0, str(backend_dir))
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.tables import Fixture, PlayerCatalog, PlayerMatchStat, Round, Season, Team

    db = SessionLocal()
    try:
        season = db.execute(select(Season).where(Season.year == season_year)).scalar_one_or_none()
        if season is None:
            raise RuntimeError(f"fantasy_season_not_found:{season_year}")

        rounds = db.execute(select(Round).where(Round.season_id == season.id)).scalars().all()
        round_lookup = {int(round_row.id): int(round_row.round_number) for round_row in rounds}

        teams = db.execute(select(Team)).scalars().all()
        team_lookup = {
            int(team.id): {
                "team_id": int(team.id),
                "short_name": team.name_short,
                "full_name": team.name_full,
            }
            for team in teams
        }

        fixtures = (
            db.execute(
                select(Fixture)
                .where(Fixture.season_id == season.id)
                .order_by(Fixture.kickoff_at.nullslast(), Fixture.match_id)
            )
            .scalars()
            .all()
        )
        player_catalog = db.execute(select(PlayerCatalog)).scalars().all()
        player_lookup = {
            int(player.player_id): {
                "player_id": int(player.player_id),
                "name": player.name,
                "short_name": player.short_name,
                "position": player.position,
                "team_id": int(player.team_id) if player.team_id is not None else None,
            }
            for player in player_catalog
        }
        player_match_stats = (
            db.execute(
                select(PlayerMatchStat)
                .where(PlayerMatchStat.season_id == season.id)
                .order_by(PlayerMatchStat.match_id, PlayerMatchStat.player_id)
            )
            .scalars()
            .all()
        )
    finally:
        db.close()

    master_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    match_stat_counts: dict[int, int] = {}
    for stat in player_match_stats:
        match_stat_counts[int(stat.match_id)] = match_stat_counts.get(int(stat.match_id), 0) + 1

    for fixture in fixtures:
        match_id = int(fixture.match_id)
        home_meta = team_lookup.get(int(fixture.home_team_id), {}) if fixture.home_team_id is not None else {}
        away_meta = team_lookup.get(int(fixture.away_team_id), {}) if fixture.away_team_id is not None else {}
        master_rows.append(
            {
                "match_id": match_id,
                "round_number": round_lookup.get(int(fixture.round_id)) if fixture.round_id is not None else None,
                "tournament": season.name,
                "season": season.year,
                "home_id": int(fixture.home_team_id) if fixture.home_team_id is not None else None,
                "away_id": int(fixture.away_team_id) if fixture.away_team_id is not None else None,
                "home": home_meta.get("short_name") or home_meta.get("full_name"),
                "away": away_meta.get("short_name") or away_meta.get("full_name"),
                "home_score": fixture.home_score,
                "away_score": fixture.away_score,
                "resultado_final": _result_label(fixture.home_score, fixture.away_score),
                "fecha": _format_match_datetime(fixture.kickoff_at),
                "estadio": fixture.stadium,
                "ciudad": fixture.city,
                "arbitro": None,
                "status": fixture.status,
            }
        )
        rows_player_stats = match_stat_counts.get(match_id, 0)
        coverage_rows.append(
            {
                "match_id": match_id,
                "source_file": "fantasy_admin_bridge",
                "workbook_exists": True,
                "read_error": None,
                "has_player_stats": rows_player_stats > 0,
                "rows_player_stats": rows_player_stats,
                "has_team_stats": False,
                "rows_team_stats": 0,
                "has_average_positions": False,
                "rows_average_positions": 0,
                "has_heatmaps": False,
                "rows_heatmaps": 0,
                "has_shotmap": False,
                "rows_shotmap": 0,
                "has_momentum": False,
                "rows_momentum": 0,
            }
        )

    player_rows: list[dict[str, Any]] = []
    for stat in player_match_stats:
        identity = player_lookup.get(int(stat.player_id), {})
        player_rows.append(
            {
                "match_id": int(stat.match_id),
                "player_id": int(stat.player_id),
                "name": identity.get("name"),
                "short_name": identity.get("short_name"),
                "team_id": identity.get("team_id"),
                "position": identity.get("position"),
                "minutesplayed": stat.minutesplayed,
                "goals": stat.goals,
                "assists": stat.assists,
                "yellowcards": stat.yellow_cards,
                "redcards": stat.red_cards,
                "saves": stat.saves,
                "fouls": stat.fouls,
                "penaltywon": None,
                "penaltysave": None,
                "penaltyconceded": None,
                "clean_sheet": stat.clean_sheet,
                "goals_conceded": stat.goals_conceded,
                "rating": None,
            }
        )

    master_df = pd.DataFrame(master_rows, columns=MASTER_COLUMNS)
    teams_df = pd.DataFrame(sorted(team_lookup.values(), key=lambda row: (row.get("short_name") or "", row["team_id"])), columns=TEAM_COLUMNS)
    player_stats_df = pd.DataFrame(player_rows, columns=PLAYER_STATS_COLUMNS)
    coverage_df = pd.DataFrame(coverage_rows, columns=SHEET_COVERAGE_COLUMNS)

    master_raw_out.parent.mkdir(parents=True, exist_ok=True)
    master_clean_out.parent.mkdir(parents=True, exist_ok=True)
    teams_out.parent.mkdir(parents=True, exist_ok=True)
    bridge_dir.mkdir(parents=True, exist_ok=True)

    master_df.to_excel(master_raw_out, index=False, engine="openpyxl")
    master_df.to_excel(master_clean_out, index=False, engine="openpyxl")
    teams_df.to_excel(teams_out, index=False, engine="openpyxl")

    _write_stage_table(bridge_dir / "player_stats_raw.parquet", player_stats_df)
    _write_stage_table(bridge_dir / "sheet_coverage.parquet", coverage_df)
    for table_name in EMPTY_STAGE_TABLES:
        _write_stage_table(bridge_dir / f"{table_name}.parquet", pd.DataFrame())

    manifest = {
        "source_mode": "fantasy_admin",
        "provider": "Fantasy Liga 1 Admin",
        "season_year": season.year,
        "season_name": season.name,
        "exported_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "counts": {
            "teams": int(len(teams_df)),
            "fixtures": int(len(master_df)),
            "player_match_stats": int(len(player_stats_df)),
        },
    }
    (bridge_dir / "export_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Fantasy Liga 1 admin data into GroneStatz raw bridge artifacts.")
    parser.add_argument("--fantasy-root", required=True)
    parser.add_argument("--season-year", type=int, required=True)
    parser.add_argument("--master-raw-out", required=True)
    parser.add_argument("--master-clean-out", required=True)
    parser.add_argument("--teams-out", required=True)
    parser.add_argument("--bridge-dir", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = export_fantasy_bridge(
        fantasy_root=Path(args.fantasy_root),
        season_year=int(args.season_year),
        master_raw_out=Path(args.master_raw_out),
        master_clean_out=Path(args.master_clean_out),
        teams_out=Path(args.teams_out),
        bridge_dir=Path(args.bridge_dir),
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
