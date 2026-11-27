from __future__ import annotations

from pathlib import Path

import pandas as pd

import pytest

from gronestats.processing.sofascore_batches import (
    BlockGuard,
    Ledger,
    ScrapeBlocked,
    JsonlStore,
    SHEETS,
    apply_fixtures_to_master,
    dedupe_columns,
    error_code,
    fixtures_frame,
    heatmaps_frame,
    image_extension,
    list_season_events,
    make_details_processor,
    make_heatmaps_processor,
    make_image_processor,
    make_lineups_processor,
    make_momentum_processor,
    make_sheet_processor,
    merge_fixtures_into_master,
    parse_lineups,
    pending_details,
    pending_lineups,
    pending_heatmaps,
    pending_momentum,
    pending_player_images,
    pending_sheet,
    players_by_minutes,
    record_administrative,
    run_batches,
    scrape_fixtures,
)


def _guard_with(responses: dict[str, dict]) -> tuple[BlockGuard, list[str]]:
    requested: list[str] = []

    def transport(url: str) -> dict:
        requested.append(url)
        return responses[url]

    return BlockGuard(transport), requested


def test_error_code_distinguishes_data_not_found_and_blocks() -> None:
    assert error_code({"heatmap": []}) is None
    assert error_code({"error": {"code": 404, "reason": "Not found"}}) == 404
    assert error_code({"error": {"code": 403, "reason": "Forbidden"}}) == 403
    assert error_code({"error": {"code": 0, "reason": "no_response"}}) == 0
    assert error_code({"error": "challenge"}) == 0
    assert error_code("no es un diccionario") == 0


def test_block_guard_treats_404_as_missing_data_and_keeps_going() -> None:
    guard, requested = _guard_with({"a": {"error": {"code": 404}}, "b": {"heatmap": [1]}})

    assert guard("a") == {"error": {"code": 404}}
    assert guard("b") == {"heatmap": [1]}
    assert guard.tripped is False
    assert guard.calls == 2
    assert requested == ["a", "b"]


def test_block_guard_stops_calling_the_network_after_the_first_block() -> None:
    guard, requested = _guard_with({"a": {"error": {"code": 403, "reason": "Forbidden"}}, "b": {"heatmap": [1]}})

    first = guard("a")
    second = guard("b")

    assert first["error"]["code"] == 403
    assert guard.tripped is True
    assert "403" in guard.reason and "a" in guard.reason
    assert second["error"]["code"] == 0
    assert requested == ["a"]
    assert guard.calls == 1


def test_ledger_appends_json_lines_and_reports_settled_matches_by_mode(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "raw" / "scrape_ledger.jsonl")
    ledger.append(mode="heatmaps", match_id=1, status="bloqueado")
    ledger.append(mode="heatmaps", match_id=1, status="ok")
    ledger.append(mode="heatmaps", match_id=2, status="vacio")
    ledger.append(mode="heatmaps", match_id=3, status="bloqueado")
    ledger.append(mode="details", match_id=4, status="ok")

    assert len(ledger.entries()) == 5
    assert all("ts" in entry for entry in ledger.entries())
    # Cuenta el último estado de cada partido: el 1 se resolvió después de bloquearse.
    assert ledger.settled_ids("heatmaps") == {1, 2}
    assert ledger.settled_ids("details") == {4}
    assert Ledger(tmp_path / "otro.jsonl").entries() == []


def _runner(tmp_path: Path, outcomes: dict[int, str], guard: BlockGuard):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    pauses: list[float] = []
    processed: list[int] = []

    def process_one(match_id: int) -> dict:
        processed.append(match_id)
        if outcomes[match_id] == "bloquear":
            guard.tripped, guard.reason = True, "403 Forbidden en /event/x"
            return {"status": "ok"}
        return {"status": outcomes[match_id]}

    def run(ids: list[int], **kwargs):
        return run_batches(ids, process_one, mode="heatmaps", guard=guard, ledger=ledger, batch_size=2, pause_seconds=30, sleep=pauses.append, log=lambda _: None, **kwargs)

    return run, ledger, pauses, processed


def test_run_batches_pauses_only_between_batches_and_records_every_match(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    run, ledger, pauses, processed = _runner(tmp_path, {1: "ok", 2: "ok", 3: "ok", 4: "saltado", 5: "ok"}, guard)

    summary = run([1, 2, 3, 4, 5])

    assert processed == [1, 2, 3, 4, 5]
    assert pauses == [30, 30]  # tras el partido 2 y tras el 4; no después del último
    assert summary["by_status"] == {"ok": 4, "saltado": 1}
    assert summary["stop_reason"] is None
    assert [entry["match_id"] for entry in ledger.entries()] == [1, 2, 3, 4, 5]


def test_run_batches_stops_at_the_first_block_and_marks_that_match_as_blocked(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    run, ledger, pauses, processed = _runner(tmp_path, {1: "ok", 2: "bloquear", 3: "ok", 4: "ok"}, guard)

    summary = run([1, 2, 3, 4])

    assert processed == [1, 2]
    assert pauses == []
    assert "bloqueo" in summary["stop_reason"] and "403" in summary["stop_reason"]
    statuses = {entry["match_id"]: entry["status"] for entry in ledger.entries()}
    assert statuses == {1: "ok", 2: "bloqueado"}


def test_run_batches_stops_after_consecutive_failures_without_progress(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    run, ledger, _, processed = _runner(tmp_path, {1: "ok", 2: "vacio", 3: "error", 4: "vacio", 5: "ok"}, guard)

    summary = run([1, 2, 3, 4, 5], max_consecutive_failures=3)

    assert processed == [1, 2, 3, 4]
    assert "3 fallos seguidos" in summary["stop_reason"]
    assert summary["by_status"] == {"ok": 1, "vacio": 2, "error": 1}


def test_run_batches_records_exceptions_as_errors_and_keeps_going(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    ledger = Ledger(tmp_path / "ledger.jsonl")

    def process_one(match_id: int) -> dict:
        if match_id == 1:
            raise RuntimeError("boom")
        return {"status": "ok"}

    summary = run_batches([1, 2], process_one, mode="details", guard=guard, ledger=ledger, batch_size=5, pause_seconds=0, sleep=lambda _: None, log=lambda _: None)

    assert summary["by_status"] == {"error": 1, "ok": 1}
    assert "RuntimeError: boom" in ledger.entries()[0]["note"]


def test_heatmaps_frame_keeps_only_players_with_points_and_stringifies_them() -> None:
    players = {
        "Jugador Uno": {"id": 101, "heatmap": [(0, 10), (15.5, 20)]},
        "Suplente": {"id": 102, "heatmap": []},
        "Raro": "no es un diccionario",
    }

    frame = heatmaps_frame(players)

    assert frame.columns.tolist() == ["player", "player_id", "heatmap"]
    assert frame["player"].tolist() == ["Jugador Uno"]
    assert frame["heatmap"].tolist() == ["[(0, 10), (15.5, 20)]"]


def _write_workbook(path: Path, **sheets: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name.replace("_", " "), index=False)


class _FakeClient:
    def __init__(self, guard: BlockGuard, players: dict, *, trip: bool = False) -> None:
        self.guard, self.players, self.trip = guard, players, trip

    def scrape_heatmaps(self, match_id: str) -> dict:
        if self.trip:
            self.guard.tripped, self.guard.reason = True, "403 Forbidden"
        return self.players


def test_heatmaps_processor_writes_the_sheet_and_skips_matches_that_already_have_it(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    workbook = tmp_path / "Sofascore_7.xlsx"
    _write_workbook(workbook, Team_Stats=pd.DataFrame({"a": [1]}), Heatmaps=pd.DataFrame(columns=["player", "player_id", "heatmap"]))
    players = {"Jugador Uno": {"id": 101, "heatmap": [(0, 10), (15.5, 20)]}, "Suplente": {"id": 102, "heatmap": []}}
    process = make_heatmaps_processor(details_dir=tmp_path, client=_FakeClient(guard, players), guard=guard, force=False)

    first = process(7)
    second = process(7)

    assert first == {"status": "ok", "players": 2, "players_with_points": 1, "points": 2}
    assert second == {"status": "saltado"}
    written = pd.read_excel(workbook, sheet_name="Heatmaps")
    assert written["player_id"].tolist() == [101]
    assert written["heatmap"].tolist() == ["[(0, 10), (15.5, 20)]"]
    assert pd.read_excel(workbook, sheet_name="Team Stats")["a"].tolist() == [1]  # el resto del workbook se conserva


def test_heatmaps_processor_reuses_the_legacy_sheet_name_and_never_writes_when_blocked(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    workbook = tmp_path / "Sofascore_8.xlsx"
    _write_workbook(workbook, Team_Stats=pd.DataFrame({"a": [1]}))
    blocked = make_heatmaps_processor(details_dir=tmp_path, client=_FakeClient(guard, {"X": {"id": 1, "heatmap": [(1, 1)]}}, trip=True), guard=guard, force=False)

    assert blocked(8) == {"status": "bloqueado"}
    assert pd.ExcelFile(workbook).sheet_names == ["Team Stats"]  # un bloqueo no deja heatmaps vacíos escritos

    guard2, _ = _guard_with({})
    legacy = tmp_path / "Sofascore_9.xlsx"
    _write_workbook(legacy, Team_Stats=pd.DataFrame({"a": [1]}), Heatmap=pd.DataFrame({"player": ["Viejo"], "heatmap": ["{'id': 5, 'heatmap': [(1, 2)]}"]}))
    process = make_heatmaps_processor(details_dir=tmp_path, client=_FakeClient(guard2, {"Nuevo": {"id": 6, "heatmap": [(3, 4)]}}, trip=False), guard=guard2, force=True)

    assert process(9)["status"] == "ok"
    assert pd.ExcelFile(legacy).sheet_names.count("Heatmap") == 1 and "Heatmaps" not in pd.ExcelFile(legacy).sheet_names


def test_a_heatmaps_sheet_with_rows_but_no_points_is_pending_and_gets_rescraped(tmp_path: Path) -> None:
    # Un scrape bloqueado dejó una fila por jugador con listas vacías: el libro pesa poco y no tiene heatmaps de verdad.
    empty = tmp_path / "Sofascore_20.xlsx"
    _write_workbook(empty, Team_Stats=pd.DataFrame({"a": [1]}), Heatmaps=pd.DataFrame({"player": ["A", "B"], "player_id": [1, 2], "heatmap": ["[]", "[]"]}))
    done = tmp_path / "Sofascore_21.xlsx"
    _write_workbook(done, Team_Stats=pd.DataFrame({"a": [1]}), Heatmaps=pd.DataFrame({"player": ["A"], "player_id": [1], "heatmap": ["[(1, 2)]"]}))
    legacy_done = tmp_path / "Sofascore_22.xlsx"
    _write_workbook(legacy_done, Team_Stats=pd.DataFrame({"a": [1]}), Heatmap=pd.DataFrame({"player": ["Viejo"], "heatmap": ["{'id': 5, 'heatmap': [(1, 2)]}"]}))
    legacy_empty = tmp_path / "Sofascore_23.xlsx"
    _write_workbook(legacy_empty, Team_Stats=pd.DataFrame({"a": [1]}), Heatmap=pd.DataFrame({"player": ["Viejo"], "heatmap": ["{'id': 5, 'heatmap': []}"]}))
    ledger = Ledger(tmp_path / "ledger.jsonl")

    assert pending_heatmaps(_master([20, 21, 22, 23]), tmp_path, ledger) == [20, 23]  # solo los que no tienen un solo punto

    guard, _ = _guard_with({})
    process = make_heatmaps_processor(details_dir=tmp_path, client=_FakeClient(guard, {"A": {"id": 1, "heatmap": [(5, 6)]}}), guard=guard, force=False)
    assert process(20)["status"] == "ok"  # ya no lo salta por tener filas
    assert pd.read_excel(empty, sheet_name="Heatmaps")["heatmap"].tolist() == ["[(5, 6)]"]
    assert process(21) == {"status": "saltado"}  # el que ya tiene puntos no se vuelve a pedir
    assert pending_heatmaps(_master([20, 21, 22, 23]), tmp_path, ledger) == [23]


def test_heatmaps_processor_reports_empty_when_the_match_has_no_points_or_no_workbook(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    _write_workbook(tmp_path / "Sofascore_10.xlsx", Team_Stats=pd.DataFrame({"a": [1]}))
    process = make_heatmaps_processor(details_dir=tmp_path, client=_FakeClient(guard, {"Suplente": {"id": 1, "heatmap": []}}), guard=guard, force=False)

    assert process(10)["status"] == "vacio"
    assert process(11)["status"] == "vacio"


def _master(ids: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"match_id": [str(match_id) for match_id in ids], "match_url": [f"https://www.sofascore.com/a-b/x#id:{match_id}" for match_id in ids]})


def _complete_workbook(path: Path) -> None:
    _write_workbook(
        path,
        Team_Stats=pd.DataFrame({"a": [1]}),
        Player_Stats=pd.DataFrame({"a": [1, 2]}),
        Average_Positions=pd.DataFrame({"a": [1]}),
        Shotmap=pd.DataFrame({"a": [1]}),
    )


def test_details_processor_accepts_a_complete_workbook_and_reports_sheet_rows(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    calls: list[str] = []

    def scrape(rows: pd.DataFrame, out_dir: Path, **_: object) -> None:
        calls.append(str(rows.iloc[0]["match_id"]))
        _complete_workbook(out_dir / f"Sofascore_{rows.iloc[0]['match_id']}.xlsx")

    process = make_details_processor(master=_master([21]), details_dir=tmp_path, error_log=tmp_path / "errors.txt", scrape_fn=scrape, guard=guard)

    result = process(21)

    assert calls == ["21"]
    assert result["status"] == "ok"
    assert result["sheets"]["Player Stats"] == 2


def test_details_processor_removes_partial_workbooks_when_blocked_or_incomplete(tmp_path: Path) -> None:
    guard, _ = _guard_with({})

    def scrape_blocked(rows: pd.DataFrame, out_dir: Path, **_: object) -> None:
        _complete_workbook(out_dir / f"Sofascore_{rows.iloc[0]['match_id']}.xlsx")
        guard.tripped, guard.reason = True, "403 Forbidden"

    blocked = make_details_processor(master=_master([22]), details_dir=tmp_path, error_log=tmp_path / "errors.txt", scrape_fn=scrape_blocked, guard=guard)
    assert blocked(22) == {"status": "bloqueado"}
    assert not (tmp_path / "Sofascore_22.xlsx").exists()

    guard2, _ = _guard_with({})

    def scrape_incomplete(rows: pd.DataFrame, out_dir: Path, **_: object) -> None:
        _write_workbook(out_dir / f"Sofascore_{rows.iloc[0]['match_id']}.xlsx", Team_Stats=pd.DataFrame({"a": [1]}))

    incomplete = make_details_processor(master=_master([23]), details_dir=tmp_path, error_log=tmp_path / "errors.txt", scrape_fn=scrape_incomplete, guard=guard2)
    assert incomplete(23)["status"] == "vacio"
    assert not (tmp_path / "Sofascore_23.xlsx").exists()


def test_details_processor_never_touches_a_workbook_that_already_exists(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    existing = tmp_path / "Sofascore_24.xlsx"
    _write_workbook(existing, Team_Stats=pd.DataFrame({"a": [1]}), Heatmaps=pd.DataFrame({"player": ["X"]}))  # incompleto: sin Player Stats
    calls: list[str] = []

    def scrape(rows: pd.DataFrame, out_dir: Path, **_: object) -> None:
        calls.append(str(rows.iloc[0]["match_id"]))

    process = make_details_processor(master=_master([24]), details_dir=tmp_path, error_log=tmp_path / "errors.txt", scrape_fn=scrape, guard=guard)

    result = process(24)

    assert result["status"] == "saltado"
    assert calls == []
    assert existing.exists()  # el workbook incompleto conserva sus hojas: otro partido pudo no tener datos en origen
    assert "Heatmaps" in pd.ExcelFile(existing).sheet_names


def test_pending_details_lists_only_matches_without_a_workbook(tmp_path: Path) -> None:
    _complete_workbook(tmp_path / "Sofascore_31.xlsx")
    _write_workbook(tmp_path / "Sofascore_32.xlsx", Team_Stats=pd.DataFrame({"a": [1]}))  # existe pero incompleto
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(mode="details", match_id=34, status="vacio")

    pending = pending_details(_master([31, 32, 33, 34]), tmp_path, ledger)

    assert pending == [33]
    assert pending_details(_master([31, 32, 33, 34]), tmp_path, ledger, retry_empty=True) == [33, 34]


def test_pending_details_can_skip_matches_the_listing_does_not_mark_as_finished(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")

    assert pending_details(_master([61, 62, 63]), tmp_path, ledger, skip_ids={62}) == [61, 63]


def test_record_administrative_marks_each_match_once_and_keeps_real_attempts(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(mode="details", match_id=71, status="vacio", note="404 en todo")

    first = record_administrative(ledger, {71, 72}, mode="details", note="estado canceled en el listado")
    second = record_administrative(ledger, {71, 72}, mode="details", note="estado canceled en el listado")

    assert first == [72] and second == []  # el 71 ya estaba resuelto; el 72 se registra una sola vez
    assert [(entry["match_id"], entry["status"]) for entry in ledger.entries()] == [(71, "vacio"), (72, "vacio")]
    assert ledger.entries()[1]["note"] == "estado canceled en el listado"


def test_run_batches_can_treat_empty_results_as_progress(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    run, _, _, processed = _runner(tmp_path, {1: "vacio", 2: "vacio", 3: "vacio", 4: "vacio", 5: "ok"}, guard)

    summary = run([1, 2, 3, 4, 5], max_consecutive_failures=3, progress_statuses={"ok", "saltado", "vacio"})

    assert processed == [1, 2, 3, 4, 5]  # un 404 repetido es dato ausente, no una parada
    assert summary["stop_reason"] is None


class _FakeMomentumClient:
    def __init__(self, guard: BlockGuard, frame: pd.DataFrame, *, trip: bool = False) -> None:
        self.guard, self.frame, self.trip = guard, frame, trip
        self.requested: list[str] = []

    def scrape_match_momentum(self, match_id: str) -> pd.DataFrame:
        self.requested.append(match_id)
        if self.trip:
            self.guard.tripped, self.guard.reason = True, "403 Forbidden"
        return self.frame


def test_momentum_processor_writes_the_sheet_keeping_the_rest_and_skips_matches_that_have_it(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    workbook = tmp_path / "Sofascore_41.xlsx"
    _write_workbook(workbook, Team_Stats=pd.DataFrame({"a": [1]}), Match_Momentum=pd.DataFrame(columns=["minute", "value"]))
    client = _FakeMomentumClient(guard, pd.DataFrame({"minute": [1.0, 2.0, 3.0], "value": [5, -3, 10]}))
    process = make_momentum_processor(details_dir=tmp_path, client=client, guard=guard)

    first = process(41)
    second = process(41)

    assert first == {"status": "ok", "points": 3}
    assert second == {"status": "saltado"}
    assert client.requested == ["41"]  # el segundo intento no llama a la red
    assert pd.read_excel(workbook, sheet_name="Match Momentum")["value"].tolist() == [5, -3, 10]
    assert pd.read_excel(workbook, sheet_name="Team Stats")["a"].tolist() == [1]


def test_momentum_processor_reports_missing_at_source_and_never_writes_when_blocked(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    workbook = tmp_path / "Sofascore_42.xlsx"
    _write_workbook(workbook, Team_Stats=pd.DataFrame({"a": [1]}))

    sin_datos = make_momentum_processor(details_dir=tmp_path, client=_FakeMomentumClient(guard, pd.DataFrame()), guard=guard)
    assert sin_datos(42)["status"] == "vacio"
    assert sin_datos(43)["status"] == "vacio"  # sin workbook
    assert pd.ExcelFile(workbook).sheet_names == ["Team Stats"]

    guard2, _ = _guard_with({})
    bloqueado = make_momentum_processor(details_dir=tmp_path, client=_FakeMomentumClient(guard2, pd.DataFrame({"minute": [1.0], "value": [1]}), trip=True), guard=guard2)
    assert bloqueado(42) == {"status": "bloqueado"}
    assert pd.ExcelFile(workbook).sheet_names == ["Team Stats"]


def test_pending_momentum_lists_workbooks_without_the_sheet_and_respects_the_ledger(tmp_path: Path) -> None:
    _write_workbook(tmp_path / "Sofascore_51.xlsx", Team_Stats=pd.DataFrame({"a": [1]}), Match_Momentum=pd.DataFrame({"minute": [1.0], "value": [2]}))
    _write_workbook(tmp_path / "Sofascore_52.xlsx", Team_Stats=pd.DataFrame({"a": [1]}), Match_Momentum=pd.DataFrame(columns=["minute", "value"]))
    _write_workbook(tmp_path / "Sofascore_53.xlsx", Team_Stats=pd.DataFrame({"a": [1]}))
    _write_workbook(tmp_path / "Sofascore_54.xlsx", Team_Stats=pd.DataFrame({"a": [1]}), Momentum=pd.DataFrame({"minute": [1.0], "value": [2]}))  # nombre antiguo
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(mode="momentum", match_id=53, status="vacio")

    master = _master([51, 52, 53, 54, 55])  # el 55 no tiene workbook

    assert pending_momentum(master, tmp_path, ledger) == [52]
    assert pending_momentum(master, tmp_path, ledger, retry_empty=True) == [52, 53]


class _FakeSheetClient:
    """Imita los métodos de ScraperFC: cada hoja se pide con su propio método y un error devuelve un DataFrame vacío."""

    def __init__(self, guard: BlockGuard, frames: dict[str, pd.DataFrame], *, trip: bool = False) -> None:
        self.guard, self.frames, self.trip = guard, frames, trip
        self.requested: list[tuple[str, str]] = []

    def __getattr__(self, method: str):
        def call(match_id: str) -> pd.DataFrame:
            self.requested.append((method, match_id))
            if self.trip:
                self.guard.tripped, self.guard.reason = True, "403 Forbidden"
            return self.frames.get(method, pd.DataFrame())

        return call


@pytest.mark.parametrize(
    ("key", "method", "sheet", "count"),
    [
        ("team_stats", "scrape_team_match_stats", "Team Stats", "rows"),
        ("average_positions", "scrape_player_average_positions", "Average Positions", "rows"),
        ("shotmap", "scrape_match_shots", "Shotmap", "rows"),
    ],
)
def test_sheet_processor_fills_each_missing_sheet_with_its_own_scraper(tmp_path: Path, key: str, method: str, sheet: str, count: str) -> None:
    guard, _ = _guard_with({})
    workbook = tmp_path / "Sofascore_81.xlsx"
    _write_workbook(workbook, Player_Stats=pd.DataFrame({"a": [1]}))
    client = _FakeSheetClient(guard, {method: pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})})
    process = make_sheet_processor(SHEETS[key], details_dir=tmp_path, client=client, guard=guard)

    first = process(81)
    second = process(81)

    assert first == {"status": "ok", count: 2}
    assert second == {"status": "saltado"}
    assert client.requested == [(method, "81")]  # solo la hoja que faltaba, y una sola vez
    assert pd.read_excel(workbook, sheet_name=sheet)["x"].tolist() == [1.0, 2.0]
    assert pd.read_excel(workbook, sheet_name="Player Stats")["a"].tolist() == [1]


def test_sheet_processor_reports_missing_at_source_and_never_writes_when_blocked(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    workbook = tmp_path / "Sofascore_82.xlsx"
    _write_workbook(workbook, Player_Stats=pd.DataFrame({"a": [1]}))

    empty = make_sheet_processor(SHEETS["shotmap"], details_dir=tmp_path, client=_FakeSheetClient(guard, {}), guard=guard)
    assert empty(82)["status"] == "vacio"
    assert pd.ExcelFile(workbook).sheet_names == ["Player Stats"]

    guard2, _ = _guard_with({})
    blocked = make_sheet_processor(SHEETS["shotmap"], details_dir=tmp_path, client=_FakeSheetClient(guard2, {"scrape_match_shots": pd.DataFrame({"x": [1]})}, trip=True), guard=guard2)
    assert blocked(82) == {"status": "bloqueado"}
    assert pd.ExcelFile(workbook).sheet_names == ["Player Stats"]


def test_sheet_processor_renames_duplicate_columns_like_the_details_scraper(tmp_path: Path) -> None:
    guard, _ = _guard_with({})
    workbook = tmp_path / "Sofascore_83.xlsx"
    _write_workbook(workbook, Player_Stats=pd.DataFrame({"a": [1]}))
    duplicated = pd.DataFrame([[10, "Ana", 7]], columns=["id", "name", "id"])  # el id del jugador y el del registro, como en average-positions
    process = make_sheet_processor(SHEETS["average_positions"], details_dir=tmp_path, client=_FakeSheetClient(guard, {"scrape_player_average_positions": duplicated}), guard=guard)

    assert process(83)["status"] == "ok"
    assert pd.read_excel(workbook, sheet_name="Average Positions").columns.tolist() == ["id", "name", "id_1"]


def test_dedupe_columns_suffixes_only_the_repeats() -> None:
    frame = pd.DataFrame([[1, 2, 3, 4]], columns=["id", "name", "id", "id"])

    assert dedupe_columns(frame).columns.tolist() == ["id", "name", "id_1", "id_2"]
    assert dedupe_columns(pd.DataFrame({"a": [1], "b": [2]})).columns.tolist() == ["a", "b"]


def test_pending_sheet_looks_at_the_sheet_of_each_spec_and_respects_the_ledger(tmp_path: Path) -> None:
    _write_workbook(tmp_path / "Sofascore_91.xlsx", Shotmap=pd.DataFrame({"x": [1]}), Average_Positions=pd.DataFrame(columns=["id"]))
    _write_workbook(tmp_path / "Sofascore_92.xlsx", Team_Stats=pd.DataFrame({"a": [1]}))
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(mode="shotmap", match_id=92, status="vacio")
    master = _master([91, 92, 93])  # el 93 no tiene workbook

    assert pending_sheet(SHEETS["shotmap"], master, tmp_path, ledger) == []
    assert pending_sheet(SHEETS["shotmap"], master, tmp_path, ledger, retry_empty=True) == [92]
    assert pending_sheet(SHEETS["average_positions"], master, tmp_path, ledger) == [91, 92]
    assert pending_sheet(SHEETS["team_stats"], master, tmp_path, ledger) == [91]


def _event(match_id: int, *, timestamp: int | None = 1666217700, status: str = "finished", home_score: int | None = 1, venue: dict | None = None, round_number: int = 3) -> dict:
    return {
        "id": match_id,
        "startTimestamp": timestamp,
        "status": {"type": status, "description": "Ended" if status == "finished" else "Postponed"},
        "tournament": {"name": "Liga 1, Apertura"},
        "roundInfo": {"round": round_number},
        "homeTeam": {"id": 10},
        "awayTeam": {"id": 20},
        "homeScore": {"current": home_score} if home_score is not None else {},
        "awayScore": {"current": 0} if home_score is not None else {},
        "venue": venue,
    }


def test_list_season_events_follows_pages_until_the_last_one_and_stops_on_a_missing_page() -> None:
    pages = {
        "p0": {"events": [_event(1), _event(2)], "hasNextPage": True},
        "p1": {"events": [_event(3)], "hasNextPage": False},
    }
    guard, requested = _guard_with(pages)

    events = list_season_events(guard, lambda page: f"p{page}")

    assert [event["id"] for event in events] == [1, 2, 3]
    assert requested == ["p0", "p1"]  # hasNextPage=False evita pedir una página de más

    guard2, requested2 = _guard_with({"p0": {"events": [_event(1)]}, "p1": {"error": {"code": 404}}})
    assert [event["id"] for event in list_season_events(guard2, lambda page: f"p{page}")] == [1]
    assert requested2 == ["p0", "p1"]


def test_list_season_events_refuses_a_truncated_listing_when_blocked_or_empty() -> None:
    guard, _ = _guard_with({"p0": {"events": [_event(1)], "hasNextPage": True}, "p1": {"error": {"code": 403, "reason": "Forbidden"}}})
    with pytest.raises(ScrapeBlocked, match="403"):
        list_season_events(guard, lambda page: f"p{page}")  # un 403 a mitad no se confunde con el fin del listado

    guard2, _ = _guard_with({"p0": {"error": {"code": 404}}})
    with pytest.raises(ValueError, match="vacio"):
        list_season_events(guard2, lambda page: f"p{page}")


def test_fixtures_frame_extracts_date_status_and_venue() -> None:
    venue = {"name": "Estadio de la UNSA", "id": 5172, "capacity": 60000, "city": {"name": "Arequipa"}, "venueCoordinates": {"latitude": -16.4, "longitude": -71.5}}
    events = [_event(1, venue=venue), _event(2, timestamp=None, status="postponed", home_score=None, venue=None), _event(1, venue=venue)]

    frame = fixtures_frame(events)

    assert frame["match_id"].tolist() == [1, 2]  # un partido repetido en el listado queda una sola vez
    first = frame.iloc[0]
    assert first["fecha"] == pd.Timestamp("2022-10-19 22:15:00")  # UTC sin zona, como el maestro de 2026
    assert (first["estado"], first["estadio"], first["ciudad"], first["venue_id"], first["aforo"]) == ("finished", "Estadio de la UNSA", "Arequipa", 5172, 60000)
    assert (first["venue_lat"], first["venue_lon"], first["home_score"], first["round_number"]) == (-16.4, -71.5, 1, 3)
    second = frame.iloc[1]
    assert pd.isna(second["fecha"]) and second["estado"] == "postponed" and pd.isna(second["home_score"]) and pd.isna(second["estadio"])


def test_merge_fixtures_into_master_adds_date_venue_and_city_without_dropping_rows() -> None:
    master = pd.DataFrame({"match_id": [1, 2, 3], "home": ["A", "B", "C"], "home_score": [1, None, 2]})
    fixtures = pd.DataFrame(
        {
            "match_id": [1, 2],
            "fecha": [pd.Timestamp("2022-02-01 20:00"), pd.NaT],
            "estadio": ["Nacional", None],
            "ciudad": ["Lima", None],
        }
    )

    merged = merge_fixtures_into_master(master, fixtures)

    assert merged["match_id"].tolist() == [1, 2, 3]
    assert merged["home"].tolist() == ["A", "B", "C"]
    assert merged["estadio"].iloc[0] == "Nacional" and pd.isna(merged["estadio"].iloc[2])
    assert merged["fecha"].iloc[0] == pd.Timestamp("2022-02-01 20:00") and merged["fecha"].isna().tolist() == [False, True, True]

    # Idempotente, y un valor que el listado ya no trae no borra el que había.
    again = merge_fixtures_into_master(merged, fixtures.assign(estadio=[None, None]))
    assert again["estadio"].iloc[0] == "Nacional"


def test_scrape_fixtures_saves_the_listing_and_reports_what_the_master_has_that_the_listing_lacks(tmp_path: Path) -> None:
    guard, _ = _guard_with({"p0": {"events": [_event(1), _event(2, status="postponed", home_score=None)], "hasNextPage": False}})
    ledger = Ledger(tmp_path / "ledger.jsonl")
    out = tmp_path / "raw" / "fixtures_listing.parquet"

    summary = scrape_fixtures(guard, lambda page: f"p{page}", out_path=out, ledger=ledger, season=2022, master_ids={1, 2, 9})

    assert summary["events"] == 2 and summary["master_not_in_listing"] == [9]
    assert summary["by_status"] == {"finished": 1, "postponed": 1}
    assert pd.read_parquet(out)["match_id"].tolist() == [1, 2]
    assert ledger.entries()[0]["mode"] == "fixtures" and ledger.entries()[0]["status"] == "ok"


def test_scrape_fixtures_writes_nothing_when_the_listing_is_blocked_midway(tmp_path: Path) -> None:
    guard, _ = _guard_with({"p0": {"events": [_event(1)], "hasNextPage": True}, "p1": {"error": {"code": 403, "reason": "Forbidden"}}})
    ledger = Ledger(tmp_path / "ledger.jsonl")
    out = tmp_path / "fixtures_listing.parquet"

    with pytest.raises(ScrapeBlocked):
        scrape_fixtures(guard, lambda page: f"p{page}", out_path=out, ledger=ledger, season=2022, master_ids={1})

    assert not out.exists()  # un listado truncado habria parecido una temporada con menos partidos
    assert ledger.entries()[0]["status"] == "bloqueado"


def test_merge_fixtures_into_master_carries_the_event_status_as_status() -> None:
    master = pd.DataFrame({"match_id": [1, 2], "home_score": [3, 1]})
    fixtures = pd.DataFrame({"match_id": [1, 2], "estado": ["postponed", "finished"], "fecha": [pd.Timestamp("2023-02-04 20:30"), pd.Timestamp("2023-02-05 15:00")]})

    merged = merge_fixtures_into_master(master, fixtures)

    # Un 3-0 con estado 'postponed' es un resultado administrativo: tiene marcador pero no se jugó.
    assert merged["status"].tolist() == ["postponed", "finished"]
    assert "estadio" not in merged.columns  # lo que el listado no trae no se inventa


def test_apply_fixtures_to_master_rewrites_the_source_workbook(tmp_path: Path) -> None:
    source = tmp_path / "0_Matches.xlsx"
    pd.DataFrame({"match_id": [1, 2], "home": ["A", "B"]}).to_excel(source, index=False)
    listing = tmp_path / "fixtures.parquet"
    pd.DataFrame(
        {"match_id": [1, 2], "fecha": [pd.Timestamp("2022-02-01 20:00"), pd.Timestamp("2022-02-02 20:00")], "estadio": ["N", "M"], "ciudad": ["Lima", "Lima"]}
    ).to_parquet(listing)

    apply_fixtures_to_master(source, listing)

    written = pd.read_excel(source)
    assert written.columns.tolist() == ["match_id", "home", "fecha", "estadio", "ciudad"]
    assert written["estadio"].tolist() == ["N", "M"]


def _lineups_payload(*, home_formation: str | None = "4-3-3", starters_home: int = 11, confirmed: bool = True) -> dict:
    def side(formation: str | None, team_id: int, n_starters: int, positions: str) -> dict:
        players = [
            {
                "player": {"id": team_id * 100 + i, "name": f"Jugador {i}", "shortName": f"J. {i}", "position": "M"},
                "position": positions[i % len(positions)],
                "shirtNumber": i + 1,
                "substitute": i >= n_starters,
                "teamId": team_id,
            }
            for i in range(n_starters + 3)
        ]
        return {"players": players, "formation": formation, "supportStaff": []}

    return {"confirmed": confirmed, "home": side(home_formation, 7, starters_home, "GDDDDMMMFFF"), "away": side("4-4-2", 8, 11, "GDDDDMMMMFF"), "statisticalVersion": 1}


def test_parse_lineups_keeps_the_declared_formation_and_only_the_starters() -> None:
    record = parse_lineups(_lineups_payload())

    assert record["confirmed"] is True
    assert record["home"]["formation"] == "4-3-3" and record["away"]["formation"] == "4-4-2"
    assert record["home"]["team_id"] == 7 and record["away"]["team_id"] == 8
    assert len(record["home"]["starters"]) == 11  # los 3 suplentes no entran
    assert record["home"]["starters"][0] == {"player_id": 700, "name": "J. 0", "position": "G", "shirt": 1, "team_id": 7}
    assert [starter["position"] for starter in record["home"]["starters"]].count("D") == 4


def test_parse_lineups_returns_none_when_the_response_has_no_lineups() -> None:
    assert parse_lineups({"error": {"code": 404}}) is None
    assert parse_lineups({"confirmed": True, "home": {}, "away": "x"}) is None
    assert parse_lineups("no es un diccionario") is None
    assert parse_lineups(_lineups_payload(home_formation=None))["home"]["formation"] is None  # sin formación declarada también es un dato


def test_lineups_processor_stores_the_record_and_distinguishes_missing_from_blocked(tmp_path: Path) -> None:
    store = JsonlStore(tmp_path / "raw" / "lineups.jsonl")
    guard, requested = _guard_with({"u/1": _lineups_payload(), "u/2": {"error": {"code": 404}}, "u/3": {"error": {"code": 403, "reason": "Forbidden"}}})
    process = make_lineups_processor(url_for=lambda match_id: f"u/{match_id}", guard=guard, sink=store.append)

    ok = process(1)
    missing = process(2)
    blocked = process(3)

    assert ok == {"status": "ok", "formations": ["4-3-3", "4-4-2"], "starters": [11, 11]}
    assert missing["status"] == "vacio" and "404" in missing["note"]
    assert blocked == {"status": "bloqueado"}
    assert requested == ["u/1", "u/2", "u/3"]
    records = store.records()
    assert [record["match_id"] for record in records] == [1]  # solo el partido que sí tenía datos
    assert records[0]["home"]["formation"] == "4-3-3"


def test_pending_lineups_skips_done_and_empty_matches_and_the_given_ids(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(mode="lineups", match_id=1, status="ok")
    ledger.append(mode="lineups", match_id=2, status="vacio")
    ledger.append(mode="lineups", match_id=3, status="error")
    master = _master([1, 2, 3, 4, 5])

    assert pending_lineups(master, ledger, skip_ids={5}) == [3, 4]  # el error se reintenta
    assert pending_lineups(master, ledger, retry_empty=True) == [2, 3, 4, 5]  # lo ya resuelto con datos no se vuelve a pedir


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 8


def test_image_extension_reads_the_format_from_the_bytes_not_from_the_server() -> None:
    assert image_extension(PNG) == "png"
    assert image_extension(JPG) == "jpg"
    assert image_extension(WEBP) == "webp"
    assert image_extension(b"<html>challenge</html>") is None
    assert image_extension(b"") is None


def test_players_by_minutes_orders_by_total_minutes_and_keeps_players_who_never_played() -> None:
    frames = [
        pd.DataFrame({"player_id": [1, 2, 3], "minutesplayed": [90, 10, 0]}),
        pd.DataFrame({"player_id": [2, 4, 3], "minutesplayed": [90, 0, None]}),
    ]

    assert players_by_minutes(frames) == [2, 1, 3, 4]  # el 2 suma 100 y el 1 suma 90; los de 0 minutos al final, por id


def test_player_image_processor_saves_the_file_with_its_real_format_and_tells_missing_from_blocked(tmp_path: Path) -> None:
    images = tmp_path / "players"
    guard, requested = _guard_with({"u/1": {"content_type": "image/png", "data": PNG}, "u/2": {"error": {"code": 404}}, "u/3": {"error": {"code": 403, "reason": "Forbidden"}}})
    process = make_image_processor(url_for=lambda player_id: f"u/{player_id}", guard=guard, images_dir=images)

    ok = process(1)
    missing = process(2)
    blocked = process(3)

    assert ok == {"status": "ok", "bytes": len(PNG), "format": "png"}
    assert (images / "1.png").read_bytes() == PNG
    assert missing["status"] == "vacio" and "404" in missing["note"]
    assert blocked == {"status": "bloqueado"}
    assert requested == ["u/1", "u/2", "u/3"]
    assert sorted(path.name for path in images.iterdir()) == ["1.png"]  # ni el 404 ni el bloqueo dejan archivos, tampoco temporales


def test_player_image_processor_does_not_store_a_response_that_is_not_an_image(tmp_path: Path) -> None:
    images = tmp_path / "players"
    guard, _ = _guard_with({"u/1": {"content_type": "image/png", "data": b"<html>challenge</html>"}})
    process = make_image_processor(url_for=lambda player_id: f"u/{player_id}", guard=guard, images_dir=images)

    result = process(1)

    assert result["status"] == "error"
    assert not images.exists() or not any(images.iterdir())


def test_pending_player_images_skips_photos_in_any_format_and_settled_ledger_entries(tmp_path: Path) -> None:
    images = tmp_path / "players"
    images.mkdir()
    (images / "10.png").write_bytes(PNG)
    (images / "11.webp").write_bytes(WEBP)
    (images / "notes.txt").write_text("no es una foto", encoding="utf-8")
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(mode="player_images", match_id=12, status="ok")
    ledger.append(mode="player_images", match_id=13, status="vacio")
    ledger.append(mode="player_images", match_id=14, status="error")
    ledger.append(mode="lineups", match_id=15, status="ok")  # otro modo: no cuenta
    ids = [10, 11, 12, 13, 14, 15, 16, 16]

    assert pending_player_images(ids, images, ledger) == [14, 15, 16]  # el error se reintenta y los repetidos cuentan una vez
    assert pending_player_images(ids, images, ledger, retry_empty=True) == [13, 14, 15, 16]
