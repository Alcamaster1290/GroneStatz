from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from gronestats.processing.optional_sheet_backfill import (
    OPTIONAL_SHEET_CANONICAL_NAMES,
    OPTIONAL_SHEET_KEYS,
    build_sofascore_client,
    extract_match_ids_from_validation,
    fetch_optional_sheet,
    optional_backfill_history_report_path,
    optional_backfill_latest_report_path,
    read_workbook_frames,
    resolve_missing_match_ids_from_coverage,
    summarize_results,
    write_workbook_frames,
)
from gronestats.processing.pipeline import (
    PipelinePaths,
    read_json,
    read_parquet_safe,
    run_pipeline,
    timestamp_id,
    utc_now,
    write_json,
)


def _parse_match_ids(value: str | None) -> list[int]:
    if value is None:
        return []
    result: list[int] = []
    for token in value.split(","):
        numeric = pd.to_numeric(pd.Series([token.strip()]), errors="coerce").iloc[0]
        if pd.isna(numeric):
            continue
        result.append(int(numeric))
    return sorted(dict.fromkeys(result))


def _selected_sheet_keys(sheet: str) -> tuple[str, ...]:
    if sheet == "all":
        return OPTIONAL_SHEET_KEYS
    if sheet not in OPTIONAL_SHEET_KEYS:
        raise ValueError(f"Unsupported sheet selector: {sheet}")
    return (sheet,)


def _resolve_sheet_targets(
    *,
    paths: PipelinePaths,
    sheet_keys: tuple[str, ...],
    explicit_match_ids: list[int],
    from_validation: bool,
) -> dict[str, list[int]]:
    sheet_targets: dict[str, list[int]] = {sheet_key: list(explicit_match_ids) for sheet_key in sheet_keys}
    if not from_validation:
        return {sheet_key: sorted(dict.fromkeys(match_ids)) for sheet_key, match_ids in sheet_targets.items()}

    coverage = read_parquet_safe(paths.staging_dir / "sheet_coverage.parquet")
    validation_payload = read_json(paths.dashboard_current_dir / "validation.json") if (paths.dashboard_current_dir / "validation.json").exists() else {}
    for sheet_key in sheet_keys:
        coverage_ids = resolve_missing_match_ids_from_coverage(coverage, sheet_key)
        validation_ids = extract_match_ids_from_validation(validation_payload, sheet_key)
        resolved = sorted(dict.fromkeys(sheet_targets[sheet_key] + coverage_ids + validation_ids))
        sheet_targets[sheet_key] = resolved
    return sheet_targets


def _merge_sheet_into_workbook(
    *,
    workbook_path: Path,
    sheet_name: str,
    frame: pd.DataFrame,
) -> None:
    frames_by_sheet = read_workbook_frames(workbook_path)
    frames_by_sheet[sheet_name] = frame
    write_workbook_frames(workbook_path, frames_by_sheet)


def _run_publish_pipeline(paths: PipelinePaths) -> int:
    args = argparse.Namespace(
        league=paths.league,
        season=paths.season,
        mode="full",
        from_phase="build-staging",
        to_phase="publish",
        only_missing=False,
        force=False,
        publish_target="all",
        dry_run=False,
        command="run",
    )
    return run_pipeline(args)


def run_backfill(args: argparse.Namespace) -> int:
    base_dir = Path(__file__).resolve().parents[2]
    report_id = timestamp_id()
    paths = PipelinePaths(
        base_dir=base_dir,
        league=args.league,
        season=int(args.season),
        run_id=report_id,
        release_id=report_id,
    )
    sheet_keys = _selected_sheet_keys(args.sheet)
    explicit_match_ids = _parse_match_ids(args.match_ids)
    sheet_targets = _resolve_sheet_targets(
        paths=paths,
        sheet_keys=sheet_keys,
        explicit_match_ids=explicit_match_ids,
        from_validation=args.from_validation,
    )
    all_target_match_ids = sorted({match_id for match_ids in sheet_targets.values() for match_id in match_ids})

    report: dict[str, Any] = {
        "report_id": report_id,
        "generated_at": utc_now().isoformat(),
        "league": paths.league,
        "season": paths.season,
        "sheet_selector": args.sheet,
        "sheet_targets": sheet_targets,
        "match_ids": all_target_match_ids,
        "results": [],
        "summary": {},
        "pipeline": {
            "ran": False,
            "status": "skipped",
        },
    }

    latest_report_path = optional_backfill_latest_report_path(paths.season_dir)
    history_report_path = optional_backfill_history_report_path(paths.season_dir, report_id)
    latest_report_path.parent.mkdir(parents=True, exist_ok=True)
    history_report_path.parent.mkdir(parents=True, exist_ok=True)

    if not all_target_match_ids:
        report["summary"] = {"selected_matches": 0}
        write_json(history_report_path, report)
        write_json(latest_report_path, report)
        return 0

    sofascore_client = build_sofascore_client()
    changed_workbooks: set[int] = set()
    for sheet_key in sheet_keys:
        sheet_name = OPTIONAL_SHEET_CANONICAL_NAMES[sheet_key]
        for match_id in sheet_targets[sheet_key]:
            workbook_path = paths.raw_details_dir / f"Sofascore_{match_id}.xlsx"
            result_entry: dict[str, Any] = {
                "match_id": match_id,
                "sheet_key": sheet_key,
                "sheet_name": sheet_name,
                "workbook_path": str(workbook_path),
                "updated": False,
                "rows_written": 0,
            }
            try:
                existing_frames = read_workbook_frames(workbook_path)
            except Exception as exc:
                result_entry.update(
                    {
                        "classification": "retryable_error",
                        "source": "workbook_reader",
                        "message": f"Existing workbook could not be read: {exc}",
                    }
                )
                report["results"].append(result_entry)
                continue

            existing_frame = existing_frames.get(sheet_name, pd.DataFrame())
            if not args.force and not existing_frame.empty:
                result_entry.update(
                    {
                        "classification": "skipped_existing",
                        "source": "existing_workbook",
                        "message": "The target sheet already has rows and `--force` was not provided.",
                    }
                )
                report["results"].append(result_entry)
                continue

            fetch_result = fetch_optional_sheet(
                match_id=match_id,
                sheet_key=sheet_key,
                sofascore_client=sofascore_client,
            )
            result_entry.update(
                {
                    "classification": fetch_result.classification,
                    "source": fetch_result.source,
                    "message": fetch_result.message,
                    "http_status": fetch_result.http_status,
                }
            )
            if fetch_result.classification == "missing_from_run" and not fetch_result.frame.empty:
                _merge_sheet_into_workbook(
                    workbook_path=workbook_path,
                    sheet_name=sheet_name,
                    frame=fetch_result.frame,
                )
                result_entry["updated"] = True
                result_entry["rows_written"] = int(len(fetch_result.frame))
                changed_workbooks.add(match_id)
            report["results"].append(result_entry)

    report["summary"] = {
        **summarize_results(report["results"]),
        "selected_matches": len(all_target_match_ids),
        "updated_workbooks": len(changed_workbooks),
    }
    write_json(history_report_path, report)
    write_json(latest_report_path, report)

    if report["results"]:
        report["pipeline"]["ran"] = True
        report["pipeline"]["status"] = "running"
        write_json(history_report_path, report)
        write_json(latest_report_path, report)
        try:
            _run_publish_pipeline(paths)
        except Exception as exc:
            report["pipeline"]["status"] = "failed"
            report["pipeline"]["error"] = str(exc)
            write_json(history_report_path, report)
            write_json(latest_report_path, report)
            raise
        report["pipeline"]["status"] = "completed"
        current_validation_path = paths.dashboard_current_dir / "validation.json"
        if current_validation_path.exists():
            current_validation = json.loads(current_validation_path.read_text(encoding="utf-8"))
            report["pipeline"]["dashboard_validation_status"] = current_validation.get("status")
            report["pipeline"]["dashboard_warning_count"] = len(current_validation.get("warnings", []))
        write_json(history_report_path, report)
        write_json(latest_report_path, report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill optional SofaScore sheets and republish the affected season.")
    parser.add_argument("--league", default="Liga 1 Peru")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--sheet", choices=(*OPTIONAL_SHEET_KEYS, "all"), default="all")
    parser.add_argument("--match-ids", default=None, help="Comma-separated match_id list applied to the selected sheet(s).")
    parser.add_argument("--from-validation", action="store_true", help="Resolve missing match_ids from validation.json or sheet_coverage.parquet.")
    parser.add_argument("--force", action="store_true", help="Re-fetch and overwrite the target sheet even if the workbook already has rows.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(run_backfill(args))


if __name__ == "__main__":
    main()
