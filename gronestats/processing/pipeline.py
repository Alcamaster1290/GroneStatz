from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from gronestats.data_layout import SeasonDataLayout, season_layout
from gronestats.processing.canonical_warehouse import (
    build_canonical_tables,
    build_dashboard_bundle_from_canonical,
    build_fantasy_bundle_from_canonical,
    load_canonical_tables_for_season,
    upsert_canonical_tables,
    validate_warehouse_contract,
)
from gronestats.processing.fantasy_export import (
    FANTASY_EXPORT_TABLES,
    validate_fantasy_export_bundle,
)
from gronestats.processing.optional_sheet_backfill import (
    load_optional_backfill_report_for_staging,
    warning_suffix_from_backfill_report,
)

PROVIDER_NAME = "SofaScore (Opta-backed)"
FANTASY_PROVIDER_NAME = "Fantasy Liga 1 Admin"
FANTASY_SOURCE_MODE = "fantasy_admin"
PUBLISH_TARGET_CHOICES = ("dashboard", "fantasy", "all")
PHASES = (
    "extract-master",
    "bootstrap-raw",
    "build-staging",
    "build-curated",
    "build-warehouse",
    "validate",
    "publish",
)
REQUIRED_CURATED_TABLES = (
    "matches",
    "teams",
    "players",
    "player_match",
    "player_totals_full_season",
    "team_stats",
    "average_positions",
    "heatmap_points",
    "shot_events",
    "match_momentum",
    "player_identity",
)
CORE_DASHBOARD_TABLES = (
    "matches",
    "teams",
    "players",
    "player_match",
    "team_stats",
    "average_positions",
    "heatmap_points",
)
STAGING_TABLES = (
    "matches_raw",
    "player_stats_raw",
    "team_stats_raw",
    "average_positions_raw",
    "heatmaps_raw",
    "shotmap_raw",
    "momentum_raw",
    "sheet_coverage",
)
SHEET_ALIASES: dict[str, list[str]] = {
    "team_stats": ["Team Stats", "TeamStats"],
    "player_stats": ["Player Stats", "Players", "PlayerStats"],
    "average_positions": ["Average Positions", "AveragePositions"],
    "heatmaps": ["Heatmap", "Heatmaps"],
    "shotmap": ["Shotmap", "Match Shots"],
    "momentum": ["Match Momentum", "Momentum"],
}
REQUIRED_SHEET_KEYS = ("player_stats", "team_stats", "average_positions")
WARNING_SHEET_KEYS = ("heatmaps", "shotmap", "momentum")
LEGACY_SPLIT_FILE_TO_SHEET = {
    "Players": "Player Stats",
    "Teams": "Team Stats",
    "AveragePositions": "Average Positions",
    "Heatmaps": "Heatmaps",
    "Shotmap": "Shotmap",
    "Momentum": "Match Momentum",
}
PIPELINE_ARTIFACT_DIRS = {"raw", "staging", "curated", "dashboard", "fantasy", "parquets"}


@dataclass(frozen=True)
class PipelinePaths:
    base_dir: Path
    league: str
    season: int
    run_id: str
    release_id: str

    @property
    def layout(self) -> SeasonDataLayout:
        return season_layout(self.season, league=self.league, repo_root=self.base_dir)

    @property
    def legacy_league_dir(self) -> Path:
        return self.layout.league_dir

    @property
    def season_dir(self) -> Path:
        return self.layout.season_dir

    @property
    def raw_dir(self) -> Path:
        return self.layout.raw_dir

    @property
    def raw_master_raw_dir(self) -> Path:
        return self.raw_dir / "master" / "raw"

    @property
    def raw_master_clean_dir(self) -> Path:
        return self.raw_dir / "master" / "clean"

    @property
    def raw_details_dir(self) -> Path:
        return self.raw_dir / "details" / "xlsx"

    @property
    def raw_runs_dir(self) -> Path:
        return self.raw_dir / "runs"

    @property
    def staging_dir(self) -> Path:
        return self.layout.staging_dir

    @property
    def curated_dir(self) -> Path:
        return self.layout.curated_dir

    @property
    def warehouse_dir(self) -> Path:
        return self.layout.warehouse_dir

    @property
    def warehouse_db_path(self) -> Path:
        return self.layout.warehouse_db_path

    @property
    def dashboard_dir(self) -> Path:
        return self.layout.dashboard.root_dir

    @property
    def dashboard_releases_dir(self) -> Path:
        return self.layout.dashboard.releases_dir

    @property
    def dashboard_current_dir(self) -> Path:
        return self.layout.dashboard.current_dir

    @property
    def dashboard_release_dir(self) -> Path:
        return self.layout.dashboard.release_dir(self.release_id)

    @property
    def fantasy_dir(self) -> Path:
        return self.layout.fantasy.root_dir

    @property
    def fantasy_releases_dir(self) -> Path:
        return self.layout.fantasy.releases_dir

    @property
    def fantasy_current_dir(self) -> Path:
        return self.layout.fantasy.current_dir

    @property
    def fantasy_release_dir(self) -> Path:
        return self.layout.fantasy.release_dir(self.release_id)

    @property
    def releases_dir(self) -> Path:
        return self.dashboard_releases_dir

    @property
    def current_dir(self) -> Path:
        return self.dashboard_current_dir

    @property
    def release_dir(self) -> Path:
        return self.dashboard_release_dir

    @property
    def run_dir(self) -> Path:
        return self.raw_runs_dir / self.run_id

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "manifest.json"

    @property
    def validation_path(self) -> Path:
        return self.run_dir / "validation.json"

    @property
    def log_path(self) -> Path:
        return self.run_dir / "run.log"

    @property
    def validation_candidates_dir(self) -> Path:
        return self.run_dir / "validation_candidates"

    @property
    def dashboard_validation_candidate_dir(self) -> Path:
        return self.validation_candidates_dir / "dashboard"

    @property
    def fantasy_validation_candidate_dir(self) -> Path:
        return self.validation_candidates_dir / "fantasy"

    @property
    def raw_inventory_path(self) -> Path:
        return self.run_dir / "raw_inventory.parquet"

    @property
    def master_inventory_path(self) -> Path:
        return self.run_dir / "master_inventory.parquet"

    @property
    def legacy_master_raw_path(self) -> Path:
        return self.legacy_league_dir / f"Partidos_{self.league}_{self.season}.xlsx"

    @property
    def legacy_master_clean_path(self) -> Path:
        return self.legacy_league_dir / f"Partidos_{self.league}_{self.season}_limpio.xlsx"

    @property
    def legacy_master_clean_fallback_path(self) -> Path:
        return self.base_dir / "gronestats" / "data" / "master_data" / f"Partidos_{self.league}_{self.season}_limpio.xlsx"

    @property
    def teams_reference_path(self) -> Path:
        return self.base_dir / "gronestats" / "data" / "master_data" / "BD Alkagrone 2025.xlsx"

    @property
    def legacy_normalized_dir(self) -> Path:
        return self.layout.legacy_normalized_dir

    @property
    def legacy_zero_matches_path(self) -> Path:
        return self.season_dir / "0_Matches.xlsx"

    @property
    def legacy_zero_teams_path(self) -> Path:
        return self.season_dir / "0_Teams.xlsx"

    @property
    def fantasy_repo_dir(self) -> Path:
        return self.base_dir / "FantasyL1-2026"

    @property
    def fantasy_python_path(self) -> Path:
        return self.fantasy_repo_dir / ".venv" / "Scripts" / "python.exe"

    @property
    def fantasy_bridge_dir(self) -> Path:
        return self.raw_dir / "fantasy_bridge"

    @property
    def fantasy_bridge_manifest_path(self) -> Path:
        return self.fantasy_bridge_dir / "export_manifest.json"


@dataclass
class RunContext:
    paths: PipelinePaths
    mode: str
    only_missing: bool
    force: bool
    dry_run: bool
    publish_target: str
    logger: "PipelineLogger"
    manifest: dict[str, Any]


class PipelineLogger:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def log(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"[{stamp}] {message}"
        print(line)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp_id(moment: datetime | None = None) -> str:
    value = moment or utc_now()
    return value.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat()
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=json_default), encoding="utf-8")


def selected_publish_targets(target: str) -> tuple[str, ...]:
    if target == "all":
        return ("dashboard", "fantasy")
    if target not in {"dashboard", "fantasy"}:
        raise ValueError(f"Unsupported publish target: {target}")
    return (target,)


def load_curated_tables(curated_dir: Path) -> dict[str, pd.DataFrame]:
    return {
        table_name: read_parquet_safe(curated_dir / f"{table_name}.parquet")
        for table_name in REQUIRED_CURATED_TABLES
    }


def write_table_bundle(dataset_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    ensure_dir(dataset_dir)
    for table_name, frame in tables.items():
        stringify_if_mixed_objects(frame).to_parquet(dataset_dir / f"{table_name}.parquet", index=False)


def combine_target_validations(target_validations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    target_errors = [
        f"{target}: {message}"
        for target, payload in target_validations.items()
        for message in payload.get("blocking_errors", [])
    ]
    target_warnings = [
        f"{target}: {message}"
        for target, payload in target_validations.items()
        for message in payload.get("warnings", [])
    ]
    return {
        "status": "passed" if not target_errors else "failed",
        "validated_at": utc_now().isoformat(),
        "blocking_errors": target_errors,
        "warnings": target_warnings,
        "targets": target_validations,
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_parquet_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def master_clean_has_rows(paths: PipelinePaths) -> bool:
    for candidate in (paths.legacy_master_clean_path, paths.legacy_master_clean_fallback_path):
        if not candidate.exists():
            continue
        try:
            frame = pd.read_excel(candidate, nrows=2)
        except Exception:
            continue
        if not frame.empty:
            return True
    return False


def fantasy_bridge_has_useful_data(paths: PipelinePaths) -> bool:
    if not paths.fantasy_bridge_manifest_path.exists():
        return False
    try:
        manifest = read_json(paths.fantasy_bridge_manifest_path)
    except Exception:
        return False
    counts = manifest.get("counts", {}) if isinstance(manifest, dict) else {}
    fixtures = int(pd.to_numeric(pd.Series([counts.get("fixtures", 0)]), errors="coerce").fillna(0).iloc[0])
    player_match_stats = int(
        pd.to_numeric(pd.Series([counts.get("player_match_stats", 0)]), errors="coerce").fillna(0).iloc[0]
    )
    return fixtures > 0 or player_match_stats > 0


def source_mode_from_paths(paths: PipelinePaths) -> str:
    if master_clean_has_rows(paths):
        return "sofascore"
    if fantasy_bridge_has_useful_data(paths):
        return FANTASY_SOURCE_MODE
    return "sofascore"


def provider_name_for_source_mode(source_mode: str) -> str:
    if source_mode == FANTASY_SOURCE_MODE:
        return FANTASY_PROVIDER_NAME
    return PROVIDER_NAME


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def reset_dir(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_root not in resolved_path.parents and resolved_path != resolved_root:
        raise ValueError(f"Refusing to reset path outside root: {path}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def find_latest_file(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0] if files else None


def latest_master_clean_path(paths: PipelinePaths) -> Path:
    latest = find_latest_file(paths.raw_master_clean_dir, "*.xlsx")
    if latest is None:
        raise FileNotFoundError(f"No clean master found in {paths.raw_master_clean_dir}")
    return latest


def candidate_source_season_dirs(paths: PipelinePaths) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()
    raw_candidates = [
        paths.season_dir,
        paths.base_dir.parent / "GroneStats_Legacy" / "GRONESTATS 1.0" / paths.league / str(paths.season),
        paths.base_dir.parent / "GroneStats-Legacy" / "GRONESTATS 1.0" / paths.league / str(paths.season),
        paths.base_dir.parent / "GroneStats_Legacy" / paths.league / str(paths.season),
        paths.base_dir.parent / "GroneStats-Legacy" / paths.league / str(paths.season),
    ]
    for candidate in raw_candidates:
        try:
            resolved = str(candidate.resolve())
        except FileNotFoundError:
            continue
        if not candidate.exists() or resolved in seen:
            continue
        seen.add(resolved)
        candidates.append(candidate)
    return candidates


def normalize_finished_master(master: pd.DataFrame) -> pd.DataFrame:
    if master.empty:
        return master
    work = master.copy()
    for column in ["match_id", "round_number", "home_id", "away_id", "home_score", "away_score"]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    if {"home_score", "away_score"}.issubset(work.columns):
        work = work.loc[work["home_score"].notna() & work["away_score"].notna()].copy()
    if "match_id" in work.columns:
        work = work.dropna(subset=["match_id"]).copy()
        work["match_id"] = pd.to_numeric(work["match_id"], errors="coerce").astype("Int64")
    if "fecha" in work.columns:
        work["fecha"] = normalize_match_datetime(work["fecha"]).astype("string")
    sort_columns = [column for column in ["round_number", "match_id"] if column in work.columns]
    if sort_columns:
        work = work.sort_values(sort_columns, kind="mergesort")
    if "match_id" in work.columns:
        work = work.drop_duplicates(subset=["match_id"], keep="last")
    return work.reset_index(drop=True)


def resolve_master_sources(paths: PipelinePaths) -> tuple[Path, Path, pd.DataFrame | None]:
    raw_source = paths.legacy_master_raw_path
    if raw_source.exists():
        if paths.legacy_master_clean_path.exists():
            return raw_source, paths.legacy_master_clean_path, None
        if paths.legacy_master_clean_fallback_path.exists():
            return raw_source, paths.legacy_master_clean_fallback_path, None

    for source_dir in candidate_source_season_dirs(paths):
        zero_matches = source_dir / "0_Matches.xlsx"
        if zero_matches.exists():
            clean_target = paths.raw_master_clean_dir / f"Partidos_{paths.league}_{paths.season}_limpio.xlsx"
            return zero_matches, clean_target, normalize_finished_master(pd.read_excel(zero_matches))

    raise FileNotFoundError(
        f"Legacy master sources not found for {paths.league} {paths.season}. "
        f"Checked raw={paths.legacy_master_raw_path} clean={paths.legacy_master_clean_path} fallback={paths.legacy_master_clean_fallback_path}"
    )


def resolve_teams_reference_path(paths: PipelinePaths) -> Path | None:
    for source_dir in candidate_source_season_dirs(paths):
        zero_teams = source_dir / "0_Teams.xlsx"
        if zero_teams.exists():
            return zero_teams
    if paths.teams_reference_path.exists():
        return paths.teams_reference_path
    return None


def should_refresh_fantasy_bridge(paths: PipelinePaths) -> bool:
    if not paths.fantasy_repo_dir.exists() or not paths.fantasy_python_path.exists():
        return False
    if paths.season < 2026:
        return False
    if fantasy_bridge_has_useful_data(paths):
        return True
    return not master_clean_has_rows(paths)


def export_fantasy_bridge_seed(paths: PipelinePaths, logger: PipelineLogger) -> dict[str, Any]:
    if not paths.fantasy_repo_dir.exists():
        raise FileNotFoundError(f"Fantasy repo not found: {paths.fantasy_repo_dir}")
    if not paths.fantasy_python_path.exists():
        raise FileNotFoundError(f"Fantasy Python not found: {paths.fantasy_python_path}")

    script_path = paths.base_dir / "gronestats" / "processing" / "fantasy_bridge_export.py"
    command = [
        str(paths.fantasy_python_path),
        str(script_path),
        "--fantasy-root",
        str(paths.fantasy_repo_dir),
        "--season-year",
        str(paths.season),
        "--master-raw-out",
        str(paths.legacy_master_raw_path),
        "--master-clean-out",
        str(paths.legacy_master_clean_path),
        "--teams-out",
        str(paths.legacy_zero_teams_path),
        "--bridge-dir",
        str(paths.fantasy_bridge_dir),
    ]
    ensure_dir(paths.fantasy_bridge_dir)
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(paths.base_dir),
    )
    stdout = result.stdout.strip()
    if stdout:
        logger.log(stdout)
    stderr = result.stderr.strip()
    if stderr:
        logger.log(stderr)
    return read_json(paths.fantasy_bridge_manifest_path)


def read_fantasy_bridge_manifest(paths: PipelinePaths) -> dict[str, Any]:
    if not paths.fantasy_bridge_manifest_path.exists():
        return {}
    return read_json(paths.fantasy_bridge_manifest_path)


def build_fantasy_bridge_inventory(paths: PipelinePaths) -> pd.DataFrame:
    coverage = read_parquet_safe(paths.fantasy_bridge_dir / "sheet_coverage.parquet")
    manifest = read_fantasy_bridge_manifest(paths)
    if coverage.empty:
        return pd.DataFrame(columns=["match_id", "file_name", "size_bytes", "modified_ns"])

    exported_at = pd.to_datetime(manifest.get("exported_at"), utc=True, errors="coerce")
    if pd.isna(exported_at):
        modified_ns = int(pd.Timestamp.utcnow().value)
    else:
        modified_ns = int(exported_at.value)

    inventory = coverage[["match_id"]].copy()
    inventory["file_name"] = "fantasy_admin_bridge"
    inventory["size_bytes"] = pd.to_numeric(coverage.get("rows_player_stats", 0), errors="coerce").fillna(0).astype(int)
    inventory["modified_ns"] = modified_ns
    inventory["match_id"] = pd.to_numeric(inventory["match_id"], errors="coerce").astype("Int64")
    inventory = inventory.dropna(subset=["match_id"]).copy()
    return inventory.sort_values("match_id", kind="mergesort").reset_index(drop=True)


def collect_fantasy_bridge_staging_tables(
    *,
    bridge_dir: Path,
    match_ids: set[int],
    season: int,
    run_id: str,
    ingested_at: datetime,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    tables = {}
    provider = provider_name_for_source_mode(FANTASY_SOURCE_MODE)
    for table_name in ["player_stats_raw", "team_stats_raw", "average_positions_raw", "heatmaps_raw", "shotmap_raw", "momentum_raw"]:
        frame = read_parquet_safe(bridge_dir / f"{table_name}.parquet")
        if not frame.empty and "match_id" in frame.columns:
            frame = frame.loc[pd.to_numeric(frame["match_id"], errors="coerce").isin(match_ids)].reset_index(drop=True)
        tables[table_name] = append_metadata(
            frame,
            match_id=None,
            season=season,
            source_file="fantasy_admin_bridge",
            source_sheet=table_name,
            run_id=run_id,
            ingested_at=ingested_at,
            provider=provider,
        )

    coverage = read_parquet_safe(bridge_dir / "sheet_coverage.parquet")
    if not coverage.empty and "match_id" in coverage.columns:
        coverage = coverage.loc[pd.to_numeric(coverage["match_id"], errors="coerce").isin(match_ids)].reset_index(drop=True)
    return tables, coverage


def is_pipeline_artifact_path(path: Path, source_dir: Path) -> bool:
    try:
        relative_parts = path.relative_to(source_dir).parts
    except ValueError:
        return False
    return bool(relative_parts and relative_parts[0] in PIPELINE_ARTIFACT_DIRS)


def legacy_split_sheet_name(path: Path) -> str | None:
    if path.name.startswith("0_") or path.name.startswith("Sofascore_"):
        return None
    stem = path.stem
    if "_" not in stem:
        return None
    suffix = stem.split("_", 1)[1]
    return LEGACY_SPLIT_FILE_TO_SHEET.get(suffix)


def collect_legacy_split_workbooks(
    source_dirs: list[Path],
    expected_match_ids: set[int],
) -> tuple[dict[int, dict[str, pd.DataFrame]], int]:
    workbooks: dict[int, dict[str, pd.DataFrame]] = {}
    source_files = 0
    for source_dir in source_dirs:
        for path in sorted(source_dir.rglob("*.xlsx")):
            if is_pipeline_artifact_path(path, source_dir):
                continue
            canonical_sheet_name = legacy_split_sheet_name(path)
            if canonical_sheet_name is None:
                continue
            source_files += 1
            workbook = pd.ExcelFile(path)
            try:
                for sheet_name in workbook.sheet_names:
                    match_id = safe_int(sheet_name)
                    if match_id is None:
                        continue
                    if expected_match_ids and match_id not in expected_match_ids:
                        continue
                    sheet_frame = pd.read_excel(path, sheet_name=sheet_name)
                    workbooks.setdefault(match_id, {})[canonical_sheet_name] = sheet_frame
            finally:
                workbook.close()
    return workbooks, source_files


def write_legacy_split_workbooks(
    *,
    source_dirs: list[Path],
    expected_match_ids: set[int],
    details_dir: Path,
    only_missing: bool,
) -> dict[str, Any]:
    workbook_payloads, source_files = collect_legacy_split_workbooks(source_dirs, expected_match_ids)
    written = 0
    available_match_ids: set[int] = set()
    ordered_sheets = list(dict.fromkeys(LEGACY_SPLIT_FILE_TO_SHEET.values()))

    for match_id, sheets in sorted(workbook_payloads.items()):
        if not sheets:
            continue
        available_match_ids.add(match_id)
        target = details_dir / f"Sofascore_{match_id}.xlsx"
        if only_missing and target.exists():
            continue
        with pd.ExcelWriter(target, engine="openpyxl") as writer:
            for sheet_name in ordered_sheets:
                frame = sheets.get(sheet_name)
                if frame is None:
                    continue
                frame.to_excel(writer, sheet_name=sheet_name, index=False)
        written += 1

    return {
        "available_match_ids": available_match_ids,
        "source_files": source_files,
        "written_workbooks": written,
    }


def find_required_sheet_gaps(details_dir: Path, expected_match_ids: set[int]) -> set[int]:
    workbook_by_match_id: dict[int, Path] = {}
    for workbook_path in details_dir.glob("Sofascore_*.xlsx"):
        match_id = parse_match_id(workbook_path)
        if match_id is None:
            continue
        workbook_by_match_id[match_id] = workbook_path

    missing_required: set[int] = set()
    for match_id in expected_match_ids:
        workbook_path = workbook_by_match_id.get(match_id)
        if workbook_path is None:
            missing_required.add(match_id)
            continue
        try:
            workbook = pd.ExcelFile(workbook_path)
        except Exception:
            missing_required.add(match_id)
            continue
        try:
            for sheet_key in REQUIRED_SHEET_KEYS:
                sheet_name, sheet_frame = load_sheet(workbook, SHEET_ALIASES[sheet_key])
                if sheet_name is None or sheet_frame.empty:
                    missing_required.add(match_id)
                    break
        finally:
            workbook.close()
    return missing_required


def append_metadata(
    frame: pd.DataFrame,
    *,
    match_id: int | None,
    season: int,
    source_file: str | None,
    source_sheet: str | None,
    run_id: str,
    ingested_at: datetime,
    provider: str = PROVIDER_NAME,
) -> pd.DataFrame:
    if frame is None:
        frame = pd.DataFrame()
    work = frame.copy()
    work["provider"] = provider
    work["season"] = season
    if match_id is not None or "match_id" not in work.columns:
        work["match_id"] = match_id
    work["source_file"] = source_file
    work["source_sheet"] = source_sheet
    work["run_id"] = run_id
    work["ingested_at"] = pd.Timestamp(ingested_at)
    return work


def stringify_if_mixed_objects(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    work = frame.copy()

    def _to_string(value: object) -> object:
        if value is None:
            return pd.NA
        try:
            missing = pd.isna(value)
        except Exception:
            missing = False
        if isinstance(missing, bool) and missing:
            return pd.NA
        return str(value)

    for column in work.columns:
        if work[column].dtype != "object":
            continue
        non_null = work[column].dropna()
        if non_null.empty:
            continue
        numeric_candidate = pd.to_numeric(non_null, errors="coerce")
        if numeric_candidate.notna().all():
            work[column] = pd.to_numeric(work[column], errors="coerce")
            continue
        normalized_name = column.casefold().replace(".", "_")
        if "id" in normalized_name:
            work[column] = work[column].map(_to_string)
            continue
        sample = non_null.iloc[:1000]
        value_types = {type(value) for value in sample}
        if len(value_types) <= 1:
            continue
        work[column] = work[column].map(_to_string)
    return work


def coalesce_columns(df: pd.DataFrame, target: str, aliases: list[str]) -> pd.DataFrame:
    work = df.copy()
    available = [column for column in aliases if column in work.columns]
    if not available:
        return work
    if target not in work.columns:
        first_source = available[0]
        work[target] = work[first_source]
        available = [column for column in available if column != first_source]
    for column in available:
        if column == target:
            continue
        work[target] = work[target].combine_first(work[column])
    drop_columns = [column for column in available if column != target]
    return work.drop(columns=drop_columns, errors="ignore")


def safe_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def safe_int(value: object) -> int | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return int(float(numeric))


def safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def normalize_id_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    result = series.astype("string").str.strip()
    result.loc[numeric.notna()] = numeric.loc[numeric.notna()].astype("Int64").astype("string")
    return result.str.replace(".0", "", regex=False)


def normalize_match_datetime(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        dt = pd.to_datetime(series, errors="coerce")
        dt = dt - pd.Timedelta(hours=5)
        return dt.dt.strftime("%d/%m/%Y %H:%M")

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        dt = pd.to_datetime(series, errors="coerce")
        dt = dt - pd.Timedelta(hours=5)
        return dt.dt.strftime("%d/%m/%Y %H:%M")

    max_value = numeric.abs().max()
    if max_value >= 1_000_000_000_000_000:
        unit = "ns"
    elif max_value >= 1_000_000_000_000:
        unit = "ms"
    else:
        unit = "s"

    dt_numeric = pd.to_datetime(numeric, unit=unit, errors="coerce")
    dt_text = pd.to_datetime(series, errors="coerce")
    dt = dt_numeric.copy()
    dt.loc[numeric.isna()] = dt_text.loc[numeric.isna()]
    dt = dt - pd.Timedelta(hours=5)
    return dt.dt.strftime("%d/%m/%Y %H:%M")


def normalize_player_stats_df(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work = coalesce_columns(work, "player_id", ["player_id", "playerId", "id", "player id", "__pid"])
    work = coalesce_columns(work, "name", ["name", "player", "player_name", "__name"])
    work = coalesce_columns(work, "short_name", ["short_name", "shortName", "short name", "shortname", "SHORTNAME"])
    work = coalesce_columns(work, "team_id", ["team_id", "teamId", "teamid", "team id"])
    work = coalesce_columns(work, "position", ["position.1", "position", "pos"])
    work = coalesce_columns(
        work,
        "dateOfBirth",
        ["dateOfBirth", "dateOfBirthTimestamp", "dateofbirthtimestamp", "dateofbirth", "dob", "birthTimestamp"],
    )
    if "dateOfBirth" in work.columns:
        dob_series = work["dateOfBirth"]
        dob_numeric = pd.to_numeric(dob_series, errors="coerce")
        dob_dt_numeric = pd.to_datetime(dob_numeric, unit="s", errors="coerce")
        dob_dt_text = pd.to_datetime(dob_series, errors="coerce")
        dob_dt = dob_dt_numeric.copy()
        dob_dt.loc[dob_numeric.isna()] = dob_dt_text.loc[dob_numeric.isna()]
        work["dateOfBirth"] = dob_dt.dt.strftime("%d/%m/%Y")
        ref = pd.Timestamp("2026-01-01")
        work["age_jan_2026"] = ((ref - dob_dt).dt.days / 365.25).round(1)
    return work


def canonicalize_player_stats(player_stats_raw: pd.DataFrame) -> pd.DataFrame:
    if player_stats_raw.empty:
        return pd.DataFrame()
    work = normalize_player_stats_df(player_stats_raw)
    work = coalesce_columns(work, "match_id", ["match_id", "MATCH_ID", "matchId", "matchid"])
    work = coalesce_columns(work, "minutesplayed", ["minutesplayed", "minutesPlayed", "MINUTESPLAYED", "minutes"])
    work = coalesce_columns(work, "goals", ["goals", "GOALS", "goal"])
    work = coalesce_columns(work, "assists", ["assists", "ASSISTS", "goalassist", "goalAssist", "GOALASSIST"])
    work = coalesce_columns(work, "yellowcards", ["yellowcards", "yellowCards", "YELLOWCARDS"])
    work = coalesce_columns(work, "redcards", ["redcards", "redCards", "REDCARDS"])
    work = coalesce_columns(work, "saves", ["saves", "SAVES", "save"])
    work = coalesce_columns(work, "fouls", ["fouls", "FOULS", "foul"])
    work = coalesce_columns(work, "penaltywon", ["penaltywon", "penaltyWon", "PENALTYWON"])
    work = coalesce_columns(work, "penaltysave", ["penaltysave", "penaltySave", "PENALTYSAVE"])
    work = coalesce_columns(
        work,
        "penaltyconceded",
        ["penaltyconceded", "penaltyConceded", "PENALTYCONCEDED"],
    )
    work = coalesce_columns(work, "rating", ["rating", "RATING"])
    work = coalesce_columns(work, "shirt_number", ["shirt_number", "shirtNumber", "jerseyNumber", "jerseyNumber.1"])
    work = coalesce_columns(work, "substitute", ["substitute"])
    work = coalesce_columns(work, "dateofbirth", ["dateofbirth", "dateOfBirth"])

    for column in [
        "match_id",
        "player_id",
        "team_id",
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
        "shirt_number",
        "rating",
        "age_jan_2026",
    ]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    if "position" in work.columns:
        work["position"] = work["position"].astype("string").str.strip().str.upper()
    if "name" in work.columns:
        work["name"] = work["name"].astype("string").str.strip()
    if "short_name" in work.columns:
        work["short_name"] = work["short_name"].astype("string").str.strip()
    if "substitute" in work.columns:
        work["substitute"] = work["substitute"].astype("boolean")
    return work


def parse_match_id(path: Path) -> int | None:
    stem = path.stem
    if not stem.lower().startswith("sofascore_"):
        return None
    try:
        return int(stem.split("_", 1)[1])
    except (IndexError, ValueError):
        return None


def load_sheet(workbook: pd.ExcelFile, names: list[str]) -> tuple[str | None, pd.DataFrame]:
    for name in names:
        if name in workbook.sheet_names:
            return name, pd.read_excel(workbook, sheet_name=name)
    return None, pd.DataFrame()


def last_non_null(series: pd.Series) -> object:
    for value in reversed(series.tolist()):
        if value is None or pd.isna(value):
            continue
        text = safe_text(value)
        if isinstance(value, str) and text is None:
            continue
        return value
    return pd.NA


def first_present(*values: object) -> object:
    for value in values:
        if value is None or pd.isna(value):
            continue
        return value
    return None


def build_matches_curated(matches_raw: pd.DataFrame) -> pd.DataFrame:
    if matches_raw.empty:
        return pd.DataFrame()
    columns = [
        "match_id",
        "round_number",
        "tournament",
        "season",
        "status",
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
    ]
    work = matches_raw.copy()
    for column in columns:
        if column not in work.columns:
            work[column] = pd.NA
    result = work[columns].copy()
    for column in ["match_id", "round_number", "home_id", "away_id", "home_score", "away_score"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").astype("Int64")
    if "fecha" in result.columns:
        result["fecha"] = normalize_match_datetime(result["fecha"]).astype("string")
    if "round_number" in result.columns:
        result = result.sort_values(["round_number", "match_id"], kind="mergesort")
    else:
        result = result.sort_values(["match_id"], kind="mergesort")
    return result.drop_duplicates(subset=["match_id"], keep="last").reset_index(drop=True)


def build_teams_curated(matches: pd.DataFrame, teams_reference: pd.DataFrame) -> pd.DataFrame:
    base_frames: list[pd.DataFrame] = []
    if not matches.empty:
        if {"home_id", "home"}.issubset(matches.columns):
            base_frames.append(
                matches[["home_id", "home"]]
                .rename(columns={"home_id": "team_id", "home": "short_name"})
                .dropna(subset=["team_id"])
            )
        if {"away_id", "away"}.issubset(matches.columns):
            base_frames.append(
                matches[["away_id", "away"]]
                .rename(columns={"away_id": "team_id", "away": "short_name"})
                .dropna(subset=["team_id"])
            )
    base = (
        pd.concat(base_frames, ignore_index=True)
        .drop_duplicates(subset=["team_id"], keep="last")
        .reset_index(drop=True)
        if base_frames
        else pd.DataFrame(columns=["team_id", "short_name"])
    )
    if base.empty:
        base["team_id"] = pd.Series(dtype="Int64")
    else:
        base["team_id"] = pd.to_numeric(base["team_id"], errors="coerce").astype("Int64")
        base["short_name"] = base["short_name"].astype("string").str.strip()

    if teams_reference.empty:
        if "short_name" in base.columns:
            base["full_name"] = base["short_name"]
        return base.sort_values("short_name", kind="mergesort").reset_index(drop=True)

    work = teams_reference.copy()
    work = coalesce_columns(work, "team_id", ["team_id", "teamId", "id", "ID_Equipo", "ID Equipo"])
    work = coalesce_columns(work, "short_name", ["short_name", "team_name", "team", "name", "equipo", "club", "Nombre_Corto"])
    work = coalesce_columns(work, "full_name", ["full_name", "Nombre_Completo", "Nombre completo"])
    work = coalesce_columns(work, "team_colors", ["team_colors", "team_color", "colors", "color", "Color"])
    work = coalesce_columns(work, "is_altitude_team", ["is_altitude_team", "Es_Equipo_Altura", "Es Equipo Altura"])
    work = coalesce_columns(
        work,
        "competitiveness_level",
        ["competitiveness_level", "Nivel_Competitividad", "Nivel Competitividad"],
    )
    work = coalesce_columns(work, "stadium_id", ["stadium_id", "ID_Estadio_Principal", "ID Estadio Principal"])
    work = coalesce_columns(
        work,
        "stadium_name_city",
        ["stadium_name_city", "Nombre_Estadio / Ciudad", "Nombre Estadio / Ciudad", "Nombre_Estadio_Ciudad"],
    )
    work = coalesce_columns(work, "province", ["province", "Provincia_Equipo", "Provincia Equipo"])
    work = coalesce_columns(work, "department", ["department", "Departamento"])
    work = coalesce_columns(work, "region", ["region", "Región", "Region"])
    keep = [
        column
        for column in [
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
        if column in work.columns
    ]
    reference = work[keep].copy()
    reference["team_id"] = pd.to_numeric(reference["team_id"], errors="coerce").astype("Int64")
    if not reference.empty:
        aggregations = {column: last_non_null for column in reference.columns if column != "team_id"}
        reference = (
            reference.groupby("team_id", as_index=False)
            .agg(aggregations)
            .sort_values("team_id", kind="mergesort")
            .reset_index(drop=True)
        )
    merged = base.merge(reference, on="team_id", how="outer", suffixes=("", "_ref"))
    if "short_name_ref" in merged.columns:
        merged["short_name"] = merged["short_name_ref"].combine_first(merged["short_name"])
        merged = merged.drop(columns=["short_name_ref"])
    if "full_name" not in merged.columns:
        merged["full_name"] = merged.get("short_name")
    merged["full_name"] = merged["full_name"].combine_first(merged["short_name"])
    merged["short_name"] = merged["short_name"].astype("string").str.strip()
    return merged.drop_duplicates(subset=["team_id"], keep="last").sort_values("short_name", kind="mergesort").reset_index(drop=True)


def build_player_match_curated(player_stats_raw: pd.DataFrame) -> pd.DataFrame:
    work = canonicalize_player_stats(player_stats_raw)
    if work.empty:
        return pd.DataFrame()
    columns = [
        "match_id",
        "player_id",
        "name",
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
        "rating",
    ]
    for column in columns:
        if column not in work.columns:
            work[column] = pd.NA
    result = work[columns].copy()
    for column in [
        "match_id",
        "player_id",
        "team_id",
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
        "rating",
    ]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["position"] = result["position"].astype("string").str.strip().str.upper()
    result["name"] = result["name"].astype("string").str.strip()
    result = result.dropna(subset=["match_id", "player_id"]).copy()
    result["match_id"] = result["match_id"].astype("Int64")
    result["player_id"] = result["player_id"].astype("Int64")
    result["team_id"] = result["team_id"].astype("Int64")
    result = result.sort_values(["match_id", "team_id", "name"], kind="mergesort")
    return result.reset_index(drop=True)


def build_player_totals_full_season(player_match: pd.DataFrame) -> pd.DataFrame:
    if player_match.empty:
        return pd.DataFrame()
    work = player_match.copy()
    for column in ["goals", "assists", "saves", "fouls", "minutesplayed", "penaltywon", "penaltysave", "penaltyconceded"]:
        if column not in work.columns:
            work[column] = 0
        work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0)
    totals = (
        work.dropna(subset=["player_id"])
        .groupby("player_id", as_index=False)
        .agg(
            goals=("goals", "sum"),
            assists=("assists", "sum"),
            saves=("saves", "sum"),
            fouls=("fouls", "sum"),
            minutesplayed=("minutesplayed", "sum"),
            penaltywon=("penaltywon", "sum"),
            penaltysave=("penaltysave", "sum"),
            penaltyconceded=("penaltyconceded", "sum"),
            matches_played=("match_id", "nunique"),
        )
        .sort_values("player_id", kind="mergesort")
    )
    totals["player_id"] = pd.to_numeric(totals["player_id"], errors="coerce").astype("Int64")
    return totals.reset_index(drop=True)


def build_player_identity(player_stats_raw: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    work = canonicalize_player_stats(player_stats_raw)
    if work.empty:
        return pd.DataFrame()
    match_dates = matches[["match_id", "fecha"]].copy() if {"match_id", "fecha"}.issubset(matches.columns) else pd.DataFrame()
    if not match_dates.empty:
        match_dates["fecha_dt"] = pd.to_datetime(match_dates["fecha"], format="%d/%m/%Y %H:%M", errors="coerce")
        work = work.merge(match_dates[["match_id", "fecha_dt"]], on="match_id", how="left")
    else:
        work["fecha_dt"] = pd.NaT
    work = work.dropna(subset=["player_id"]).copy()
    work["player_id"] = pd.to_numeric(work["player_id"], errors="coerce").astype("Int64")
    work["team_id"] = pd.to_numeric(work["team_id"], errors="coerce").astype("Int64")
    work = work.sort_values(["player_id", "fecha_dt", "match_id"], kind="mergesort")
    grouped = (
        work.groupby("player_id", as_index=False)
        .agg(
            name=("name", last_non_null),
            short_name=("short_name", last_non_null),
            position=("position", last_non_null),
            team_id=("team_id", last_non_null),
            dateofbirth=("dateofbirth", last_non_null),
            age_jan_2026=("age_jan_2026", last_non_null),
            last_match_id=("match_id", "last"),
            last_seen_at=("fecha_dt", "last"),
        )
        .sort_values(["name", "player_id"], kind="mergesort")
        .reset_index(drop=True)
    )
    grouped["position"] = grouped["position"].astype("string").str.strip().str.upper()
    grouped["name"] = grouped["name"].astype("string").str.strip()
    grouped["short_name"] = grouped["short_name"].astype("string").str.strip()
    grouped["team_id"] = pd.to_numeric(grouped["team_id"], errors="coerce").astype("Int64")
    grouped["last_match_id"] = pd.to_numeric(grouped["last_match_id"], errors="coerce").astype("Int64")
    return grouped


def build_players_curated(player_identity: pd.DataFrame) -> pd.DataFrame:
    if player_identity.empty:
        return pd.DataFrame()
    columns = [column for column in ["player_id", "name", "short_name", "position", "team_id", "dateofbirth", "age_jan_2026"] if column in player_identity.columns]
    return player_identity[columns].copy().sort_values(["name", "player_id"], kind="mergesort").reset_index(drop=True)


def build_player_lookup_by_match(player_stats_raw: pd.DataFrame) -> dict[int, dict[str, dict[object, dict[str, object]]]]:
    work = canonicalize_player_stats(player_stats_raw)
    if work.empty:
        return {}
    lookup: dict[int, dict[str, dict[object, dict[str, object]]]] = {}
    for match_id, subset in work.dropna(subset=["match_id"]).groupby("match_id", dropna=True):
        by_id: dict[object, dict[str, object]] = {}
        by_name: dict[object, dict[str, object]] = {}
        for _, row in subset.iterrows():
            player_id = safe_int(row.get("player_id"))
            name = safe_text(row.get("name"))
            payload = {
                "player_id": player_id,
                "team_id": safe_int(row.get("team_id")),
                "name": name,
                "short_name": safe_text(row.get("short_name")),
                "position": safe_text(row.get("position")),
                "shirt_number": safe_int(row.get("shirt_number")),
                "is_starter": False if bool(row.get("substitute")) else True if pd.notna(row.get("substitute")) else None,
            }
            if player_id is not None:
                by_id[player_id] = payload
            if name:
                by_name[name.casefold()] = payload
        lookup[int(match_id)] = {"by_id": by_id, "by_name": by_name}
    return lookup


def parse_heatmap_payload(value: object) -> tuple[int | None, list[tuple[float, float]]]:
    if value is None or pd.isna(value):
        return None, []
    payload = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None, []
        try:
            payload = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return None, []
    if not isinstance(payload, dict):
        return None, []
    player_id = safe_int(payload.get("id"))
    points: list[tuple[float, float]] = []
    for pair in payload.get("heatmap", []) or []:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        x = safe_float(pair[0])
        y = safe_float(pair[1])
        if x is None or y is None:
            continue
        points.append((x, y))
    return player_id, points


def build_average_positions_curated(
    average_positions_raw: pd.DataFrame,
    player_stats_raw: pd.DataFrame,
    teams: pd.DataFrame,
) -> pd.DataFrame:
    if average_positions_raw.empty:
        return pd.DataFrame()
    team_lookup = {}
    if not teams.empty and {"team_id", "short_name"}.issubset(teams.columns):
        team_lookup = (
            teams[["team_id", "short_name"]]
            .dropna(subset=["team_id"])
            .drop_duplicates(subset=["team_id"])
            .set_index("team_id")["short_name"]
            .to_dict()
        )
    player_lookup = build_player_lookup_by_match(player_stats_raw)
    rows: list[dict[str, object]] = []
    for _, row in average_positions_raw.iterrows():
        match_id = safe_int(row.get("match_id"))
        match_lookup = player_lookup.get(match_id or -1, {"by_id": {}, "by_name": {}})
        player_id = safe_int(row.get("id")) or safe_int(row.get("player_id"))
        name = safe_text(row.get("name")) or safe_text(row.get("shortName"))
        identity = None
        if player_id is not None:
            identity = match_lookup["by_id"].get(player_id)
        if identity is None and name:
            identity = match_lookup["by_name"].get(name.casefold())
        final_player_id = player_id or (identity or {}).get("player_id")
        team_id = (identity or {}).get("team_id")
        raw_team_name = safe_text(row.get("team"))
        team_name = raw_team_name or team_lookup.get(team_id)
        rows.append(
            {
                "match_id": match_id,
                "player_id": final_player_id,
                "team_id": team_id,
                "team_name": team_name,
                "name": name or (identity or {}).get("name"),
                "shirt_number": safe_int(row.get("jerseyNumber")) or (identity or {}).get("shirt_number"),
                "position": safe_text(row.get("position")) or (identity or {}).get("position"),
                "average_x": first_present(safe_float(row.get("averageX")), safe_float(row.get("average_x"))),
                "average_y": first_present(safe_float(row.get("averageY")), safe_float(row.get("average_y"))),
                "points_count": first_present(safe_int(row.get("pointsCount")), safe_int(row.get("points_count"))),
                "is_starter": (identity or {}).get("is_starter"),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for column in ["match_id", "player_id", "team_id", "shirt_number", "points_count"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    for column in ["average_x", "average_y"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["is_starter"] = frame["is_starter"].astype("boolean")
    frame["position"] = frame["position"].astype("string").str.strip().str.upper()
    frame["name"] = frame["name"].astype("string").str.strip()
    frame["team_name"] = frame["team_name"].astype("string").str.strip()
    frame = frame.dropna(subset=["match_id", "player_id", "average_x", "average_y"])
    frame = frame.drop_duplicates(subset=["match_id", "player_id"], keep="last")
    frame = frame.sort_values(["match_id", "team_name", "shirt_number", "name"], kind="mergesort")
    return frame.reset_index(drop=True)


def build_heatmap_points_curated(
    heatmaps_raw: pd.DataFrame,
    player_stats_raw: pd.DataFrame,
    teams: pd.DataFrame,
) -> pd.DataFrame:
    if heatmaps_raw.empty:
        return pd.DataFrame()
    player_lookup = build_player_lookup_by_match(player_stats_raw)
    team_lookup = {}
    if not teams.empty and {"team_id", "short_name"}.issubset(teams.columns):
        team_lookup = (
            teams[["team_id", "short_name"]]
            .dropna(subset=["team_id"])
            .drop_duplicates(subset=["team_id"])
            .set_index("team_id")["short_name"]
            .to_dict()
        )
    rows: list[dict[str, object]] = []
    for _, row in heatmaps_raw.iterrows():
        match_id = safe_int(row.get("match_id"))
        name = safe_text(row.get("player")) or safe_text(row.get("name"))
        parsed_player_id, points = parse_heatmap_payload(row.get("heatmap"))
        match_lookup = player_lookup.get(match_id or -1, {"by_id": {}, "by_name": {}})
        identity = None
        if parsed_player_id is not None:
            identity = match_lookup["by_id"].get(parsed_player_id)
        if identity is None and name:
            identity = match_lookup["by_name"].get(name.casefold())
        final_player_id = parsed_player_id or (identity or {}).get("player_id")
        team_id = (identity or {}).get("team_id")
        team_name = team_lookup.get(team_id)
        final_name = name or (identity or {}).get("name")
        for x, y in points:
            rows.append(
                {
                    "match_id": match_id,
                    "player_id": final_player_id,
                    "team_id": team_id,
                    "team_name": team_name,
                    "name": final_name,
                    "x": x,
                    "y": y,
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for column in ["match_id", "player_id", "team_id"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    for column in ["x", "y"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["name"] = frame["name"].astype("string").str.strip()
    frame["team_name"] = frame["team_name"].astype("string").str.strip()
    frame = frame.dropna(subset=["match_id", "player_id", "x", "y"])
    frame = frame.sort_values(["match_id", "player_id"], kind="mergesort")
    return frame.reset_index(drop=True)


def build_shot_events_curated(shotmap_raw: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    if shotmap_raw.empty:
        return pd.DataFrame()
    work = shotmap_raw.copy()
    work = coalesce_columns(work, "shot_id", ["shot_id", "id"])
    work = coalesce_columns(work, "player_id", ["player_id", "id.1", "playerId"])
    work = coalesce_columns(work, "is_home", ["is_home", "isHome"])
    work = coalesce_columns(work, "shot_type", ["shot_type", "shotType"])
    work = coalesce_columns(work, "body_part", ["body_part", "bodyPart"])
    work = coalesce_columns(work, "goal_mouth_location", ["goal_mouth_location", "goalMouthLocation"])
    work = coalesce_columns(work, "goal_mouth_coordinates", ["goal_mouth_coordinates", "goalMouthCoordinates"])
    work = coalesce_columns(work, "added_time", ["added_time", "addedTime"])
    work = coalesce_columns(work, "time_seconds", ["time_seconds", "timeSeconds"])
    work = coalesce_columns(work, "incident_type", ["incident_type", "incidentType"])
    work = coalesce_columns(work, "block_coordinates", ["block_coordinates", "blockCoordinates"])
    work = coalesce_columns(work, "goal_type", ["goal_type", "goalType"])
    work = coalesce_columns(work, "short_name", ["short_name", "shortName"])
    work = coalesce_columns(work, "jersey_number", ["jersey_number", "jerseyNumber"])
    columns = [
        "match_id",
        "shot_id",
        "player_id",
        "is_home",
        "shot_type",
        "situation",
        "body_part",
        "goal_mouth_location",
        "goal_mouth_coordinates",
        "time",
        "added_time",
        "time_seconds",
        "incident_type",
        "block_coordinates",
        "goal_type",
        "name",
        "short_name",
        "position",
        "jersey_number",
        "x",
        "y",
        "z",
    ]
    for column in columns:
        if column not in work.columns:
            work[column] = pd.NA
    result = work[columns].copy()
    for column in ["match_id", "shot_id", "player_id", "time", "added_time", "time_seconds", "jersey_number", "x", "y", "z"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["is_home"] = result["is_home"].astype("boolean")
    result["position"] = result["position"].astype("string").str.strip().str.upper()
    result["name"] = result["name"].astype("string").str.strip()
    result["short_name"] = result["short_name"].astype("string").str.strip()
    result["match_id"] = result["match_id"].astype("Int64")
    result["player_id"] = result["player_id"].astype("Int64")
    match_lookup = matches[["match_id", "home_id", "away_id", "home", "away"]].copy() if {"match_id", "home_id", "away_id", "home", "away"}.issubset(matches.columns) else pd.DataFrame()
    if not match_lookup.empty:
        result = result.merge(match_lookup, on="match_id", how="left")
        result["is_home_resolved"] = result["is_home"].fillna(False).astype(bool)
        result["team_id"] = result.apply(
            lambda row: row.get("home_id") if row.get("is_home_resolved") else row.get("away_id"),
            axis=1,
        )
        result["team_name"] = result.apply(
            lambda row: row.get("home") if row.get("is_home_resolved") else row.get("away"),
            axis=1,
        )
        result = result.drop(columns=["home_id", "away_id", "home", "away", "is_home_resolved"], errors="ignore")
        result["team_id"] = pd.to_numeric(result["team_id"], errors="coerce").astype("Int64")
    result = result.sort_values(["match_id", "time_seconds", "shot_id"], kind="mergesort")
    return result.reset_index(drop=True)


def build_match_momentum_curated(momentum_raw: pd.DataFrame) -> pd.DataFrame:
    if momentum_raw.empty:
        return pd.DataFrame()
    work = momentum_raw.copy()
    result = work[[column for column in ["match_id", "minute", "value"] if column in work.columns]].copy()
    result["match_id"] = pd.to_numeric(result["match_id"], errors="coerce").astype("Int64")
    result["minute"] = pd.to_numeric(result["minute"], errors="coerce")
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    result["dominant_side"] = result["value"].map(lambda value: "home" if value > 0 else "away" if value < 0 else "neutral")
    result = result.sort_values(["match_id", "minute"], kind="mergesort")
    return result.reset_index(drop=True)


def build_team_stats_curated(team_stats_raw: pd.DataFrame) -> pd.DataFrame:
    if team_stats_raw.empty:
        return pd.DataFrame()
    work = team_stats_raw.copy()
    rename_map = {
        "name": "NAME",
        "home": "HOME",
        "away": "AWAY",
        "compareCode": "COMPARECODE",
        "statisticsType": "STATISTICSTYPE",
        "valueType": "VALUETYPE",
        "homeValue": "HOMEVALUE",
        "awayValue": "AWAYVALUE",
        "renderType": "RENDERTYPE",
        "key": "KEY",
        "period": "PERIOD",
        "group": "GROUP",
        "homeTotal": "HOMETOTAL",
        "awayTotal": "AWAYTOTAL",
        "match_id": "MATCH_ID",
    }
    work = work.rename(columns={source: target for source, target in rename_map.items() if source in work.columns})
    columns = [
        "NAME",
        "HOME",
        "AWAY",
        "COMPARECODE",
        "STATISTICSTYPE",
        "VALUETYPE",
        "HOMEVALUE",
        "AWAYVALUE",
        "RENDERTYPE",
        "KEY",
        "PERIOD",
        "GROUP",
        "HOMETOTAL",
        "AWAYTOTAL",
        "MATCH_ID",
    ]
    for column in columns:
        if column not in work.columns:
            work[column] = pd.NA
    result = work[columns].copy()
    for column in ["COMPARECODE", "HOMEVALUE", "AWAYVALUE", "RENDERTYPE", "HOMETOTAL", "AWAYTOTAL", "MATCH_ID"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["MATCH_ID"] = result["MATCH_ID"].astype("Int64")
    result = result.sort_values(["MATCH_ID", "GROUP", "KEY"], kind="mergesort")
    return result.reset_index(drop=True)


def build_master_inventory(master: pd.DataFrame) -> pd.DataFrame:
    if master.empty or "match_id" not in master.columns:
        return pd.DataFrame(columns=["match_id", "row_hash"])
    rows: list[dict[str, object]] = []
    for _, row in master.iterrows():
        match_id = safe_int(row.get("match_id"))
        if match_id is None:
            continue
        payload = {key: json_default(value) for key, value in row.dropna().to_dict().items()}
        row_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        rows.append({"match_id": match_id, "row_hash": row_hash})
    return pd.DataFrame(rows).sort_values("match_id", kind="mergesort").reset_index(drop=True)


def build_raw_inventory(details_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for workbook in sorted(details_dir.glob("Sofascore_*.xlsx")):
        match_id = parse_match_id(workbook)
        if match_id is None:
            continue
        stat = workbook.stat()
        rows.append(
            {
                "match_id": match_id,
                "file_name": workbook.name,
                "size_bytes": stat.st_size,
                "modified_ns": getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["match_id", "file_name", "size_bytes", "modified_ns"])
    return pd.DataFrame(rows).sort_values("match_id", kind="mergesort").reset_index(drop=True)


def resolve_changed_match_ids(
    current_raw_inventory: pd.DataFrame,
    previous_raw_inventory: pd.DataFrame,
    current_master_inventory: pd.DataFrame,
    previous_master_inventory: pd.DataFrame,
) -> set[int]:
    changed: set[int] = set()

    def compare_frames(current: pd.DataFrame, previous: pd.DataFrame, columns: list[str]) -> set[int]:
        if current.empty and previous.empty:
            return set()
        if previous.empty:
            return set(pd.to_numeric(current.get("match_id", pd.Series(dtype="int64")), errors="coerce").dropna().astype(int).tolist())
        current_indexed = current.set_index("match_id")[columns] if not current.empty else pd.DataFrame(columns=columns)
        previous_indexed = previous.set_index("match_id")[columns] if not previous.empty else pd.DataFrame(columns=columns)
        all_match_ids = set(current_indexed.index.tolist()) | set(previous_indexed.index.tolist())
        result: set[int] = set()
        for match_id in all_match_ids:
            if match_id not in current_indexed.index or match_id not in previous_indexed.index:
                result.add(int(match_id))
                continue
            left = current_indexed.loc[match_id].to_dict()
            right = previous_indexed.loc[match_id].to_dict()
            if left != right:
                result.add(int(match_id))
        return result

    changed |= compare_frames(current_raw_inventory, previous_raw_inventory, ["file_name", "size_bytes", "modified_ns"])
    changed |= compare_frames(current_master_inventory, previous_master_inventory, ["row_hash"])
    return changed


def flatten_master_to_matches_raw(
    master: pd.DataFrame,
    *,
    season: int,
    source_file: str,
    run_id: str,
    ingested_at: datetime,
    provider: str = PROVIDER_NAME,
) -> pd.DataFrame:
    if master.empty:
        return pd.DataFrame()
    return append_metadata(
        master,
        match_id=None,
        season=season,
        source_file=source_file,
        source_sheet="master_clean",
        run_id=run_id,
        ingested_at=ingested_at,
        provider=provider,
    )


def empty_sheet_coverage_row(match_id: int, source_file: str | None = None, error: str | None = None) -> dict[str, object]:
    row: dict[str, object] = {
        "match_id": match_id,
        "source_file": source_file,
        "workbook_exists": bool(source_file),
        "read_error": error,
    }
    for sheet_key in SHEET_ALIASES:
        row[f"has_{sheet_key}"] = False
        row[f"rows_{sheet_key}"] = 0
    return row


def collect_workbook_staging_tables(
    *,
    details_dir: Path,
    match_ids: set[int],
    season: int,
    run_id: str,
    ingested_at: datetime,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    by_match_id: dict[int, Path] = {}
    for workbook in details_dir.glob("Sofascore_*.xlsx"):
        match_id = parse_match_id(workbook)
        if match_id is not None:
            by_match_id[match_id] = workbook

    frames: dict[str, list[pd.DataFrame]] = {
        "player_stats_raw": [],
        "team_stats_raw": [],
        "average_positions_raw": [],
        "heatmaps_raw": [],
        "shotmap_raw": [],
        "momentum_raw": [],
    }
    coverage_rows: list[dict[str, object]] = []

    for match_id in sorted(match_ids):
        workbook_path = by_match_id.get(match_id)
        if workbook_path is None:
            coverage_rows.append(empty_sheet_coverage_row(match_id))
            continue
        coverage = empty_sheet_coverage_row(match_id, workbook_path.name)
        try:
            workbook = pd.ExcelFile(workbook_path)
        except Exception as exc:
            coverage_rows.append(empty_sheet_coverage_row(match_id, workbook_path.name, str(exc)))
            continue
        try:
            for sheet_key, aliases in SHEET_ALIASES.items():
                sheet_name, sheet_frame = load_sheet(workbook, aliases)
                has_rows = sheet_name is not None and not sheet_frame.empty
                coverage[f"has_{sheet_key}"] = bool(has_rows)
                coverage[f"rows_{sheet_key}"] = int(len(sheet_frame)) if sheet_name is not None else 0
                if sheet_name is None:
                    continue
                stage_table = f"{sheet_key}_raw"
                if stage_table not in frames:
                    continue
                if sheet_frame.empty:
                    continue
                frames[stage_table].append(
                    append_metadata(
                        sheet_frame,
                        match_id=match_id,
                        season=season,
                        source_file=workbook_path.name,
                        source_sheet=sheet_name,
                        run_id=run_id,
                        ingested_at=ingested_at,
                    )
                )
        finally:
            workbook.close()
        coverage_rows.append(coverage)

    staging_tables = {
        table_name: pd.concat(table_frames, ignore_index=True) if table_frames else pd.DataFrame()
        for table_name, table_frames in frames.items()
    }
    coverage = pd.DataFrame(coverage_rows).sort_values("match_id", kind="mergesort").reset_index(drop=True)
    return staging_tables, coverage


def merge_incremental_frame(existing: pd.DataFrame, new: pd.DataFrame, changed_match_ids: set[int]) -> pd.DataFrame:
    if existing.empty:
        return new.reset_index(drop=True)
    if "match_id" not in existing.columns:
        return new.reset_index(drop=True)
    kept = existing.loc[~existing["match_id"].isin(changed_match_ids)].copy()
    if new.empty:
        return kept.reset_index(drop=True)
    return pd.concat([kept, new], ignore_index=True).reset_index(drop=True)


def sort_table(table_name: str, frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    if table_name == "matches_raw":
        sort_columns = [column for column in ["match_id"] if column in frame.columns]
    elif table_name == "sheet_coverage":
        sort_columns = ["match_id"]
    elif table_name == "player_stats_raw":
        sort_columns = [column for column in ["match_id", "team_id", "player_id", "name"] if column in frame.columns]
    elif table_name == "team_stats_raw":
        sort_columns = [column for column in ["match_id", "group", "key", "name"] if column in frame.columns]
    elif table_name == "average_positions_raw":
        sort_columns = [column for column in ["match_id", "team", "jerseyNumber", "name"] if column in frame.columns]
    elif table_name == "heatmaps_raw":
        sort_columns = [column for column in ["match_id", "player"] if column in frame.columns]
    elif table_name == "shotmap_raw":
        sort_columns = [column for column in ["match_id", "timeSeconds", "id"] if column in frame.columns]
    elif table_name == "momentum_raw":
        sort_columns = [column for column in ["match_id", "minute"] if column in frame.columns]
    else:
        sort_columns = [column for column in ["match_id"] if column in frame.columns]
    if not sort_columns:
        return frame.reset_index(drop=True)
    return frame.sort_values(sort_columns, kind="mergesort").reset_index(drop=True)


def load_previous_run_artifact(paths: PipelinePaths, artifact_name: str) -> pd.DataFrame:
    candidates = sorted(
        [run_dir for run_dir in paths.raw_runs_dir.glob("*") if run_dir.is_dir() and run_dir.name != paths.run_id],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for run_dir in candidates:
        artifact_path = run_dir / artifact_name
        if artifact_path.exists():
            return pd.read_parquet(artifact_path)
    return pd.DataFrame()


def reference_dataset_dir(paths: PipelinePaths) -> Path | None:
    if paths.current_dir.exists() and any(paths.current_dir.glob("*.parquet")):
        return paths.current_dir
    if paths.legacy_normalized_dir.exists() and any(paths.legacy_normalized_dir.glob("*.parquet")):
        return paths.legacy_normalized_dir
    return None


def build_dataset_diff(reference_dir: Path | None, candidate_dir: Path) -> dict[str, Any]:
    if reference_dir is None or not reference_dir.exists():
        return {}
    metrics: dict[str, Any] = {}
    for table_name in ["matches", "teams", "players", "player_match", "team_stats", "average_positions", "heatmap_points"]:
        reference_path = reference_dir / f"{table_name}.parquet"
        candidate_path = candidate_dir / f"{table_name}.parquet"
        if not reference_path.exists() or not candidate_path.exists():
            continue
        before = pd.read_parquet(reference_path)
        after = pd.read_parquet(candidate_path)
        delta: dict[str, Any] = {
            "rows_before": int(len(before)),
            "rows_after": int(len(after)),
            "delta_rows": int(len(after) - len(before)),
        }
        if table_name == "matches":
            before_home = pd.to_numeric(before.get("home_score", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum()
            after_home = pd.to_numeric(after.get("home_score", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum()
            before_away = pd.to_numeric(before.get("away_score", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum()
            after_away = pd.to_numeric(after.get("away_score", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum()
            delta["home_goals_delta"] = int(after_home - before_home)
            delta["away_goals_delta"] = int(after_away - before_away)
        elif table_name == "player_match":
            for column in ["goals", "assists", "minutesplayed"]:
                before_series = pd.to_numeric(before.get(column, before.get(column.upper(), pd.Series(dtype="float64"))), errors="coerce").fillna(0)
                after_series = pd.to_numeric(after.get(column, after.get(column.upper(), pd.Series(dtype="float64"))), errors="coerce").fillna(0)
                delta[f"{column}_delta"] = float(after_series.sum() - before_series.sum())
        if any(value != 0 for key, value in delta.items() if key.startswith("delta") or key.endswith("_delta")):
            metrics[table_name] = delta
    return metrics


def finished_match_ids_from_master(master_matches: pd.DataFrame) -> set[int]:
    if master_matches.empty or "match_id" not in master_matches.columns:
        return set()
    work = master_matches.copy()
    match_ids = pd.to_numeric(work["match_id"], errors="coerce")
    status = work.get("status", pd.Series(index=work.index, dtype="object")).astype("string").str.strip().str.lower()
    home_score = pd.to_numeric(work.get("home_score", pd.Series(index=work.index, dtype="float64")), errors="coerce")
    away_score = pd.to_numeric(work.get("away_score", pd.Series(index=work.index, dtype="float64")), errors="coerce")
    has_score = home_score.notna() & away_score.notna()
    is_finished = has_score | status.isin({"finalizado", "finished", "ended"})
    return set(match_ids.loc[is_finished].dropna().astype(int).tolist())


def validate_dataset_contract(
    *,
    dataset_dir: Path,
    master_matches: pd.DataFrame,
    staging_dir: Path | None,
    reference_dir: Path | None,
    season: int | None = None,
    source_mode: str = "sofascore",
) -> dict[str, Any]:
    blocking_errors: list[str] = []
    warnings: list[str] = []

    tables = {table_name: read_parquet_safe(dataset_dir / f"{table_name}.parquet") for table_name in REQUIRED_CURATED_TABLES}
    missing_tables = [table_name for table_name, frame in tables.items() if frame.empty and not (dataset_dir / f"{table_name}.parquet").exists()]
    if missing_tables:
        blocking_errors.append(f"Missing curated tables: {', '.join(missing_tables)}")

    matches = tables["matches"]
    teams = tables["teams"]
    players = tables["players"]
    player_match = tables["player_match"]
    average_positions = tables["average_positions"]
    heatmap_points = tables["heatmap_points"]

    expected_match_ids = set(pd.to_numeric(master_matches.get("match_id", pd.Series(dtype="float64")), errors="coerce").dropna().astype(int).tolist())
    finished_match_ids = finished_match_ids_from_master(master_matches)
    curated_match_ids = set(pd.to_numeric(matches.get("match_id", pd.Series(dtype="float64")), errors="coerce").dropna().astype(int).tolist())
    missing_curated_matches = sorted(expected_match_ids - curated_match_ids)
    if missing_curated_matches:
        blocking_errors.append(
            f"Master matches missing from curated matches: {len(missing_curated_matches)} ({', '.join(map(str, missing_curated_matches[:10]))})"
        )

    if source_mode == FANTASY_SOURCE_MODE:
        if matches.empty:
            blocking_errors.append("Fantasy admin bridge has no curated matches yet; publish is blocked until fixtures exist.")
        elif player_match.empty:
            warnings.append(
                "Fantasy admin bridge has no player_match rows yet; release can publish as schedule-only until admin stats are loaded."
            )

    if not player_match.empty:
        player_match_ids = set(pd.to_numeric(player_match.get("match_id", pd.Series(dtype="float64")), errors="coerce").dropna().astype(int).tolist())
        orphan_match_ids = sorted(player_match_ids - curated_match_ids)
        if orphan_match_ids:
            blocking_errors.append(
                f"player_match has orphan match_ids: {len(orphan_match_ids)} ({', '.join(map(str, orphan_match_ids[:10]))})"
            )
        team_ids = set(pd.to_numeric(teams.get("team_id", pd.Series(dtype="float64")), errors="coerce").dropna().astype(int).tolist())
        unresolved_team_rows = player_match[
            player_match["team_id"].isna()
            | ~pd.to_numeric(player_match["team_id"], errors="coerce").fillna(-1).astype(int).isin(team_ids)
        ]
        if not unresolved_team_rows.empty:
            unresolved_ids = (
                unresolved_team_rows[["match_id", "player_id", "team_id"]]
                .head(10)
                .astype("string")
                .to_dict(orient="records")
            )
            blocking_errors.append(
                f"player_match has unresolved team_id rows: {len(unresolved_team_rows)} ({unresolved_ids})"
            )

    player_ids = set(pd.to_numeric(players.get("player_id", pd.Series(dtype="float64")), errors="coerce").dropna().astype(int).tolist())
    for table_name, frame in [("average_positions", average_positions), ("heatmap_points", heatmap_points)]:
        if frame.empty:
            continue
        frame_match_ids = set(pd.to_numeric(frame.get("match_id", pd.Series(dtype="float64")), errors="coerce").dropna().astype(int).tolist())
        orphan_matches = sorted(frame_match_ids - curated_match_ids)
        if orphan_matches:
            blocking_errors.append(
                f"{table_name} has orphan match_ids: {len(orphan_matches)} ({', '.join(map(str, orphan_matches[:10]))})"
            )
        frame_player_ids = set(pd.to_numeric(frame.get("player_id", pd.Series(dtype="float64")), errors="coerce").dropna().astype(int).tolist())
        orphan_players = sorted(frame_player_ids - player_ids)
        if orphan_players:
            blocking_errors.append(
                f"{table_name} has orphan player_ids: {len(orphan_players)} ({', '.join(map(str, orphan_players[:10]))})"
            )

    timestamp_paths = [dataset_dir / f"{table_name}.parquet" for table_name in CORE_DASHBOARD_TABLES if (dataset_dir / f"{table_name}.parquet").exists()]
    if timestamp_paths:
        mtimes = [path.stat().st_mtime for path in timestamp_paths]
        timestamp_span_seconds = max(mtimes) - min(mtimes)
        if timestamp_span_seconds > 600:
            blocking_errors.append(
                f"Base table timestamp span is too large ({timestamp_span_seconds:.1f}s), indicating mixed releases."
            )
    else:
        timestamp_span_seconds = None

    coverage = read_parquet_safe(staging_dir / "sheet_coverage.parquet") if staging_dir is not None else pd.DataFrame()
    optional_backfill_report = load_optional_backfill_report_for_staging(staging_dir)
    if not coverage.empty:
        current_season_partial_mode = (
            source_mode != FANTASY_SOURCE_MODE
            and season is not None
            and int(season) == utc_now().year
        )
        if source_mode == FANTASY_SOURCE_MODE:
            strict_required_sheet_keys: tuple[str, ...] = ()
            relaxed_required_sheet_keys = ("team_stats", "average_positions")
            if finished_match_ids:
                finished_coverage = coverage.loc[pd.to_numeric(coverage.get("match_id"), errors="coerce").isin(finished_match_ids)].copy()
                missing_player_stats_finished = (
                    finished_coverage.loc[~finished_coverage["has_player_stats"], "match_id"].dropna().astype(int).tolist()
                    if "has_player_stats" in finished_coverage.columns
                    else sorted(finished_match_ids)
                )
                if missing_player_stats_finished:
                    blocking_errors.append(
                        f"Missing required finished-match sheet 'player_stats' for {len(missing_player_stats_finished)} matches "
                        f"({', '.join(map(str, missing_player_stats_finished[:10]))})"
                    )
        elif current_season_partial_mode:
            strict_required_sheet_keys = ()
            relaxed_required_sheet_keys = REQUIRED_SHEET_KEYS
        else:
            strict_required_sheet_keys = REQUIRED_SHEET_KEYS if season is None or season >= 2024 else ()
            relaxed_required_sheet_keys = tuple(
                sheet_key for sheet_key in REQUIRED_SHEET_KEYS if sheet_key not in strict_required_sheet_keys
            )
        for sheet_key in strict_required_sheet_keys:
            missing_sheet_matches = coverage.loc[~coverage[f"has_{sheet_key}"], "match_id"].dropna().astype(int).tolist()
            if missing_sheet_matches:
                suffix = warning_suffix_from_backfill_report(
                    optional_backfill_report,
                    sheet_key=sheet_key,
                    missing_match_ids=missing_sheet_matches,
                )
                blocking_errors.append(
                    f"Missing required sheet '{sheet_key}' for {len(missing_sheet_matches)} matches "
                    f"({', '.join(map(str, missing_sheet_matches[:10]))}){suffix}"
                )
        for sheet_key in relaxed_required_sheet_keys:
            missing_sheet_matches = coverage.loc[~coverage[f"has_{sheet_key}"], "match_id"].dropna().astype(int).tolist()
            if missing_sheet_matches:
                suffix = warning_suffix_from_backfill_report(
                    optional_backfill_report,
                    sheet_key=sheet_key,
                    missing_match_ids=missing_sheet_matches,
                )
                if source_mode == FANTASY_SOURCE_MODE:
                    warnings.append(
                        f"Missing bridge non-blocking sheet '{sheet_key}' for {len(missing_sheet_matches)} matches "
                        f"({', '.join(map(str, missing_sheet_matches[:10]))}){suffix}"
                    )
                elif current_season_partial_mode:
                    warnings.append(
                        f"Missing current-season non-blocking sheet '{sheet_key}' for {len(missing_sheet_matches)} matches "
                        f"({', '.join(map(str, missing_sheet_matches[:10]))}){suffix}"
                    )
                else:
                    warnings.append(
                        f"Missing legacy non-blocking sheet '{sheet_key}' for {len(missing_sheet_matches)} matches "
                        f"({', '.join(map(str, missing_sheet_matches[:10]))}){suffix}"
                    )
        for sheet_key in WARNING_SHEET_KEYS:
            missing_sheet_matches = coverage.loc[~coverage[f"has_{sheet_key}"], "match_id"].dropna().astype(int).tolist()
            if missing_sheet_matches:
                suffix = warning_suffix_from_backfill_report(
                    optional_backfill_report,
                    sheet_key=sheet_key,
                    missing_match_ids=missing_sheet_matches,
                )
                warnings.append(
                    f"Missing warning-only sheet '{sheet_key}' for {len(missing_sheet_matches)} matches "
                    f"({', '.join(map(str, missing_sheet_matches[:10]))}){suffix}"
                )

    diff = build_dataset_diff(reference_dir, dataset_dir)

    return {
        "status": "passed" if not blocking_errors else "failed",
        "validated_at": utc_now().isoformat(),
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "stats": {
            "expected_finished_matches": len(finished_match_ids) if source_mode == FANTASY_SOURCE_MODE else len(expected_match_ids),
            "expected_curated_matches": len(expected_match_ids),
            "curated_matches": int(len(matches)),
            "curated_players": int(len(players)),
            "curated_player_match_rows": int(len(player_match)),
            "timestamp_span_seconds": timestamp_span_seconds,
        },
        "diff": diff,
    }


def publish_release_atomically(release_dir: Path, current_dir: Path) -> None:
    dashboard_dir = current_dir.parent
    temp_dir = dashboard_dir / f"_current_{release_dir.name}"
    backup_dir = dashboard_dir / f"_current_backup_{release_dir.name}"

    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    shutil.copytree(release_dir, temp_dir)

    try:
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        if current_dir.exists():
            current_dir.rename(backup_dir)
        temp_dir.rename(current_dir)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
    except Exception:
        if backup_dir.exists() and not current_dir.exists():
            backup_dir.rename(current_dir)
        raise
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def build_base_manifest(args: argparse.Namespace, paths: PipelinePaths, selected_phases: list[str]) -> dict[str, Any]:
    return {
        "run_id": paths.run_id,
        "release_id": paths.release_id,
        "league": paths.league,
        "season": paths.season,
        "mode": args.mode if hasattr(args, "mode") else "validate",
        "publish_target": getattr(args, "publish_target", getattr(args, "target", "dashboard")),
        "dry_run": bool(getattr(args, "dry_run", False)),
        "from_phase": getattr(args, "from_phase", None),
        "to_phase": getattr(args, "to_phase", None),
        "selected_phases": selected_phases,
        "started_at": utc_now().isoformat(),
        "status": "running",
        "paths": {
            "season_dir": str(paths.season_dir),
            "raw_dir": str(paths.raw_dir),
            "staging_dir": str(paths.staging_dir),
            "curated_dir": str(paths.curated_dir),
            "warehouse_dir": str(paths.warehouse_dir),
            "warehouse_db_path": str(paths.warehouse_db_path),
            "dashboard_dir": str(paths.dashboard_dir),
            "dashboard_release_dir": str(paths.dashboard_release_dir),
            "dashboard_current_dir": str(paths.dashboard_current_dir),
            "fantasy_dir": str(paths.fantasy_dir),
            "fantasy_release_dir": str(paths.fantasy_release_dir),
            "fantasy_current_dir": str(paths.fantasy_current_dir),
        },
        "phases": [],
        "artifacts": {},
    }


def persist_manifest(ctx: RunContext) -> None:
    if ctx.dry_run:
        return
    write_json(ctx.paths.manifest_path, ctx.manifest)


def record_phase(
    ctx: RunContext,
    *,
    phase: str,
    started_at: datetime,
    status: str,
    details: dict[str, Any],
) -> None:
    ctx.manifest["phases"].append(
        {
            "phase": phase,
            "started_at": started_at.isoformat(),
            "ended_at": utc_now().isoformat(),
            "status": status,
            "details": details,
        }
    )
    persist_manifest(ctx)


def sync_file(source: Path, destination: Path, *, only_missing: bool) -> bool:
    ensure_dir(destination.parent)
    if destination.exists():
        if only_missing:
            return False
        source_stat = source.stat()
        dest_stat = destination.stat()
        if source_stat.st_size == dest_stat.st_size and getattr(source_stat, "st_mtime_ns", 0) == getattr(dest_stat, "st_mtime_ns", 1):
            return False
    shutil.copy2(source, destination)
    return True


def phase_extract_master(ctx: RunContext) -> dict[str, Any]:
    paths = ctx.paths
    ensure_dir(paths.raw_master_raw_dir)
    ensure_dir(paths.raw_master_clean_dir)
    bridge_manifest: dict[str, Any] = {}
    if should_refresh_fantasy_bridge(paths):
        try:
            bridge_manifest = export_fantasy_bridge_seed(paths, ctx.logger)
        except Exception as exc:
            ctx.logger.log(f"Fantasy bridge export skipped: {exc}")
            if paths.fantasy_bridge_manifest_path.exists():
                bridge_manifest = read_fantasy_bridge_manifest(paths)
    try:
        raw_source, clean_source, generated_clean = resolve_master_sources(paths)
    except FileNotFoundError:
        if not bridge_manifest and should_refresh_fantasy_bridge(paths):
            bridge_manifest = export_fantasy_bridge_seed(paths, ctx.logger)
            raw_source, clean_source, generated_clean = resolve_master_sources(paths)
        else:
            raise

    raw_target = paths.raw_master_raw_dir / raw_source.name
    clean_target = paths.raw_master_clean_dir / clean_source.name

    copied_raw = sync_file(raw_source, raw_target, only_missing=ctx.only_missing and not ctx.force)
    if generated_clean is None:
        copied_clean = sync_file(clean_source, clean_target, only_missing=ctx.only_missing and not ctx.force)
        master = pd.read_excel(clean_target)
    else:
        if not (ctx.only_missing and not ctx.force and clean_target.exists()):
            generated_clean.to_excel(clean_target, index=False, engine="openpyxl")
            copied_clean = True
        else:
            copied_clean = False
        master = generated_clean.copy()
    master_inventory = build_master_inventory(master)
    if not ctx.dry_run:
        master_inventory.to_parquet(paths.master_inventory_path, index=False)

    return {
        "raw_source": str(raw_source),
        "clean_source": str(clean_source),
        "raw_target": str(raw_target),
        "clean_target": str(clean_target),
        "copied_raw": copied_raw,
        "copied_clean": copied_clean,
        "matches": int(len(master)),
        "source_mode": source_mode_from_paths(paths),
        "fantasy_bridge": bridge_manifest,
    }


def phase_bootstrap_raw(ctx: RunContext) -> dict[str, Any]:
    paths = ctx.paths
    if source_mode_from_paths(paths) == FANTASY_SOURCE_MODE:
        ensure_dir(paths.raw_details_dir)
        raw_inventory = build_fantasy_bridge_inventory(paths)
        if not ctx.dry_run:
            raw_inventory.to_parquet(paths.raw_inventory_path, index=False)
        bridge_manifest = read_fantasy_bridge_manifest(paths)
        return {
            "source_mode": FANTASY_SOURCE_MODE,
            "bridge_counts": bridge_manifest.get("counts", {}),
            "workbooks_in_raw_details": 0,
            "copied_workbooks": 0,
            "expected_match_ids": int(len(raw_inventory)),
        }

    ensure_dir(paths.raw_details_dir)
    master = pd.read_excel(latest_master_clean_path(paths))
    expected_match_ids = set(pd.to_numeric(master["match_id"], errors="coerce").dropna().astype(int).tolist())

    copied = 0
    available_legacy_ids: set[int] = set()
    source_dirs = candidate_source_season_dirs(paths)
    for source_dir in source_dirs:
        for workbook in sorted(source_dir.glob("Sofascore_*.xlsx")):
            match_id = parse_match_id(workbook)
            if match_id is None:
                continue
            available_legacy_ids.add(match_id)
            target = paths.raw_details_dir / workbook.name
            changed = sync_file(workbook, target, only_missing=ctx.only_missing and not ctx.force)
            copied += int(changed)

    split_result = write_legacy_split_workbooks(
        source_dirs=source_dirs,
        expected_match_ids=expected_match_ids - available_legacy_ids,
        details_dir=paths.raw_details_dir,
        only_missing=ctx.only_missing and not ctx.force,
    )
    available_legacy_ids.update(split_result["available_match_ids"])
    copied += int(split_result["written_workbooks"])

    missing_match_ids = sorted(expected_match_ids - available_legacy_ids)
    incomplete_required_sheet_match_ids = sorted(find_required_sheet_gaps(paths.raw_details_dir, expected_match_ids))
    refresh_match_ids = sorted(set(missing_match_ids) | set(incomplete_required_sheet_match_ids))
    if refresh_match_ids:
        ctx.logger.log(
            f"Refreshing {len(refresh_match_ids)} matches via targeted scrape "
            f"(missing_workbooks={len(missing_match_ids)}, missing_required_sheets={len(incomplete_required_sheet_match_ids)})."
        )
        refresh_backup_dir = paths.run_dir / "refresh_backups"
        backed_up_workbooks: dict[int, Path] = {}
        for match_id in incomplete_required_sheet_match_ids:
            workbook_path = paths.raw_details_dir / f"Sofascore_{match_id}.xlsx"
            if workbook_path.exists() and not ctx.dry_run:
                ensure_dir(refresh_backup_dir)
                backup_path = refresh_backup_dir / workbook_path.name
                shutil.copy2(workbook_path, backup_path)
                backed_up_workbooks[match_id] = backup_path
                workbook_path.unlink()
        try:
            from gronestats.processing.data_loader_unprep import scrape_match_details
        except Exception as exc:
            raise RuntimeError(f"Unable to import scraper for missing workbooks: {exc}") from exc
        missing_rows = master.loc[pd.to_numeric(master["match_id"], errors="coerce").astype("Int64").isin(refresh_match_ids)].copy()
        error_log = paths.run_dir / "matches_details_errors.txt"
        scrape_match_details(missing_rows, paths.raw_details_dir, min_file_kb=15, error_log=error_log)
        if not ctx.dry_run:
            for match_id, backup_path in backed_up_workbooks.items():
                target_path = paths.raw_details_dir / backup_path.name
                if not target_path.exists() and backup_path.exists():
                    shutil.copy2(backup_path, target_path)

    raw_inventory = build_raw_inventory(paths.raw_details_dir)
    if not ctx.dry_run:
        raw_inventory.to_parquet(paths.raw_inventory_path, index=False)

    return {
        "expected_match_ids": len(expected_match_ids),
        "workbooks_in_raw_details": int(len(raw_inventory)),
        "copied_workbooks": copied,
        "legacy_split_source_files": int(split_result["source_files"]),
        "legacy_split_match_ids": int(len(split_result["available_match_ids"])),
        "missing_match_ids_before_scrape": missing_match_ids,
        "missing_required_sheet_match_ids_before_scrape": incomplete_required_sheet_match_ids,
    }


def phase_build_staging(ctx: RunContext) -> dict[str, Any]:
    paths = ctx.paths
    ensure_dir(paths.staging_dir)
    master_clean_path = latest_master_clean_path(paths)
    master = pd.read_excel(master_clean_path)
    master["match_id"] = pd.to_numeric(master["match_id"], errors="coerce").astype("Int64")
    ingested_at = utc_now()
    source_mode = source_mode_from_paths(paths)
    provider = provider_name_for_source_mode(source_mode)

    current_raw_inventory = read_parquet_safe(paths.raw_inventory_path)
    current_master_inventory = read_parquet_safe(paths.master_inventory_path)
    previous_raw_inventory = load_previous_run_artifact(paths, "raw_inventory.parquet")
    previous_master_inventory = load_previous_run_artifact(paths, "master_inventory.parquet")

    current_match_ids = set(master["match_id"].dropna().astype(int).tolist())
    existing_staging_present = any((paths.staging_dir / f"{table_name}.parquet").exists() for table_name in STAGING_TABLES)

    if ctx.mode == "incremental" and existing_staging_present and not ctx.force:
        changed_match_ids = resolve_changed_match_ids(
            current_raw_inventory,
            previous_raw_inventory,
            current_master_inventory,
            previous_master_inventory,
        )
    else:
        changed_match_ids = set(current_match_ids)

    processed_match_ids = changed_match_ids if changed_match_ids else set()
    matches_subset = master.loc[master["match_id"].isin(processed_match_ids)].copy() if processed_match_ids else pd.DataFrame(columns=master.columns)
    matches_raw_new = flatten_master_to_matches_raw(
        matches_subset,
        season=paths.season,
        source_file=master_clean_path.name,
        run_id=paths.run_id,
        ingested_at=ingested_at,
        provider=provider,
    )
    if source_mode == FANTASY_SOURCE_MODE:
        workbook_tables_new, coverage_new = collect_fantasy_bridge_staging_tables(
            bridge_dir=paths.fantasy_bridge_dir,
            match_ids=processed_match_ids,
            season=paths.season,
            run_id=paths.run_id,
            ingested_at=ingested_at,
        )
    else:
        workbook_tables_new, coverage_new = collect_workbook_staging_tables(
            details_dir=paths.raw_details_dir,
            match_ids=processed_match_ids,
            season=paths.season,
            run_id=paths.run_id,
            ingested_at=ingested_at,
        )

    staged_tables: dict[str, pd.DataFrame] = {
        "matches_raw": matches_raw_new,
        **workbook_tables_new,
        "sheet_coverage": coverage_new,
    }

    if ctx.mode == "incremental" and existing_staging_present and not ctx.force:
        for table_name, frame in list(staged_tables.items()):
            existing = read_parquet_safe(paths.staging_dir / f"{table_name}.parquet")
            staged_tables[table_name] = sort_table(table_name, merge_incremental_frame(existing, frame, processed_match_ids))
        if not processed_match_ids:
            for table_name in STAGING_TABLES:
                staged_tables[table_name] = sort_table(table_name, read_parquet_safe(paths.staging_dir / f"{table_name}.parquet"))
    else:
        if staged_tables["sheet_coverage"].empty:
            staged_tables["sheet_coverage"] = pd.DataFrame([empty_sheet_coverage_row(match_id) for match_id in sorted(current_match_ids)])
        for table_name, frame in list(staged_tables.items()):
            staged_tables[table_name] = sort_table(table_name, frame)

    if not ctx.dry_run:
        for table_name, frame in staged_tables.items():
            stringify_if_mixed_objects(frame).to_parquet(paths.staging_dir / f"{table_name}.parquet", index=False)

    total_matches_after_merge = int(len(staged_tables["matches_raw"]))
    return {
        "source_mode": source_mode,
        "mode": ctx.mode,
        "processed_match_ids": sorted(processed_match_ids),
        "processed_matches": len(processed_match_ids),
        "total_matches_after_merge": total_matches_after_merge,
        "coverage_rows": int(len(staged_tables["sheet_coverage"])),
    }


def phase_build_curated(ctx: RunContext) -> dict[str, Any]:
    paths = ctx.paths
    ensure_dir(paths.curated_dir)
    if ctx.force and not ctx.dry_run:
        reset_dir(paths.curated_dir, paths.season_dir)
    else:
        ensure_dir(paths.curated_dir)

    staging = {table_name: read_parquet_safe(paths.staging_dir / f"{table_name}.parquet") for table_name in STAGING_TABLES}
    teams_reference_path = resolve_teams_reference_path(paths)
    if teams_reference_path is None:
        teams_reference = pd.DataFrame()
    elif teams_reference_path.name == "0_Teams.xlsx":
        teams_reference = pd.read_excel(teams_reference_path)
        if paths.teams_reference_path.exists():
            fallback_reference = pd.read_excel(paths.teams_reference_path, sheet_name="Equipos")
            teams_reference = pd.concat([fallback_reference, teams_reference], ignore_index=True, sort=False)
    else:
        teams_reference = pd.read_excel(teams_reference_path, sheet_name="Equipos")

    matches = build_matches_curated(staging["matches_raw"])
    teams = build_teams_curated(matches, teams_reference)
    player_identity = build_player_identity(staging["player_stats_raw"], matches)
    players = build_players_curated(player_identity)
    player_match = build_player_match_curated(staging["player_stats_raw"])
    player_totals = build_player_totals_full_season(player_match)
    team_stats = build_team_stats_curated(staging["team_stats_raw"])
    average_positions = build_average_positions_curated(staging["average_positions_raw"], staging["player_stats_raw"], teams)
    heatmap_points = build_heatmap_points_curated(staging["heatmaps_raw"], staging["player_stats_raw"], teams)
    shot_events = build_shot_events_curated(staging["shotmap_raw"], matches)
    match_momentum = build_match_momentum_curated(staging["momentum_raw"])

    curated_tables = {
        "matches": matches,
        "teams": teams,
        "players": players,
        "player_match": player_match,
        "player_totals_full_season": player_totals,
        "team_stats": team_stats,
        "average_positions": average_positions,
        "heatmap_points": heatmap_points,
        "shot_events": shot_events,
        "match_momentum": match_momentum,
        "player_identity": player_identity,
    }

    if not ctx.dry_run:
        for table_name, frame in curated_tables.items():
            stringify_if_mixed_objects(frame).to_parquet(paths.curated_dir / f"{table_name}.parquet", index=False)

    return {
        "curated_rows": {table_name: int(len(frame)) for table_name, frame in curated_tables.items()},
    }


def phase_build_warehouse(ctx: RunContext) -> dict[str, Any]:
    ensure_dir(ctx.paths.warehouse_dir)
    curated_tables = load_curated_tables(ctx.paths.curated_dir)
    canonical_tables = build_canonical_tables(curated_tables, ctx.paths.season)
    row_counts = upsert_canonical_tables(ctx.paths.warehouse_db_path, canonical_tables, ctx.paths.season)
    return {
        "warehouse_path": str(ctx.paths.warehouse_db_path),
        "canonical_rows": row_counts,
    }


def phase_validate(ctx: RunContext) -> dict[str, Any]:
    master_matches = pd.read_excel(latest_master_clean_path(ctx.paths))
    source_mode = source_mode_from_paths(ctx.paths)
    target_validations: dict[str, dict[str, Any]] = {
        "warehouse": validate_warehouse_contract(ctx.paths.warehouse_db_path, ctx.paths.season)
    }
    canonical_tables = load_canonical_tables_for_season(ctx.paths.warehouse_db_path, ctx.paths.season)

    if "dashboard" in selected_publish_targets(ctx.publish_target):
        dashboard_bundle = build_dashboard_bundle_from_canonical(canonical_tables)
        if not ctx.dry_run:
            reset_dir(ctx.paths.dashboard_validation_candidate_dir, ctx.paths.run_dir)
            write_table_bundle(ctx.paths.dashboard_validation_candidate_dir, dashboard_bundle)
        target_validations["dashboard"] = validate_dataset_contract(
            dataset_dir=ctx.paths.dashboard_validation_candidate_dir,
            master_matches=master_matches,
            staging_dir=ctx.paths.staging_dir,
            reference_dir=reference_dataset_dir(ctx.paths),
            season=ctx.paths.season,
            source_mode=source_mode,
        )

    if "fantasy" in selected_publish_targets(ctx.publish_target):
        fantasy_bundle = build_fantasy_bundle_from_canonical(canonical_tables)
        if not ctx.dry_run:
            reset_dir(ctx.paths.fantasy_validation_candidate_dir, ctx.paths.run_dir)
            write_table_bundle(ctx.paths.fantasy_validation_candidate_dir, fantasy_bundle)
        target_validations["fantasy"] = validate_fantasy_export_bundle(ctx.paths.fantasy_validation_candidate_dir)

    validation = combine_target_validations(target_validations)
    if not ctx.dry_run:
        write_json(ctx.paths.validation_path, validation)
    return validation


def phase_publish(ctx: RunContext) -> dict[str, Any]:
    validation_payload = read_json(ctx.paths.validation_path)
    if validation_payload.get("status") != "passed":
        raise RuntimeError("Validation failed. Publish aborted and published targets were left unchanged.")

    selected_targets = selected_publish_targets(ctx.publish_target)
    published: dict[str, dict[str, Any]] = {}
    canonical_tables = load_canonical_tables_for_season(ctx.paths.warehouse_db_path, ctx.paths.season)

    if "dashboard" in selected_targets:
        reset_dir(ctx.paths.dashboard_release_dir, ctx.paths.season_dir)
        dashboard_bundle = build_dashboard_bundle_from_canonical(canonical_tables)
        write_table_bundle(ctx.paths.dashboard_release_dir, dashboard_bundle)
        shutil.copy2(ctx.paths.manifest_path, ctx.paths.dashboard_release_dir / "manifest.json")
        shutil.copy2(ctx.paths.validation_path, ctx.paths.dashboard_release_dir / "validation.json")
        published["dashboard"] = {
            "release_dir": str(ctx.paths.dashboard_release_dir),
            "current_dir": str(ctx.paths.dashboard_current_dir),
            "published_tables": [
                table_name
                for table_name in REQUIRED_CURATED_TABLES
                if (ctx.paths.dashboard_release_dir / f"{table_name}.parquet").exists()
            ],
        }

    if "fantasy" in selected_targets:
        reset_dir(ctx.paths.fantasy_release_dir, ctx.paths.season_dir)
        fantasy_bundle = build_fantasy_bundle_from_canonical(canonical_tables)
        write_table_bundle(ctx.paths.fantasy_release_dir, fantasy_bundle)
        shutil.copy2(ctx.paths.manifest_path, ctx.paths.fantasy_release_dir / "manifest.json")
        shutil.copy2(ctx.paths.validation_path, ctx.paths.fantasy_release_dir / "validation.json")
        published["fantasy"] = {
            "release_dir": str(ctx.paths.fantasy_release_dir),
            "current_dir": str(ctx.paths.fantasy_current_dir),
            "published_tables": [
                table_name
                for table_name in FANTASY_EXPORT_TABLES
                if (ctx.paths.fantasy_release_dir / f"{table_name}.parquet").exists()
            ],
        }

    if "dashboard" in selected_targets:
        publish_release_atomically(ctx.paths.dashboard_release_dir, ctx.paths.dashboard_current_dir)
    if "fantasy" in selected_targets:
        publish_release_atomically(ctx.paths.fantasy_release_dir, ctx.paths.fantasy_current_dir)

    return {"targets": published}


def resolve_phase_range(from_phase: str, to_phase: str) -> list[str]:
    start_index = PHASES.index(from_phase)
    end_index = PHASES.index(to_phase)
    if start_index > end_index:
        raise ValueError(f"from-phase '{from_phase}' cannot be after to-phase '{to_phase}'")
    return list(PHASES[start_index : end_index + 1])


def run_pipeline(args: argparse.Namespace) -> int:
    base_dir = Path(__file__).resolve().parents[2]
    run_id = timestamp_id()
    release_id = timestamp_id()
    paths = PipelinePaths(base_dir=base_dir, league=args.league, season=int(args.season), run_id=run_id, release_id=release_id)
    selected_phases = resolve_phase_range(args.from_phase, args.to_phase)
    logger = PipelineLogger(None if args.dry_run else paths.log_path)
    manifest = build_base_manifest(args, paths, selected_phases)
    ctx = RunContext(
        paths=paths,
        mode=args.mode,
        only_missing=args.only_missing,
        force=args.force,
        dry_run=args.dry_run,
        publish_target=args.publish_target,
        logger=logger,
        manifest=manifest,
    )

    if args.dry_run:
        print(json.dumps(manifest, indent=2, ensure_ascii=False, default=json_default))
        return 0

    ensure_dir(paths.run_dir)
    persist_manifest(ctx)

    phase_handlers = {
        "extract-master": phase_extract_master,
        "bootstrap-raw": phase_bootstrap_raw,
        "build-staging": phase_build_staging,
        "build-curated": phase_build_curated,
        "build-warehouse": phase_build_warehouse,
        "validate": phase_validate,
        "publish": phase_publish,
    }

    try:
        for phase in selected_phases:
            started_at = utc_now()
            logger.log(f"Starting phase: {phase}")
            details = phase_handlers[phase](ctx)
            record_phase(ctx, phase=phase, started_at=started_at, status="completed", details=details)
            if phase == "validate" and details.get("status") != "passed":
                raise RuntimeError("Validation failed. Stopping before publish.")
            logger.log(f"Completed phase: {phase}")
        ctx.manifest["status"] = "completed"
        ctx.manifest["ended_at"] = utc_now().isoformat()
        persist_manifest(ctx)
        if "publish" in selected_phases:
            for target in selected_publish_targets(args.publish_target):
                release_dir = paths.dashboard_release_dir if target == "dashboard" else paths.fantasy_release_dir
                current_dir = paths.dashboard_current_dir if target == "dashboard" else paths.fantasy_current_dir
                if release_dir.exists():
                    shutil.copy2(paths.manifest_path, release_dir / "manifest.json")
                    if paths.validation_path.exists():
                        shutil.copy2(paths.validation_path, release_dir / "validation.json")
                if current_dir.exists():
                    shutil.copy2(paths.manifest_path, current_dir / "manifest.json")
                    if paths.validation_path.exists():
                        shutil.copy2(paths.validation_path, current_dir / "validation.json")
        return 0
    except Exception as exc:
        logger.log(f"Pipeline failed: {exc}")
        ctx.manifest["status"] = "failed"
        ctx.manifest["ended_at"] = utc_now().isoformat()
        ctx.manifest["error"] = str(exc)
        persist_manifest(ctx)
        raise


def validate_release(args: argparse.Namespace) -> int:
    base_dir = Path(__file__).resolve().parents[2]
    release_id = args.release_id or "current"
    paths = PipelinePaths(
        base_dir=base_dir,
        league=args.league,
        season=int(args.season),
        run_id=timestamp_id(),
        release_id=release_id if release_id != "current" else timestamp_id(),
    )
    master_matches = pd.read_excel(latest_master_clean_path(paths))
    source_mode = source_mode_from_paths(paths)
    target_validations: dict[str, dict[str, Any]] = {
        "warehouse": validate_warehouse_contract(paths.warehouse_db_path, paths.season)
    }

    for target in selected_publish_targets(args.target):
        if target == "dashboard":
            dataset_dir = paths.dashboard_current_dir if release_id == "current" else paths.dashboard_releases_dir / release_id
            manifest_path = dataset_dir / "manifest.json"
            if not dataset_dir.exists():
                target_validations[target] = {
                    "status": "failed",
                    "validated_at": utc_now().isoformat(),
                    "blocking_errors": [f"Dataset directory not found: {dataset_dir}"],
                    "warnings": [],
                    "stats": {},
                }
                continue

            manifest = read_json(manifest_path) if manifest_path.exists() else {}
            run_id = manifest.get("run_id")
            staging_dir = paths.staging_dir
            if run_id:
                candidate_run_dir = paths.raw_runs_dir / run_id
                if not candidate_run_dir.exists():
                    staging_dir = None
            target_validations[target] = validate_dataset_contract(
                dataset_dir=dataset_dir,
                master_matches=master_matches,
                staging_dir=staging_dir if staging_dir and staging_dir.exists() else None,
                reference_dir=reference_dataset_dir(paths),
                season=paths.season,
                source_mode=source_mode,
            )
            if release_id != "current":
                write_json(dataset_dir / "validation.json", target_validations[target])
            continue

        dataset_dir = paths.fantasy_current_dir if release_id == "current" else paths.fantasy_releases_dir / release_id
        if not dataset_dir.exists():
            target_validations[target] = {
                "status": "failed",
                "validated_at": utc_now().isoformat(),
                "blocking_errors": [f"Dataset directory not found: {dataset_dir}"],
                "warnings": [],
                "stats": {},
            }
            continue
        target_validations[target] = validate_fantasy_export_bundle(dataset_dir)
        if release_id != "current":
            write_json(dataset_dir / "validation.json", target_validations[target])

    validation = combine_target_validations(target_validations)
    print(json.dumps(validation, indent=2, ensure_ascii=False, default=json_default))
    return 0 if validation.get("status") == "passed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sequential, versioned data pipeline for GroneStatz.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the full GroneStatz pipeline.")
    run_parser.add_argument("--league", default="Liga 1 Peru")
    run_parser.add_argument("--season", type=int, default=2025)
    run_parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    run_parser.add_argument("--from-phase", choices=PHASES, default=PHASES[0])
    run_parser.add_argument("--to-phase", choices=PHASES, default=PHASES[-1])
    run_parser.add_argument("--only-missing", action="store_true")
    run_parser.add_argument("--force", action="store_true")
    run_parser.add_argument("--publish-target", choices=PUBLISH_TARGET_CHOICES, default="all")
    run_parser.add_argument("--dry-run", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="Validate a published release or dashboard/current.")
    validate_parser.add_argument("--league", default="Liga 1 Peru")
    validate_parser.add_argument("--season", type=int, default=2025)
    validate_parser.add_argument("--release-id", default=None)
    validate_parser.add_argument("--target", choices=PUBLISH_TARGET_CHOICES, default="all")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "run":
        raise SystemExit(run_pipeline(args))
    if args.command == "validate":
        raise SystemExit(validate_release(args))


if __name__ == "__main__":
    main()
