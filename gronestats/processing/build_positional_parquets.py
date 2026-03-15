from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
DETAILS_DIR = BASE_DIR / "gronestats" / "data" / "Liga 1 Peru" / "2025"
OUT_DIR = DETAILS_DIR / "parquets" / "normalized"
OUT_DIR.mkdir(parents=True, exist_ok=True)


MATCH_ID_RE = re.compile(r"Sofascore_(\d+)\.xlsx$", re.IGNORECASE)


def _safe_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _safe_int(value: object) -> int | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return int(float(numeric))


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def _parse_match_id(path: Path) -> int | None:
    match = MATCH_ID_RE.search(path.name)
    if not match:
        return None
    return int(match.group(1))


def _load_sheet(workbook: pd.ExcelFile, names: list[str]) -> pd.DataFrame:
    for name in names:
        if name in workbook.sheet_names:
            return pd.read_excel(workbook, sheet_name=name)
    return pd.DataFrame()


def _build_player_lookup(player_stats: pd.DataFrame) -> tuple[dict[int, dict[str, object]], dict[str, dict[str, object]]]:
    if player_stats.empty:
        return {}, {}

    work = player_stats.copy()
    if "id" in work.columns:
        work["player_id"] = pd.to_numeric(work["id"], errors="coerce").astype("Int64")
    elif "player_id" in work.columns:
        work["player_id"] = pd.to_numeric(work["player_id"], errors="coerce").astype("Int64")
    else:
        work["player_id"] = pd.Series(pd.NA, index=work.index, dtype="Int64")

    if "teamId" in work.columns:
        work["team_id"] = pd.to_numeric(work["teamId"], errors="coerce").astype("Int64")
    elif "team_id" in work.columns:
        work["team_id"] = pd.to_numeric(work["team_id"], errors="coerce").astype("Int64")
    else:
        work["team_id"] = pd.Series(pd.NA, index=work.index, dtype="Int64")

    lookup_by_id: dict[int, dict[str, object]] = {}
    lookup_by_name: dict[str, dict[str, object]] = {}

    for _, row in work.iterrows():
        player_id = _safe_int(row.get("player_id"))
        name = _safe_text(row.get("name"))
        payload = {
            "player_id": player_id,
            "team_id": _safe_int(row.get("team_id")),
            "team_name": _safe_text(row.get("teamName")),
            "name": name,
            "position": _safe_text(row.get("position.1")) or _safe_text(row.get("position")),
            "shirt_number": _safe_int(row.get("shirtNumber")) or _safe_int(row.get("jerseyNumber")),
            "is_starter": False if bool(row.get("substitute")) else True if pd.notna(row.get("substitute")) else None,
        }
        if player_id is not None:
            lookup_by_id[player_id] = payload
        if name:
            lookup_by_name[name.casefold()] = payload

    return lookup_by_id, lookup_by_name


def _parse_heatmap_payload(value: object) -> tuple[int | None, list[tuple[float, float]]]:
    if value is None or pd.isna(value):
        return None, []

    payload = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None, []
        try:
            payload = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return None, []

    if not isinstance(payload, dict):
        return None, []

    player_id = _safe_int(payload.get("id"))
    points = []
    for pair in payload.get("heatmap", []) or []:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        x = _safe_float(pair[0])
        y = _safe_float(pair[1])
        if x is None or y is None:
            continue
        points.append((x, y))
    return player_id, points


def _extract_average_positions(match_id: int, workbook: pd.ExcelFile) -> pd.DataFrame:
    average_df = _load_sheet(workbook, ["Average Positions", "AveragePositions"])
    player_stats_df = _load_sheet(workbook, ["Player Stats", "Players", "PlayerStats"])
    if average_df.empty:
        return pd.DataFrame()

    lookup_by_id, lookup_by_name = _build_player_lookup(player_stats_df)
    rows: list[dict[str, object]] = []

    for _, row in average_df.iterrows():
        player_id = _safe_int(row.get("id"))
        name = _safe_text(row.get("name")) or _safe_text(row.get("shortName"))
        identity = None
        if player_id is not None:
            identity = lookup_by_id.get(player_id)
        if identity is None and name:
            identity = lookup_by_name.get(name.casefold())

        rows.append(
            {
                "match_id": match_id,
                "player_id": player_id or (identity or {}).get("player_id"),
                "team_id": (identity or {}).get("team_id"),
                "team_name": (identity or {}).get("team_name") or _safe_text(row.get("team")),
                "name": name or (identity or {}).get("name"),
                "shirt_number": (identity or {}).get("shirt_number") or _safe_int(row.get("jerseyNumber")),
                "position": (identity or {}).get("position") or _safe_text(row.get("position")),
                "average_x": _safe_float(row.get("averageX")),
                "average_y": _safe_float(row.get("averageY")),
                "points_count": _safe_int(row.get("pointsCount")),
                "is_starter": (identity or {}).get("is_starter"),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["match_id"] = pd.to_numeric(frame["match_id"], errors="coerce").astype("Int64")
    frame["player_id"] = pd.to_numeric(frame["player_id"], errors="coerce").astype("Int64")
    frame["team_id"] = pd.to_numeric(frame["team_id"], errors="coerce").astype("Int64")
    frame["shirt_number"] = pd.to_numeric(frame["shirt_number"], errors="coerce").astype("Int64")
    frame["points_count"] = pd.to_numeric(frame["points_count"], errors="coerce").astype("Int64")
    frame["average_x"] = pd.to_numeric(frame["average_x"], errors="coerce")
    frame["average_y"] = pd.to_numeric(frame["average_y"], errors="coerce")
    frame["is_starter"] = frame["is_starter"].astype("boolean")
    frame["position"] = frame["position"].astype("string").str.strip().str.upper()
    frame["name"] = frame["name"].astype("string").str.strip()
    frame["team_name"] = frame["team_name"].astype("string").str.strip()
    return frame.dropna(subset=["player_id", "average_x", "average_y"], how="any").reset_index(drop=True)


def _extract_heatmap_points(match_id: int, workbook: pd.ExcelFile) -> pd.DataFrame:
    heatmap_df = _load_sheet(workbook, ["Heatmap", "Heatmaps"])
    player_stats_df = _load_sheet(workbook, ["Player Stats", "Players", "PlayerStats"])
    if heatmap_df.empty:
        return pd.DataFrame()

    lookup_by_id, lookup_by_name = _build_player_lookup(player_stats_df)
    rows: list[dict[str, object]] = []

    for _, row in heatmap_df.iterrows():
        name = _safe_text(row.get("player"))
        player_id, points = _parse_heatmap_payload(row.get("heatmap"))
        identity = None
        if player_id is not None:
            identity = lookup_by_id.get(player_id)
        if identity is None and name:
            identity = lookup_by_name.get(name.casefold())
        final_player_id = player_id or (identity or {}).get("player_id")
        final_name = name or (identity or {}).get("name")
        team_id = (identity or {}).get("team_id")
        team_name = (identity or {}).get("team_name")
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
    frame["match_id"] = pd.to_numeric(frame["match_id"], errors="coerce").astype("Int64")
    frame["player_id"] = pd.to_numeric(frame["player_id"], errors="coerce").astype("Int64")
    frame["team_id"] = pd.to_numeric(frame["team_id"], errors="coerce").astype("Int64")
    frame["x"] = pd.to_numeric(frame["x"], errors="coerce")
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame["name"] = frame["name"].astype("string").str.strip()
    frame["team_name"] = frame["team_name"].astype("string").str.strip()
    return frame.dropna(subset=["player_id", "x", "y"], how="any").reset_index(drop=True)


def build_positional_parquets(details_dir: Path = DETAILS_DIR, out_dir: Path = OUT_DIR) -> tuple[Path, Path]:
    average_frames: list[pd.DataFrame] = []
    heatmap_frames: list[pd.DataFrame] = []

    for workbook_path in sorted(details_dir.glob("Sofascore_*.xlsx")):
        match_id = _parse_match_id(workbook_path)
        if match_id is None:
            continue
        workbook = pd.ExcelFile(workbook_path)
        average_frame = _extract_average_positions(match_id, workbook)
        heatmap_frame = _extract_heatmap_points(match_id, workbook)
        if not average_frame.empty:
            average_frames.append(average_frame)
        if not heatmap_frame.empty:
            heatmap_frames.append(heatmap_frame)

    average_positions = (
        pd.concat(average_frames, ignore_index=True)
        if average_frames
        else pd.DataFrame(
            columns=[
                "match_id",
                "player_id",
                "team_id",
                "team_name",
                "name",
                "shirt_number",
                "position",
                "average_x",
                "average_y",
                "points_count",
                "is_starter",
            ]
        )
    )
    heatmap_points = (
        pd.concat(heatmap_frames, ignore_index=True)
        if heatmap_frames
        else pd.DataFrame(columns=["match_id", "player_id", "team_id", "team_name", "name", "x", "y"])
    )

    average_positions = average_positions.drop_duplicates(
        subset=["match_id", "player_id"], keep="last"
    ).sort_values(["match_id", "team_name", "shirt_number", "name"], kind="mergesort")
    heatmap_points = heatmap_points.sort_values(["match_id", "player_id"], kind="mergesort")

    average_path = out_dir / "average_positions.parquet"
    heatmap_path = out_dir / "heatmap_points.parquet"
    average_positions.to_parquet(average_path, index=False)
    heatmap_points.to_parquet(heatmap_path, index=False)
    return average_path, heatmap_path


def main() -> None:
    average_path, heatmap_path = build_positional_parquets()
    print(f"[OK] {average_path}")
    print(f"[OK] {heatmap_path}")


if __name__ == "__main__":
    main()
