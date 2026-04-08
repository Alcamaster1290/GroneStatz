from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


OPTIONAL_SHEET_CANONICAL_NAMES = {
    "average_positions": "Average Positions",
    "heatmaps": "Heatmaps",
    "shotmap": "Shotmap",
    "momentum": "Match Momentum",
}

OPTIONAL_SHEET_KEYS = tuple(OPTIONAL_SHEET_CANONICAL_NAMES.keys())
WORKBOOK_SHEET_ORDER = (
    "Team Stats",
    "Player Stats",
    "Average Positions",
    "Shotmap",
    "Match Momentum",
    "Heatmaps",
)

_PRE_TAG_RE = re.compile(r"^<pre[^>]*>(.*)</pre>$", re.IGNORECASE | re.DOTALL)
_VALIDATION_WARNING_RE = re.compile(r"Missing [^']+ sheet '([^']+)' for \d+ matches \(([^)]*)\)")


@dataclass(frozen=True)
class OptionalSheetFetchResult:
    classification: str
    frame: pd.DataFrame
    source: str
    message: str
    http_status: int | None = None


def optional_backfill_dir_for_season(season_dir: Path) -> Path:
    return season_dir / "raw" / "optional_backfill"


def optional_backfill_latest_report_path(season_dir: Path) -> Path:
    return optional_backfill_dir_for_season(season_dir) / "latest_report.json"


def optional_backfill_history_report_path(season_dir: Path, report_id: str) -> Path:
    return optional_backfill_dir_for_season(season_dir) / "history" / f"{report_id}.json"


def load_optional_backfill_report_for_staging(staging_dir: Path | None) -> dict[str, Any]:
    if staging_dir is None:
        return {}
    report_path = optional_backfill_latest_report_path(staging_dir.parent)
    if not report_path.exists():
        return {}
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def warning_suffix_from_backfill_report(
    report_payload: dict[str, Any],
    *,
    sheet_key: str,
    missing_match_ids: list[int] | set[int],
) -> str:
    if not report_payload:
        return ""
    missing_set = {int(match_id) for match_id in missing_match_ids}
    if not missing_set:
        return ""
    results = report_payload.get("results", [])
    if not isinstance(results, list):
        return ""
    counter: Counter[str] = Counter()
    for item in results:
        if not isinstance(item, dict):
            continue
        if str(item.get("sheet_key")) != sheet_key:
            continue
        match_id = pd.to_numeric(pd.Series([item.get("match_id")]), errors="coerce").iloc[0]
        if pd.isna(match_id):
            continue
        if int(match_id) not in missing_set:
            continue
        classification = str(item.get("classification", "")).strip()
        if classification:
            counter[classification] += 1
    if not counter:
        return ""
    labels = []
    for classification in ("missing_from_source", "retryable_error", "missing_from_run", "skipped_existing"):
        if counter.get(classification):
            labels.append(f"{classification}={counter[classification]}")
    if not labels:
        labels = [f"{key}={value}" for key, value in sorted(counter.items())]
    return f" | backfill: {', '.join(labels)}"


def extract_match_ids_from_validation(validation_payload: dict[str, Any], sheet_key: str) -> list[int]:
    warnings = validation_payload.get("warnings", [])
    if not isinstance(warnings, list):
        return []
    result: list[int] = []
    for warning in warnings:
        if not isinstance(warning, str):
            continue
        match = _VALIDATION_WARNING_RE.search(warning)
        if match is None:
            continue
        warning_sheet_key = match.group(1).strip()
        if warning_sheet_key != sheet_key:
            continue
        values = [token.strip() for token in match.group(2).split(",")]
        for value in values:
            numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            if pd.isna(numeric):
                continue
            result.append(int(numeric))
    return sorted(dict.fromkeys(result))


def resolve_missing_match_ids_from_coverage(coverage: pd.DataFrame, sheet_key: str) -> list[int]:
    if coverage.empty:
        return []
    column_name = f"has_{sheet_key}"
    if column_name not in coverage.columns or "match_id" not in coverage.columns:
        return []
    missing = coverage.loc[~coverage[column_name].fillna(False), "match_id"]
    missing = pd.to_numeric(missing, errors="coerce").dropna().astype(int)
    return sorted(dict.fromkeys(missing.tolist()))


def read_workbook_frames(workbook_path: Path) -> dict[str, pd.DataFrame]:
    if not workbook_path.exists():
        return {}
    workbook = pd.ExcelFile(workbook_path)
    try:
        return {sheet_name: pd.read_excel(workbook, sheet_name=sheet_name) for sheet_name in workbook.sheet_names}
    finally:
        workbook.close()


def write_workbook_frames(workbook_path: Path, frames_by_sheet: dict[str, pd.DataFrame]) -> None:
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    ordered_names = [sheet_name for sheet_name in WORKBOOK_SHEET_ORDER if sheet_name in frames_by_sheet]
    ordered_names.extend(sorted(sheet_name for sheet_name in frames_by_sheet if sheet_name not in WORKBOOK_SHEET_ORDER))
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        for sheet_name in ordered_names:
            frame = frames_by_sheet[sheet_name]
            if frame is None:
                continue
            frame.to_excel(writer, sheet_name=sheet_name, index=False)


def _normalize_json_like_text(payload: str) -> str:
    text = payload.strip()
    match = _PRE_TAG_RE.match(text)
    if match:
        text = match.group(1).strip()
    return text


def _browser_get_json_compat(url: str) -> dict[str, Any]:
    from botasaurus_driver.driver import Driver

    driver = Driver(headless=True, block_images_and_css=True)
    try:
        driver.get(url)
        payload = _normalize_json_like_text(driver.page_text)
        return json.loads(payload) if payload else {}
    finally:
        try:
            driver.close()
        except Exception:
            pass


def _patch_scraperfc_sofascore_transport() -> None:
    import ScraperFC.sofascore as sofascore_module

    current = getattr(sofascore_module, "botasaurus_browser_get_json", None)
    if current is _browser_get_json_compat:
        return
    sofascore_module.botasaurus_browser_get_json = _browser_get_json_compat


def build_sofascore_client():
    import ScraperFC as sfc

    _patch_scraperfc_sofascore_transport()
    return sfc.Sofascore()


def _coerce_match_frame(frame: pd.DataFrame, match_id: int) -> pd.DataFrame:
    if frame.empty:
        return frame
    work = frame.copy()
    if "match_id" not in work.columns:
        work["match_id"] = match_id
    return work


def _heatmaps_dict_to_frame(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for player_name, info in payload.items():
        if not isinstance(info, dict):
            continue
        rows.append(
            {
                "player": player_name,
                "player_id": info.get("id"),
                "heatmap": info.get("heatmap"),
            }
        )
    return pd.DataFrame(rows)


def _manual_endpoint_frame(match_id: int, *, endpoint: str, data_key: str) -> OptionalSheetFetchResult:
    url = f"https://api.sofascore.com/api/v1/event/{match_id}/{endpoint}"
    try:
        payload = _browser_get_json_compat(url)
    except Exception as exc:
        return OptionalSheetFetchResult(
            classification="retryable_error",
            frame=pd.DataFrame(),
            source="endpoint_fallback",
            message=f"Fallback endpoint failed: {exc}",
        )

    if not isinstance(payload, dict):
        return OptionalSheetFetchResult(
            classification="retryable_error",
            frame=pd.DataFrame(),
            source="endpoint_fallback",
            message="Fallback endpoint returned a non-dict payload.",
        )

    error_payload = payload.get("error")
    if isinstance(error_payload, dict):
        code = pd.to_numeric(pd.Series([error_payload.get("code")]), errors="coerce").iloc[0]
        reason = str(error_payload.get("reason", "Unknown error")).strip()
        classification = "missing_from_source" if not pd.isna(code) and int(code) == 404 else "retryable_error"
        return OptionalSheetFetchResult(
            classification=classification,
            frame=pd.DataFrame(),
            source="endpoint_fallback",
            message=f"Fallback endpoint returned {reason}.",
            http_status=None if pd.isna(code) else int(code),
        )

    data = payload.get(data_key)
    if isinstance(data, list):
        frame = _coerce_match_frame(pd.DataFrame(data), match_id)
        if not frame.empty:
            return OptionalSheetFetchResult(
                classification="missing_from_run",
                frame=frame,
                source="endpoint_fallback",
                message=f"Recovered {len(frame)} rows from manual endpoint fallback.",
            )
        return OptionalSheetFetchResult(
            classification="missing_from_source",
            frame=pd.DataFrame(),
            source="endpoint_fallback",
            message="Fallback endpoint returned an empty list.",
        )

    return OptionalSheetFetchResult(
        classification="retryable_error",
        frame=pd.DataFrame(),
        source="endpoint_fallback",
        message=f"Fallback endpoint did not expose `{data_key}`.",
    )


def fetch_optional_sheet(
    *,
    match_id: int,
    sheet_key: str,
    sofascore_client: Any | None = None,
) -> OptionalSheetFetchResult:
    if sheet_key not in OPTIONAL_SHEET_KEYS:
        raise ValueError(f"Unsupported optional sheet: {sheet_key}")

    client = sofascore_client or build_sofascore_client()
    primary_message = ""
    try:
        if sheet_key == "shotmap":
            frame = client.scrape_match_shots(str(match_id))
        elif sheet_key == "momentum":
            frame = client.scrape_match_momentum(str(match_id))
        elif sheet_key == "average_positions":
            frame = client.scrape_player_average_positions(str(match_id))
        else:
            frame = _heatmaps_dict_to_frame(client.scrape_heatmaps(str(match_id)))
    except Exception as exc:
        frame = pd.DataFrame()
        primary_message = f"ScraperFC failed: {exc}"

    frame = _coerce_match_frame(frame, match_id)
    if not frame.empty:
        return OptionalSheetFetchResult(
            classification="missing_from_run",
            frame=frame,
            source="scraperfc",
            message=f"Recovered {len(frame)} rows via ScraperFC.",
        )

    if not primary_message:
        primary_message = "ScraperFC returned an empty frame."

    if sheet_key == "shotmap":
        fallback = _manual_endpoint_frame(match_id, endpoint="shotmap", data_key="shotmap")
        if fallback.frame.empty and fallback.message:
            fallback = OptionalSheetFetchResult(
                classification=fallback.classification,
                frame=fallback.frame,
                source=fallback.source,
                message=f"{primary_message} {fallback.message}".strip(),
                http_status=fallback.http_status,
            )
        return fallback
    if sheet_key == "momentum":
        fallback = _manual_endpoint_frame(match_id, endpoint="graph", data_key="graphPoints")
        if fallback.frame.empty and fallback.message:
            fallback = OptionalSheetFetchResult(
                classification=fallback.classification,
                frame=fallback.frame,
                source=fallback.source,
                message=f"{primary_message} {fallback.message}".strip(),
                http_status=fallback.http_status,
            )
        return fallback

    return OptionalSheetFetchResult(
        classification="missing_from_source",
        frame=pd.DataFrame(),
        source="scraperfc",
        message=primary_message,
    )


def summarize_results(results: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in results:
        classification = str(item.get("classification", "")).strip()
        if classification:
            counter[classification] += 1
    return {key: int(value) for key, value in sorted(counter.items())}
