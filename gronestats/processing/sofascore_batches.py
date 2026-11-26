"""Scrapeo de SofaScore por tandas: libro de registro por partido y parada al primer bloqueo.

ScraperFC trata cualquier error de un heatmap como "el jugador no jugo" y deja una lista vacia, asi que un
bloqueo (403/429) pasaria desapercibido y se guardarian heatmaps vacios que luego se darian por buenos.
``BlockGuard`` envuelve el transporte de ``sofascore_session``: un 404 es un dato ausente legitimo; cualquier
otro error es un bloqueo y, desde ese momento, no se hace ninguna llamada mas.

Uso (siempre con la sesion visible de Chrome de ``sofascore_session``):
    py -3.11 -m gronestats.processing.sofascore_batches details  --season 2026 --batch-size 5 --pause 20
    py -3.11 -m gronestats.processing.sofascore_batches heatmaps --season 2026 --batch-size 3 --pause 45
    py -3.11 -m gronestats.processing.sofascore_batches momentum --season 2025 --batch-size 10 --pause 10
    py -3.11 -m gronestats.processing.sofascore_batches team-stats|average-positions|shotmap --season 2022   # hojas que faltan
    py -3.11 -m gronestats.processing.sofascore_batches lineups --season 2026    # formacion declarada y titulares -> raw/lineups.jsonl
    py -3.11 -m gronestats.processing.sofascore_batches player-images --season 2026   # fotos que faltan -> gronestats/images/players
    py -3.11 -m gronestats.processing.sofascore_batches fixtures --season 2022      # listado: fecha, estado y estadio
    py -3.11 -m gronestats.processing.sofascore_batches apply-fixtures --season 2022  # sin red: lo vuelca en 0_Matches.xlsx
Es reanudable: lo ya resuelto se omite y cada partido queda en ``raw/scrape_ledger.jsonl``.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

from gronestats.processing.optional_sheet_backfill import read_workbook_frames, write_workbook_frames
from gronestats.processing.pipeline import PipelinePaths, find_required_sheet_gaps, latest_master_clean_path, timestamp_id

HEATMAP_SHEET_NAMES = ("Heatmaps", "Heatmap")
SETTLED_STATUSES = {"ok", "vacio"}
PROGRESS_STATUSES = {"ok", "saltado"}
# columna del maestro -> columna del listado: el estado del evento (finished, postponed, canceled) pasa a `status`
FIXTURE_MASTER_COLUMNS = {"fecha": "fecha", "estadio": "estadio", "ciudad": "ciudad", "status": "estado"}


@dataclass(frozen=True)
class SheetSpec:
    """Una hoja que se pide con una llamada por partido: sus nombres en los workbooks y el metodo de ScraperFC que la trae."""

    key: str  # nombre del modo en el registro
    names: tuple[str, ...]  # el primero es el nombre actual; los demas son los historicos
    method: str
    count_label: str = "rows"


SHEETS = {
    "momentum": SheetSpec("momentum", ("Match Momentum", "Momentum"), "scrape_match_momentum", "points"),
    "team_stats": SheetSpec("team_stats", ("Team Stats", "TeamStats"), "scrape_team_match_stats"),
    "average_positions": SheetSpec("average_positions", ("Average Positions", "AveragePositions"), "scrape_player_average_positions"),
    "shotmap": SheetSpec("shotmap", ("Shotmap", "Match Shots"), "scrape_match_shots"),
}
SHEET_MODES = {"momentum": "momentum", "team-stats": "team_stats", "average-positions": "average_positions", "shotmap": "shotmap"}


class ScrapeBlocked(RuntimeError):
    """El transporte devolvio un error que no es un 404: nada de lo recibido hasta ahi es fiable."""


def error_code(response: object) -> int | None:
    """None si la respuesta trae datos; si no, el codigo del error (0 si no hubo respuesta)."""
    if not isinstance(response, dict):
        return 0
    error = response.get("error")
    if error is None:
        return None
    code = pd.to_numeric(pd.Series([error.get("code") if isinstance(error, dict) else None]), errors="coerce").iloc[0]
    return 0 if pd.isna(code) else int(code)


class BlockGuard:
    """Envuelve ``get_json``: 404 es dato ausente; cualquier otro error es un bloqueo y corta las llamadas."""

    def __init__(self, transport: Callable[[str], dict]) -> None:
        self._transport = transport
        self.calls = 0
        self.tripped = False
        self.reason: str | None = None

    def __call__(self, url: str) -> dict:
        if self.tripped:
            return {"error": {"code": 0, "reason": "guard_tripped"}}
        self.calls += 1
        response = self._transport(url)
        code = error_code(response)
        if code is not None and code != 404:
            reason = response.get("error", {}).get("reason", "") if isinstance(response, dict) and isinstance(response.get("error"), dict) else ""
            self.tripped = True
            self.reason = f"{code} {reason} en {url}".replace("  ", " ")
        return response


class Ledger:
    """Libro de registro append-only (JSON Lines): una linea por intento de partido."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, **entry: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def last_status(self, mode: str) -> dict[int, str]:
        last: dict[int, str] = {}
        for entry in self.entries():
            if entry.get("mode") == mode and entry.get("match_id") is not None:
                last[int(entry["match_id"])] = str(entry.get("status"))
        return last

    def settled_ids(self, mode: str) -> set[int]:
        return {match_id for match_id, status in self.last_status(mode).items() if status in SETTLED_STATUSES}


def run_batches(
    match_ids: Iterable[int],
    process_one: Callable[[int], dict[str, Any]],
    *,
    mode: str,
    guard: BlockGuard,
    ledger: Ledger,
    batch_size: int,
    pause_seconds: float,
    max_consecutive_failures: int = 3,
    progress_statuses: set[str] = PROGRESS_STATUSES,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    ids = [int(match_id) for match_id in match_ids]
    by_status: Counter[str] = Counter()
    stop_reason: str | None = None
    consecutive_failures = 0
    for index, match_id in enumerate(ids):
        started = time.monotonic()
        calls_before = guard.calls
        try:
            result = dict(process_one(match_id))
        except Exception as exc:  # un partido con error no detiene la tanda, pero cuenta para el corte por fallos seguidos
            result = {"status": "error", "note": f"{type(exc).__name__}: {exc}"}
        if guard.tripped:
            result = {**result, "status": "bloqueado", "note": guard.reason}
        result.update(mode=mode, match_id=match_id, calls=guard.calls - calls_before, seconds=round(time.monotonic() - started, 1))
        ledger.append(**result)
        by_status[result["status"]] += 1
        log(f"[{index + 1}/{len(ids)}] {mode} {match_id}: {result['status']} ({result['calls']} llamadas, {result['seconds']} s)")
        if guard.tripped:
            stop_reason = f"bloqueo: {guard.reason}"
            break
        consecutive_failures = 0 if result["status"] in progress_statuses else consecutive_failures + 1
        if consecutive_failures >= max_consecutive_failures:
            stop_reason = f"{consecutive_failures} fallos seguidos sin progreso (ultimo partido {match_id})"
            break
        if (index + 1) % batch_size == 0 and index + 1 < len(ids):
            sleep(pause_seconds)
    return {"processed": sum(by_status.values()), "by_status": dict(by_status), "stop_reason": stop_reason}


def _sheet_rows(workbook: Path) -> dict[str, int]:
    return {name: int(len(frame)) for name, frame in read_workbook_frames(workbook).items()}


def make_details_processor(*, master: pd.DataFrame, details_dir: Path, error_log: Path, scrape_fn: Callable[..., Any], guard: BlockGuard) -> Callable[[int], dict[str, Any]]:
    """Un partido por llamada a ``scrape_match_details``: asi un bloqueo nunca deja un workbook a medias."""
    numeric_ids = pd.to_numeric(master["match_id"], errors="coerce")

    def process(match_id: int) -> dict[str, Any]:
        workbook = details_dir / f"Sofascore_{match_id}.xlsx"
        if workbook.exists():  # un workbook incompleto puede ser lo unico que SofaScore tiene de ese partido
            return {"status": "saltado", "note": "ya existe un workbook: no se vuelve a descargar ni se borra"}
        scrape_fn(master[numeric_ids == match_id].iloc[[0]], details_dir, min_file_kb=15, error_log=error_log)
        if guard.tripped:
            workbook.unlink(missing_ok=True)
            return {"status": "bloqueado"}
        if not workbook.exists():
            return {"status": "vacio", "note": "el scraper no dejo workbook (menor de 15 KB o sin datos)"}
        if find_required_sheet_gaps(details_dir, {match_id}):
            workbook.unlink(missing_ok=True)
            return {"status": "vacio", "note": "faltan hojas requeridas (Team Stats, Player Stats o Average Positions)"}
        return {"status": "ok", "sheets": _sheet_rows(workbook)}

    return process


def heatmaps_frame(players: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {"player": name, "player_id": info.get("id"), "heatmap": str(list(info["heatmap"]))}
        for name, info in players.items()
        if isinstance(info, dict) and info.get("heatmap")
    ]
    return pd.DataFrame(rows, columns=["player", "player_id", "heatmap"])


def _write_atomically(workbook: Path, frames: dict[str, pd.DataFrame]) -> None:
    temporary = workbook.with_name(f"tmp_{workbook.name}")
    write_workbook_frames(temporary, frames)
    os.replace(temporary, workbook)


def make_heatmaps_processor(*, details_dir: Path, client: Any, guard: BlockGuard, force: bool) -> Callable[[int], dict[str, Any]]:
    def process(match_id: int) -> dict[str, Any]:
        workbook = details_dir / f"Sofascore_{match_id}.xlsx"
        if not workbook.exists():
            return {"status": "vacio", "note": "no hay workbook del partido"}
        frames = read_workbook_frames(workbook)
        sheet_name = next((name for name in HEATMAP_SHEET_NAMES if name in frames), HEATMAP_SHEET_NAMES[0])
        if not force and not frames.get(sheet_name, pd.DataFrame()).empty:
            return {"status": "saltado"}
        players = client.scrape_heatmaps(str(match_id))
        if guard.tripped:  # ScraperFC deja listas vacias ante un 403: nada de lo recibido es fiable
            return {"status": "bloqueado"}
        frame = heatmaps_frame(players)
        if frame.empty:
            return {"status": "vacio", "players": len(players), "note": "ningun jugador con puntos de heatmap"}
        frames[sheet_name] = frame
        _write_atomically(workbook, frames)
        points = sum(len(info["heatmap"]) for info in players.values() if isinstance(info, dict) and info.get("heatmap"))
        return {"status": "ok", "players": len(players), "players_with_points": int(len(frame)), "points": points}

    return process


def _match_ids(master: pd.DataFrame) -> list[int]:
    return sorted(pd.to_numeric(master["match_id"], errors="coerce").dropna().astype(int).tolist())


def record_administrative(ledger: Ledger, match_ids: Iterable[int], *, mode: str, note: str) -> list[int]:
    """Deja en el registro, una sola vez, los partidos que no se piden porque el listado no los marca como terminados."""
    settled = ledger.settled_ids(mode)
    recorded = sorted(int(match_id) for match_id in match_ids if int(match_id) not in settled)
    for match_id in recorded:
        ledger.append(mode=mode, match_id=match_id, status="vacio", note=note, calls=0, seconds=0.0)
    return recorded


def pending_details(master: pd.DataFrame, details_dir: Path, ledger: Ledger, *, retry_empty: bool = False, skip_ids: Iterable[int] = ()) -> list[int]:
    ids = _match_ids(master)
    gaps = find_required_sheet_gaps(details_dir, set(ids))
    skip = set(skip_ids) | (set() if retry_empty else {match_id for match_id, status in ledger.last_status("details").items() if status == "vacio"})
    # Solo los que no tienen workbook: uno incompleto no se vuelve a pedir ni se borra.
    return [match_id for match_id in ids if match_id in gaps and match_id not in skip and not (details_dir / f"Sofascore_{match_id}.xlsx").exists()]


def _heatmaps_done(workbook: Path) -> bool:
    frames = read_workbook_frames(workbook)
    return any(not frames[name].empty for name in HEATMAP_SHEET_NAMES if name in frames)


def pending_heatmaps(master: pd.DataFrame, details_dir: Path, ledger: Ledger, *, retry_empty: bool = False) -> list[int]:
    skip = set() if retry_empty else {match_id for match_id, status in ledger.last_status("heatmaps").items() if status == "vacio"}
    pending = []
    for match_id in _match_ids(master):
        workbook = details_dir / f"Sofascore_{match_id}.xlsx"
        if match_id in skip or not workbook.exists() or _heatmaps_done(workbook):
            continue
        pending.append(match_id)
    return pending


def _sheet_state(workbook: Path, names: tuple[str, ...]) -> tuple[str | None, bool]:
    """(nombre de la hoja si existe, si tiene filas)."""
    with pd.ExcelFile(workbook) as book:
        name = next((candidate for candidate in names if candidate in book.sheet_names), None)
        return name, name is not None and not pd.read_excel(book, sheet_name=name).empty


def dedupe_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """``id, id, id`` -> ``id, id_1, id_2``: el mismo esquema que deja ``scrape_match_details`` en los demas workbooks."""
    seen: Counter[str] = Counter()
    names = []
    for name in frame.columns:
        names.append(name if seen[name] == 0 else f"{name}_{seen[name]}")
        seen[name] += 1
    return frame.set_axis(names, axis=1)


def make_sheet_processor(spec: SheetSpec, *, details_dir: Path, client: Any, guard: BlockGuard) -> Callable[[int], dict[str, Any]]:
    """Una llamada por partido y hoja. Un 404 deja el partido como 'vacio': SofaScore no tiene esa hoja."""

    def process(match_id: int) -> dict[str, Any]:
        workbook = details_dir / f"Sofascore_{match_id}.xlsx"
        if not workbook.exists():
            return {"status": "vacio", "note": "no hay workbook del partido"}
        frames = read_workbook_frames(workbook)
        sheet_name = next((name for name in spec.names if name in frames), spec.names[0])
        if not frames.get(sheet_name, pd.DataFrame()).empty:
            return {"status": "saltado"}
        frame = getattr(client, spec.method)(str(match_id))
        if guard.tripped:  # ScraperFC devuelve un DataFrame vacio ante cualquier error, incluido un 403
            return {"status": "bloqueado"}
        if frame.empty:
            return {"status": "vacio", "note": f"SofaScore no devolvio {spec.names[0]} para este partido (404)"}
        frames[sheet_name] = dedupe_columns(frame)
        _write_atomically(workbook, frames)
        return {"status": "ok", spec.count_label: int(len(frame))}

    return process


def make_momentum_processor(*, details_dir: Path, client: Any, guard: BlockGuard) -> Callable[[int], dict[str, Any]]:
    return make_sheet_processor(SHEETS["momentum"], details_dir=details_dir, client=client, guard=guard)


def pending_sheet(spec: SheetSpec, master: pd.DataFrame, details_dir: Path, ledger: Ledger, *, retry_empty: bool = False) -> list[int]:
    skip = set() if retry_empty else {match_id for match_id, status in ledger.last_status(spec.key).items() if status == "vacio"}
    pending = []
    for match_id in _match_ids(master):
        workbook = details_dir / f"Sofascore_{match_id}.xlsx"
        if match_id in skip or not workbook.exists() or _sheet_state(workbook, spec.names)[1]:
            continue
        pending.append(match_id)
    return pending


def pending_momentum(master: pd.DataFrame, details_dir: Path, ledger: Ledger, *, retry_empty: bool = False) -> list[int]:
    return pending_sheet(SHEETS["momentum"], master, details_dir, ledger, retry_empty=retry_empty)


def list_season_events(guard: BlockGuard, events_url: Callable[[int], str], *, max_pages: int = 100) -> list[dict[str, Any]]:
    """Pagina el listado de la temporada. Un 404 cierra la paginacion; un bloqueo la invalida entera.

    ScraperFC corta el listado en cualquier respuesta sin ``events``, de modo que un 403 a mitad de camino
    pareceria el final y dejaria una temporada truncada: aqui se levanta ``ScrapeBlocked``.
    """
    events: list[dict[str, Any]] = []
    for page in range(max_pages):
        response = guard(events_url(page))
        if guard.tripped:
            raise ScrapeBlocked(guard.reason)
        if not isinstance(response, dict) or "events" not in response:
            break
        events.extend(response["events"])
        if response.get("hasNextPage") is False:
            break
    else:
        raise ValueError(f"el listado supera {max_pages} paginas: no se esperaba")
    if not events:
        raise ValueError("listado vacio: SofaScore no devolvio partidos para la temporada")
    return events


def fixtures_frame(events: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """Una fila por partido con lo que el listado ya trae: fecha (UTC sin zona, como el maestro de 2026), estado y sede."""
    rows = []
    for event in events:
        venue = event.get("venue") or {}
        coordinates = venue.get("venueCoordinates") or {}
        status = event.get("status") or {}
        rows.append(
            {
                "match_id": event.get("id"),
                "fecha": pd.to_datetime(event.get("startTimestamp"), unit="s", errors="coerce"),
                "estado": status.get("type"),
                "estado_detalle": status.get("description"),
                "tournament": (event.get("tournament") or {}).get("name"),
                "round_number": (event.get("roundInfo") or {}).get("round"),
                "home_id": (event.get("homeTeam") or {}).get("id"),
                "away_id": (event.get("awayTeam") or {}).get("id"),
                "home_score": (event.get("homeScore") or {}).get("current"),
                "away_score": (event.get("awayScore") or {}).get("current"),
                "estadio": venue.get("name"),
                "ciudad": (venue.get("city") or {}).get("name"),
                "venue_id": venue.get("id"),
                "venue_lat": coordinates.get("latitude"),
                "venue_lon": coordinates.get("longitude"),
                "aforo": venue.get("capacity"),
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset="match_id", keep="first").reset_index(drop=True)


def merge_fixtures_into_master(master: pd.DataFrame, fixtures: pd.DataFrame, columns: dict[str, str] = FIXTURE_MASTER_COLUMNS) -> pd.DataFrame:
    """Agrega fecha, estadio, ciudad y status al maestro por ``match_id``; un dato nuevo vacio no borra el que ya habia."""
    merged = master.copy()
    keyed = fixtures.assign(match_id=pd.to_numeric(fixtures["match_id"], errors="coerce")).drop_duplicates(subset="match_id").set_index("match_id")
    ids = pd.to_numeric(merged["match_id"], errors="coerce")
    for column, source in columns.items():
        if source not in keyed.columns:
            continue
        incoming = ids.map(keyed[source])
        merged[column] = incoming.where(incoming.notna(), merged[column]) if column in merged.columns else incoming
    return merged


def apply_fixtures_to_master(master_path: Path, fixtures_path: Path) -> pd.DataFrame:
    merged = merge_fixtures_into_master(pd.read_excel(master_path), pd.read_parquet(fixtures_path))
    temporary = master_path.with_name(f"tmp_{master_path.name}")
    merged.to_excel(temporary, index=False, engine="openpyxl")
    os.replace(temporary, master_path)
    return merged


def scrape_fixtures(guard: BlockGuard, events_url: Callable[[int], str], *, out_path: Path, ledger: Ledger, season: int, master_ids: set[int]) -> dict[str, Any]:
    """Descarga el listado de la temporada y lo guarda; solo escribe si el listado quedo completo."""
    calls_before = guard.calls
    try:
        events = list_season_events(guard, events_url)
    except ScrapeBlocked as exc:
        ledger.append(mode="fixtures", season=season, status="bloqueado", note=str(exc), calls=guard.calls - calls_before)
        raise
    frame = fixtures_frame(events)
    listed = set(pd.to_numeric(frame["match_id"], errors="coerce").dropna().astype(int))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out_path, index=False)
    summary = {
        "events": int(len(frame)),
        "with_date": int(frame["fecha"].notna().sum()),
        "with_venue": int(frame["estadio"].notna().sum()),
        "master_not_in_listing": sorted(master_ids - listed),
        "by_status": {str(key): int(value) for key, value in frame["estado"].value_counts(dropna=False).items()},
    }
    ledger.append(mode="fixtures", season=season, status="ok", calls=guard.calls - calls_before, **summary)
    return summary


class JsonlStore:
    """Datos de un modo que no cabe en un workbook (una linea JSON por partido); el estado de cada partido va en el ``Ledger``."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_lineups(payload: object) -> dict[str, Any] | None:
    """De ``/event/{id}/lineups`` solo lo que hace falta: la formacion declarada de cada lado y sus 11 titulares con la
    posicion (G, D, M o F) que ocuparon en ese partido. ``None`` si la respuesta no trae alineaciones."""
    if not isinstance(payload, dict) or not isinstance(payload.get("home"), dict) or not isinstance(payload.get("away"), dict):
        return None
    record: dict[str, Any] = {"confirmed": bool(payload.get("confirmed"))}
    for side in ("home", "away"):
        team = payload[side]
        starters = [
            {
                "player_id": item["player"].get("id"),
                "name": item["player"].get("shortName") or item["player"].get("name"),
                "position": item.get("position"),
                "shirt": item.get("shirtNumber", item.get("jerseyNumber")),
                "team_id": item.get("teamId"),
            }
            for item in team.get("players", [])
            if isinstance(item, dict) and isinstance(item.get("player"), dict) and not item.get("substitute")
        ]
        record[side] = {"formation": team.get("formation"), "team_id": next((s["team_id"] for s in starters if s["team_id"] is not None), None), "starters": starters}
    return record


def make_lineups_processor(*, url_for: Callable[[int], str], guard: BlockGuard, sink: Callable[[dict[str, Any]], None]) -> Callable[[int], dict[str, Any]]:
    """Una llamada por partido. Un 404 deja el partido como 'vacio' (SofaScore no tiene alineaciones) y no guarda nada."""

    def process(match_id: int) -> dict[str, Any]:
        response = guard(url_for(match_id))
        if guard.tripped:
            return {"status": "bloqueado"}
        if error_code(response) is not None:
            return {"status": "vacio", "note": "SofaScore no trae alineaciones de este partido (404)"}
        record = parse_lineups(response)
        if record is None:
            return {"status": "vacio", "note": "la respuesta no trae alineaciones"}
        sink({"match_id": match_id, **record})
        return {"status": "ok", "formations": [record["home"]["formation"], record["away"]["formation"]], "starters": [len(record["home"]["starters"]), len(record["away"]["starters"])]}

    return process


def pending_lineups(master: pd.DataFrame, ledger: Ledger, *, retry_empty: bool = False, skip_ids: Iterable[int] = ()) -> list[int]:
    done = {match_id for match_id, status in ledger.last_status("lineups").items() if status == "ok" or (status == "vacio" and not retry_empty)}
    skip = done | set(skip_ids)
    return [match_id for match_id in _match_ids(master) if match_id not in skip]


def image_extension(data: bytes) -> str | None:
    """Formato de una imagen por sus primeros bytes (el content-type del servidor no basta); None si no es PNG, JPEG ni WEBP."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def players_by_minutes(player_matches: Iterable[pd.DataFrame]) -> list[int]:
    """Ids de jugador de varias tablas ``player_match``, de más a menos minutos; los que nunca jugaron, al final y por id."""
    frame = pd.concat([part[["player_id", "minutesplayed"]] for part in player_matches], ignore_index=True)
    frame["player_id"] = pd.to_numeric(frame["player_id"], errors="coerce")
    frame = frame.dropna(subset=["player_id"]).astype({"player_id": int})
    frame["minutesplayed"] = pd.to_numeric(frame["minutesplayed"], errors="coerce").fillna(0)
    totals = frame.groupby("player_id", as_index=False)["minutesplayed"].sum().sort_values(["minutesplayed", "player_id"], ascending=[False, True])
    return totals["player_id"].astype(int).tolist()


def pending_player_images(player_ids: Iterable[int], images_dir: Path, ledger: Ledger, *, retry_empty: bool = False) -> list[int]:
    """Jugadores sin foto (en cualquier formato) y sin resultado final en el registro; cada id una vez y en el orden dado."""
    have = {int(path.stem) for path in images_dir.iterdir() if path.is_file() and path.stem.isdigit()} if images_dir.exists() else set()
    done = {player_id for player_id, status in ledger.last_status("player_images").items() if status == "ok" or (status == "vacio" and not retry_empty)}
    skip = have | done
    return [player_id for player_id in dict.fromkeys(int(item) for item in player_ids) if player_id not in skip]


def make_image_processor(*, url_for: Callable[[int], str], guard: BlockGuard, images_dir: Path) -> Callable[[int], dict[str, Any]]:
    """Una llamada por jugador. Un 404 lo deja como 'vacio' (SofaScore no tiene su foto) y no guarda nada.

    El registro usa ``match_id`` como clave de cualquier entidad: aquí es el id del jugador.
    """

    def process(player_id: int) -> dict[str, Any]:
        response = guard(url_for(player_id))
        if guard.tripped:
            return {"status": "bloqueado"}
        if error_code(response) is not None:
            return {"status": "vacio", "note": "SofaScore no tiene foto de este jugador (404)"}
        data = response.get("data") if isinstance(response, dict) else None
        extension = image_extension(bytes(data)) if isinstance(data, (bytes, bytearray)) else None
        if extension is None:
            return {"status": "error", "note": "la respuesta no es una imagen PNG, JPEG ni WEBP"}
        images_dir.mkdir(parents=True, exist_ok=True)
        target = images_dir / f"{player_id}.{extension}"
        partial = target.with_name(target.name + ".part")
        partial.write_bytes(data)
        partial.replace(target)
        return {"status": "ok", "bytes": len(data), "format": extension}

    return process


PLAYER_IMAGE_URL = "https://api.sofascore.com/api/v1/player/{player_id}/image"


def run_player_images(args: argparse.Namespace, base_dir: Path, batch_size: int, pause: float) -> int:
    """Fotos que faltan en ``gronestats/images/players`` para los jugadores de los bundles publicados de 2022 a ``--season``."""
    images_root = base_dir / "gronestats" / "images"
    images_dir = images_root / "players"
    ledger = Ledger(images_root / "scrape_ledger.jsonl")
    if args.match_ids:
        candidates = [int(token) for token in args.match_ids.split(",") if token.strip()]
    else:
        run_id = timestamp_id()
        tables = [PipelinePaths(base_dir=base_dir, league=args.league, season=season, run_id=run_id, release_id=run_id).dashboard_current_dir / "player_match.parquet" for season in range(2022, args.season + 1)]
        frames = [pd.read_parquet(table, columns=["player_id", "minutesplayed"]) for table in tables if table.exists()]
        candidates = players_by_minutes(frames) if frames else []
    pending = pending_player_images(candidates, images_dir, ledger, retry_empty=args.retry_empty)
    if args.limit:
        pending = pending[: args.limit]
    print(f"player-images: {len(candidates)} jugadores en los bundles, {len(pending)} sin foto pendientes, tandas de {batch_size}, pausa de {pause:g} s, intervalo mínimo {args.min_interval:g} s.")
    if args.dry_run or not pending:
        print("Plan (sin llamadas):", pending[:20], "..." if len(pending) > 20 else "")
        return 0

    # Las constantes de sofascore_session se leen al importarlo: fijarlas antes.
    os.environ.setdefault("GRONESTATS_SOFASCORE_ATTEMPTS", "2")
    os.environ["GRONESTATS_SOFASCORE_MIN_INTERVAL"] = str(args.min_interval)
    from gronestats.processing import sofascore_session

    guard = BlockGuard(sofascore_session.get_image)
    process = make_image_processor(url_for=lambda player_id: PLAYER_IMAGE_URL.format(player_id=player_id), guard=guard, images_dir=images_dir)
    summary = run_batches(pending, process, mode="player_images", guard=guard, ledger=ledger, batch_size=batch_size, pause_seconds=pause, progress_statuses=PROGRESS_STATUSES | {"vacio"})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 2 if summary["stop_reason"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrapeo de SofaScore por tandas, con libro de registro y parada al primer bloqueo.")
    parser.add_argument("mode", choices=("details", "heatmaps", *SHEET_MODES, "lineups", "player-images", "fixtures", "apply-fixtures"))
    parser.add_argument("--league", default="Liga 1 Peru")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--batch-size", type=int, default=None, help="Partidos por tanda (details: 5, heatmaps: 3).")
    parser.add_argument("--pause", type=float, default=None, help="Segundos entre tandas (details: 20, heatmaps: 45).")
    parser.add_argument("--min-interval", type=float, default=0.6, help="Segundos minimos entre llamadas.")
    parser.add_argument("--limit", type=int, default=None, help="Maximo de partidos en esta ejecucion.")
    parser.add_argument("--match-ids", default=None, help="Lista de match_id separados por coma (en vez de todos los pendientes); en player-images, de player_id.")
    parser.add_argument("--retry-empty", action="store_true", help="Reintenta los partidos que ya quedaron como 'vacio' en el registro.")
    parser.add_argument("--force", action="store_true", help="heatmaps: reescribe la hoja aunque ya tenga filas.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra el plan sin llamar a SofaScore.")
    return parser


BATCH_DEFAULTS = {"details": (5, 20.0), "heatmaps": (3, 45.0), "lineups": (20, 10.0), "player-images": (20, 10.0), **{mode: (10, 10.0) for mode in SHEET_MODES}}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    batch_size, pause = BATCH_DEFAULTS.get(args.mode, (5, 20.0))
    batch_size = args.batch_size or batch_size
    pause = args.pause if args.pause is not None else pause
    base_dir = Path(__file__).resolve().parents[2]
    if args.mode == "player-images":
        return run_player_images(args, base_dir, batch_size, pause)
    run_id = timestamp_id()
    paths = PipelinePaths(base_dir=base_dir, league=args.league, season=args.season, run_id=run_id, release_id=run_id)
    ledger = Ledger(paths.raw_dir / "scrape_ledger.jsonl")
    fixtures_path = paths.raw_dir / "fixtures_listing.parquet"
    # Las temporadas sin maestro propio (2022-2023) lo generan desde 0_Matches.xlsx: ahi van la fecha y el estadio.
    source_master = paths.season_dir / "0_Matches.xlsx"

    if args.mode in {"fixtures", "apply-fixtures"} and paths.legacy_master_raw_path.exists():
        print(f"{args.season} tiene maestro propio ({paths.legacy_master_raw_path.name}) con fecha y estadio: no hace falta '{args.mode}'.")
        return 1

    if args.mode == "apply-fixtures":
        merged = apply_fixtures_to_master(source_master, fixtures_path)
        print(f"{source_master}: {len(merged)} filas; con fecha {int(merged['fecha'].notna().sum())}, con estadio {int(merged['estadio'].notna().sum())}.")
        return 0

    master = pd.read_excel(latest_master_clean_path(paths))
    if args.mode == "fixtures":
        pending: list[int] = []
        print(f"fixtures {args.season}: un listado paginado (unas {1 + len(master) // 30 + 1} llamadas), sin consultar partido por partido.")
    elif args.match_ids:
        pending = [int(token) for token in args.match_ids.split(",") if token.strip()]
    elif args.mode in {"details", "lineups"}:
        # Un partido que el listado no marca como terminado (resultado administrativo, aplazado) no tiene datos en origen.
        administrative: set[int] = set()
        if fixtures_path.exists():
            listing = pd.read_parquet(fixtures_path)
            administrative = set(listing.loc[listing["estado"] != "finished", "match_id"].astype(int)) & set(_match_ids(master))
        if args.mode == "details":
            pending = pending_details(master, paths.raw_details_dir, ledger, retry_empty=args.retry_empty, skip_ids=administrative)
        else:
            pending = pending_lineups(master, ledger, retry_empty=args.retry_empty, skip_ids=administrative)
        if administrative and not args.dry_run:
            recorded = record_administrative(ledger, administrative, mode=args.mode, note="el listado no lo marca como terminado (resultado administrativo): sin datos de partido en origen")
            if recorded:
                print(f"registrados sin llamar a SofaScore (no terminados en el listado): {recorded}")
    elif args.mode == "heatmaps":
        pending = pending_heatmaps(master, paths.raw_details_dir, ledger, retry_empty=args.retry_empty)
    else:
        pending = pending_sheet(SHEETS[SHEET_MODES[args.mode]], master, paths.raw_details_dir, ledger, retry_empty=args.retry_empty)
    if args.limit:
        pending = pending[: args.limit]
    if args.mode != "fixtures":
        print(f"{args.mode} {args.season}: {len(pending)} partidos pendientes, tandas de {batch_size}, pausa de {pause:g} s, intervalo minimo {args.min_interval:g} s.")
    if args.dry_run or (not pending and args.mode != "fixtures"):
        print("Plan (sin llamadas):", pending[:20], "..." if len(pending) > 20 else "")
        return 0

    # Las constantes de sofascore_session se leen al importarlo: fijarlas antes.
    os.environ.setdefault("GRONESTATS_SOFASCORE_ATTEMPTS", "2")
    os.environ["GRONESTATS_SOFASCORE_MIN_INTERVAL"] = str(args.min_interval)
    os.environ["GRONESTATS_SKIP_HEATMAPS"] = "1"  # solo 'heatmaps' los pide, con su propio ejecutor
    import ScraperFC.sofascore as sofascore_module

    from gronestats.processing import data_loader_unprep, sofascore_session

    guard = BlockGuard(sofascore_session.get_json)
    sofascore_module.botasaurus_browser_get_json = guard  # despues del parche de data_loader_unprep

    if args.mode == "fixtures":
        season_id = data_loader_unprep.sofascore.get_valid_seasons(args.league)[str(args.season)]
        tournament_id = sofascore_module.comps[args.league]

        def events_url(page: int) -> str:
            return f"{sofascore_module.API_PREFIX}/unique-tournament/{tournament_id}/season/{season_id}/events/last/{page}"

        try:
            summary = scrape_fixtures(guard, events_url, out_path=fixtures_path, ledger=ledger, season=args.season, master_ids=set(_match_ids(master)))
        except ScrapeBlocked as exc:
            print(f"bloqueo: {exc}. No se guardo ningun listado.")
            return 2
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    progress = PROGRESS_STATUSES
    if args.mode == "details":
        process = make_details_processor(
            master=master,
            details_dir=paths.raw_details_dir,
            error_log=paths.raw_dir / "scrape_details_errors.txt",
            scrape_fn=data_loader_unprep.scrape_match_details,
            guard=guard,
        )
    elif args.mode == "heatmaps":
        process = make_heatmaps_processor(details_dir=paths.raw_details_dir, client=data_loader_unprep.sofascore, guard=guard, force=args.force)
    elif args.mode == "lineups":
        process = make_lineups_processor(
            url_for=lambda match_id: f"{sofascore_module.API_PREFIX}/event/{match_id}/lineups", guard=guard, sink=JsonlStore(paths.raw_dir / "lineups.jsonl").append
        )
        progress = PROGRESS_STATUSES | {"vacio"}  # un 404 es dato ausente en origen; un bloqueo real corta por el guard
    else:
        spec = SHEETS[SHEET_MODES[args.mode]]
        process = make_sheet_processor(spec, details_dir=paths.raw_details_dir, client=data_loader_unprep.sofascore, guard=guard)
        progress = PROGRESS_STATUSES | {"vacio"}  # un 404 es dato ausente en origen; un bloqueo real corta por el guard

    ledger_mode = args.mode if args.mode in {"details", "heatmaps", "lineups"} else SHEET_MODES[args.mode]
    summary = run_batches(pending, process, mode=ledger_mode, guard=guard, ledger=ledger, batch_size=batch_size, pause_seconds=pause, progress_statuses=progress)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 2 if summary["stop_reason"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
