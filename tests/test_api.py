from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gronestats.api.app import create_app
from gronestats.web_bundle.build import build_web_bundle
from tests.fixtures.web_inputs import PNG, SEASONS, make_web_inputs


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("api")
    inputs = make_web_inputs(root / "inputs")
    out = root / "web"
    build_web_bundle(inputs.data_dir, inputs.analytics_dir, inputs.analytics_dir, out, seasons=SEASONS, images_dir=inputs.images_dir)
    images = root / "images"
    (images / "players").mkdir(parents=True)
    (images / "teams").mkdir()
    (images / "players" / "11.png").write_bytes(PNG)
    (images / "teams" / "1.png").write_bytes(PNG)
    return {"out": out, "images": images, "inputs": inputs, "root": root}


@pytest.fixture(scope="module")
def client(world) -> TestClient:
    return TestClient(create_app(bundle_dir=world["out"], images_dir=world["images"]))


def test_release_reports_the_version_and_the_seasons(client: TestClient) -> None:
    body = client.get("/v1/release").json()

    assert body["schema_version"] == "1.0.0" and body["release_id"]
    assert body["seasons"] == [2026, 2025]
    assert {"xg", "elo"} <= set(body["models"])


def test_seasons_list_their_tournaments_and_rounds(client: TestClient) -> None:
    body = client.get("/v1/seasons").json()
    season = next(item for item in body["seasons"] if item["season"] == 2026)

    assert season["tournaments"] == ["Apertura", "Clausura", "Acumulada"]
    assert season["rounds"] == {"Apertura": 3, "Clausura": 3}
    assert body["release_id"]


def test_standings_come_ordered_with_team_names_colors_and_crests(client: TestClient) -> None:
    body = client.get("/v1/seasons/2026/standings", params={"tournament": "Apertura"}).json()
    rows = body["rows"]

    assert [row["pos"] for row in rows] == [1, 2, 3, 4]
    assert body["round_number"] == 3 and body["rounds"] == 3
    assert {"name", "color", "level", "pts", "dg"} <= set(rows[0])
    crests = {row["team_id"]: row["crest"] for row in rows}
    assert crests[1] == "/assets/teams/1.png" and crests[2] is None  # solo hay escudo del equipo 1


def test_standings_after_an_earlier_round_and_error_cases(client: TestClient) -> None:
    first = client.get("/v1/seasons/2026/standings", params={"tournament": "Clausura", "round": 1}).json()

    assert max(row["pj"] for row in first["rows"]) == 1
    assert client.get("/v1/seasons/1999/standings").status_code == 404
    assert client.get("/v1/seasons/2026/standings", params={"tournament": "Verano"}).status_code == 422


def test_team_strip_has_result_rival_altitude_formation_importance_and_probabilities(client: TestClient) -> None:
    body = client.get("/v1/teams/1/seasons/2026/matches").json()
    apertura = body["tournaments"]["Apertura"]
    first = apertura[0]

    assert body["team"]["name"] == "Alfa" and len(apertura) == 3 and len(body["tournaments"]["Clausura"]) == 3
    assert first["round_number"] == 1 and first["is_home"] is True
    assert first["rival"]["name"] == "Beta" and first["rival"]["level"] == "Competitivo"
    assert first["result"] in {"G", "E", "P"} and first["goals_for"] is not None
    assert first["formation"] == "4-3-3" and first["defenders_ok"] is True
    assert first["importance"]["threshold_used"] == 40 and first["importance"]["band_name"] == "Baja"
    assert first["p_title_before"] == pytest.approx(0.1) and first["p_title_after"] == pytest.approx(0.2)
    assert first["xg_for"] > 0 and first["xg_against"] > 0
    assert first["altitude_m"] == 100  # juega en su estadio
    away = apertura[1]
    assert away["is_home"] is True and apertura[2]["is_home"] is True  # Alfa es local en las tres fechas del calendario sintético
    assert apertura[2]["altitude_m"] == 100


def test_team_strip_flags_the_declared_formation_that_misses_the_defenders_and_keeps_postponed_matches(client: TestClient) -> None:
    beta = client.get("/v1/teams/2/seasons/2026/matches").json()["tournaments"]
    first = beta["Apertura"][0]
    postponed = next(match for match in beta["Clausura"] if match["status"] == "postponed")

    assert first["is_home"] is False and first["defenders_ok"] is False  # el visitante de ese partido tiene la formación marcada
    assert first["altitude_m"] == 100 and first["altitude_diff_m"] == 100 - 200  # juega a 100 m y su sede habitual está a 200 m
    assert postponed["result"] is None and postponed["goals_for"] is None
    assert postponed["importance"] is None  # sin partido jugado no hay importancia


def test_title_race_returns_one_series_per_team(client: TestClient) -> None:
    body = client.get("/v1/teams/1/seasons/2026/title-race", params={"tournament": "Apertura"}).json()

    assert body["tournament"] == "Apertura" and len(body["teams"]) == 4
    series = next(team for team in body["teams"] if team["team_id"] == 1)["series"]
    assert [point["k"] for point in series] == [0, 1, 2, 3]
    assert series[0]["p_title"] == pytest.approx(0.1)


def test_team_players_are_ordered_by_minutes_and_carry_the_photo_url(client: TestClient) -> None:
    body = client.get("/v1/teams/1/seasons/2026/players").json()
    players = body["players"]

    assert [player["player_id"] for player in players] == [11, 12]
    assert players[0]["photo"] == "/assets/players/11.png" and players[1]["photo"] is None
    assert players[0]["minutes"] > players[1]["minutes"] and players[0]["xg"] > 0


def test_match_detail_has_both_teams_shots_and_players(client: TestClient) -> None:
    body = client.get("/v1/matches/2026010").json()

    assert body["match"]["home"]["team"]["name"] == "Alfa" and body["match"]["away"]["team"]["name"] == "Beta"
    assert body["match"]["home"]["formation"] == "4-3-3" and body["match"]["away"]["defenders_ok"] is False
    assert len(body["shots"]) == 4 and {"x", "y", "xg", "is_home", "player_name"} <= set(body["shots"][0])
    assert body["match"]["home"]["xg"] == pytest.approx(sum(shot["xg"] for shot in body["shots"] if shot["is_home"]))
    assert len(body["players"]) == 4
    assert client.get("/v1/matches/1").status_code == 404


def test_player_profile_totals_by_season_and_a_missing_season_is_null_not_zero(client: TestClient) -> None:
    body = client.get("/v1/players/11", params={"season": 2026}).json()

    assert body["player"]["name"] == "Jugador 11" and body["player"]["photo"] == "/assets/players/11.png"
    assert {item["season"] for item in body["seasons"]} == {2025, 2026}
    assert body["season_stats"]["season"] == 2026 and body["season_stats"]["matches"] > 0 and body["season_stats"]["minutes"] > 0
    empty = client.get("/v1/players/11", params={"season": 2024}).json()
    assert empty["season_stats"] is None and empty["missing_reason"] == "no_data_for_season"
    assert client.get("/v1/players/999").status_code == 404


def test_player_shots_and_heatmap_report_missing_data_instead_of_zeros(client: TestClient) -> None:
    shots = client.get("/v1/players/11/shots", params={"season": 2026}).json()
    heat = client.get("/v1/players/11/heatmap", params={"season": 2026}).json()
    no_shots = client.get("/v1/players/12/shots", params={"season": 2026}).json()
    no_heat = client.get("/v1/players/12/heatmap", params={"season": 2026}).json()

    assert shots["shots"] and {"x", "y", "xg", "is_goal", "match_id"} <= set(shots["shots"][0]) and shots["missing_reason"] is None
    assert heat["total"] == 10 and heat["cols"] == 20 and all(0 <= cell["ix"] < 20 and 0 <= cell["iy"] < 20 for cell in heat["cells"])
    assert no_shots["shots"] == [] and no_shots["missing_reason"] == "no_data"
    assert no_heat["total"] == 0 and no_heat["missing_reason"] == "no_data"


def test_status_exposes_coverage_known_gaps_models_and_the_release_log(client: TestClient) -> None:
    body = client.get("/v1/status").json()

    assert {"season", "kind", "expected", "present", "missing"} <= set(body["coverage"][0])
    assert len(body["known_gaps"]) == 1 and body["known_gaps"][0]["kind"] == "venue"
    assert {model["model"] for model in body["models"]} == {"xg", "elo"}
    assert body["release_log"] and body["stale"] is False and body["data_as_of"]


def test_images_are_served_and_unknown_files_are_404(client: TestClient) -> None:
    ok = client.get("/assets/players/11.png")

    assert ok.status_code == 200 and ok.content == PNG
    assert client.get("/assets/players/nope.png").status_code == 404


def test_reload_is_only_allowed_from_localhost(world) -> None:
    app = create_app(bundle_dir=world["out"], images_dir=world["images"])
    local = TestClient(app)
    remote = TestClient(app, client=("203.0.113.9", 50000))

    assert local.post("/internal/reload").json()["reloaded"] is True
    assert remote.post("/internal/reload").status_code == 403


def test_an_invalid_release_leaves_the_previous_one_serving(world) -> None:
    copy = world["root"] / "broken"
    shutil.copytree(world["out"], copy)
    app = create_app(bundle_dir=copy, images_dir=world["images"])
    client = TestClient(app)
    before = client.get("/v1/release").json()["release_id"]

    # un release nuevo al que le falta una tabla, y el puntero `current` apuntándolo
    good = next((copy / "releases").iterdir())
    bad = copy / "releases" / "bad"
    shutil.copytree(good, bad)
    (bad / "standings.parquet").unlink()
    manifest = json.loads((copy / "current" / "manifest.json").read_text(encoding="utf-8"))
    (copy / "current" / "manifest.json").write_text(json.dumps({**manifest, "release_id": "bad"}), encoding="utf-8")
    reloaded = client.post("/internal/reload")

    assert reloaded.status_code == 409 and "standings" in reloaded.json()["error"]
    assert client.get("/v1/release").json()["release_id"] == before
    assert client.get("/v1/seasons/2026/standings").status_code == 200  # sigue sirviendo el release anterior


def test_responses_carry_an_etag_per_release_and_answer_304_when_unchanged(client: TestClient) -> None:
    first = client.get("/v1/seasons")
    again = client.get("/v1/seasons", headers={"If-None-Match": first.headers["etag"]})

    assert first.headers["cache-control"].startswith("public") and first.headers["etag"].startswith('W/"')
    assert again.status_code == 304
