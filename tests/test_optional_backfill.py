from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from gronestats.processing.backfill_optional_sheets import _resolve_sheet_targets, build_parser
from gronestats.processing.optional_sheet_backfill import (
    extract_match_ids_from_validation,
    warning_suffix_from_backfill_report,
    write_workbook_frames,
)
from gronestats.processing.pipeline import PipelinePaths


def _make_pipeline_paths(base_dir: Path, season: int = 2025) -> PipelinePaths:
    return PipelinePaths(
        base_dir=base_dir,
        league="Liga 1 Peru",
        season=season,
        run_id="20260407_010101",
        release_id="20260407_010101",
    )


def test_backfill_parser_accepts_validation_and_sheet_selectors() -> None:
    parser = build_parser()

    args = parser.parse_args(["--season", "2025", "--sheet", "momentum", "--from-validation", "--force"])

    assert args.season == 2025
    assert args.sheet == "momentum"
    assert args.from_validation is True
    assert args.force is True


def test_extract_match_ids_from_validation_reads_displayed_ids() -> None:
    payload = {
        "warnings": [
            "dashboard: Missing warning-only sheet 'shotmap' for 10 matches (11018862, 11018863, 11018866)",
            "dashboard: Missing warning-only sheet 'momentum' for 2 matches (15362086, 14935675)",
        ]
    }

    assert extract_match_ids_from_validation(payload, "shotmap") == [11018862, 11018863, 11018866]
    assert extract_match_ids_from_validation(payload, "momentum") == [14935675, 15362086]


def test_resolve_sheet_targets_prefers_sheet_coverage_when_available(tmp_path: Path) -> None:
    paths = _make_pipeline_paths(tmp_path)
    paths.staging_dir.mkdir(parents=True, exist_ok=True)
    paths.dashboard_current_dir.mkdir(parents=True, exist_ok=True)

    coverage = pd.DataFrame(
        {
            "match_id": list(range(1, 13)),
            "has_shotmap": [False] * 12,
        }
    )
    coverage.to_parquet(paths.staging_dir / "sheet_coverage.parquet", index=False)
    (paths.dashboard_current_dir / "validation.json").write_text(
        json.dumps(
            {
                "warnings": [
                    "dashboard: Missing warning-only sheet 'shotmap' for 12 matches (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)"
                ]
            }
        ),
        encoding="utf-8",
    )

    resolved = _resolve_sheet_targets(
        paths=paths,
        sheet_keys=("shotmap",),
        explicit_match_ids=[],
        from_validation=True,
    )

    assert resolved["shotmap"] == list(range(1, 13))


def test_write_workbook_frames_preserves_existing_sheets(tmp_path: Path) -> None:
    workbook_path = tmp_path / "Sofascore_123.xlsx"
    write_workbook_frames(
        workbook_path,
        {
            "Team Stats": pd.DataFrame({"name": ["Posesion"], "value": [55]}),
            "Player Stats": pd.DataFrame({"name": ["Jugador"], "minutes": [90]}),
        },
    )
    write_workbook_frames(
        workbook_path,
        {
            "Team Stats": pd.DataFrame({"name": ["Posesion"], "value": [55]}),
            "Player Stats": pd.DataFrame({"name": ["Jugador"], "minutes": [90]}),
            "Shotmap": pd.DataFrame({"match_id": [123], "time": [12], "x": [84.0], "y": [52.0]}),
        },
    )

    workbook = pd.ExcelFile(workbook_path)
    try:
        assert workbook.sheet_names == ["Team Stats", "Player Stats", "Shotmap"]
        shotmap = pd.read_excel(workbook, sheet_name="Shotmap")
        player_stats = pd.read_excel(workbook, sheet_name="Player Stats")
    finally:
        workbook.close()

    assert len(shotmap) == 1
    assert len(player_stats) == 1


def test_warning_suffix_summarizes_backfill_classification() -> None:
    suffix = warning_suffix_from_backfill_report(
        {
            "results": [
                {"sheet_key": "momentum", "match_id": 1, "classification": "missing_from_source"},
                {"sheet_key": "momentum", "match_id": 2, "classification": "retryable_error"},
                {"sheet_key": "momentum", "match_id": 99, "classification": "missing_from_run"},
            ]
        },
        sheet_key="momentum",
        missing_match_ids=[1, 2, 3],
    )

    assert "missing_from_source=1" in suffix
    assert "retryable_error=1" in suffix
    assert "missing_from_run" not in suffix
