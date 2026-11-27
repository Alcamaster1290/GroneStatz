from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from gronestats.web_bundle.schema import SCHEMA_VERSION, TABLES
from gronestats.web_bundle.validate import validate_bundle


def _write_minimal_bundle(path: Path, *, schema_version: str = SCHEMA_VERSION) -> None:
    """Un bundle con todas las tablas del esquema y una fila cada una."""
    path.mkdir(parents=True, exist_ok=True)
    for index, (name, spec) in enumerate(TABLES.items()):
        pd.DataFrame([{column: index for column in spec.columns}]).to_parquet(path / f"{name}.parquet", index=False)
    (path / "manifest.json").write_text(json.dumps({"schema_version": schema_version, "release_id": "test"}), encoding="utf-8")


def test_a_complete_bundle_has_no_errors(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path)

    assert validate_bundle(tmp_path) == []


def test_a_missing_table_is_reported_by_name(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path)
    (tmp_path / "standings.parquet").unlink()

    errors = validate_bundle(tmp_path)

    assert any("standings" in error and "falta" in error for error in errors)


def test_a_missing_column_is_reported_with_table_and_column(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path)
    matches = pd.read_parquet(tmp_path / "matches.parquet").drop(columns=["estadio"])
    matches.to_parquet(tmp_path / "matches.parquet", index=False)

    errors = validate_bundle(tmp_path)

    assert any("matches" in error and "estadio" in error for error in errors)


def test_a_duplicated_key_is_reported(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path)
    matches = pd.read_parquet(tmp_path / "matches.parquet")
    pd.concat([matches, matches], ignore_index=True).to_parquet(tmp_path / "matches.parquet", index=False)

    errors = validate_bundle(tmp_path)

    assert any("matches" in error and "clave" in error for error in errors)


def test_another_major_schema_version_is_rejected(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path, schema_version="2.0.0")

    errors = validate_bundle(tmp_path)

    assert any("schema_version" in error for error in errors)


def test_a_missing_manifest_is_reported(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path)
    (tmp_path / "manifest.json").unlink()

    assert any("manifest" in error for error in validate_bundle(tmp_path))


# --- constructor del bundle, sobre entradas sintéticas ------------------------------------------------------------------

import pytest

from gronestats.web_bundle.build import build_web_bundle
from tests.fixtures.web_inputs import SEASONS, make_web_inputs


@pytest.fixture()
def built(tmp_path: Path):
    inputs = make_web_inputs(tmp_path / "inputs")
    out = tmp_path / "web"
    release = build_web_bundle(inputs.data_dir, inputs.analytics_dir, inputs.analytics_dir, out, seasons=SEASONS, images_dir=inputs.images_dir)
    return inputs, out, release


def _table(release: Path, name: str) -> pd.DataFrame:
    return pd.read_parquet(release / f"{name}.parquet")


def test_the_built_release_passes_the_schema_and_current_points_to_it(built) -> None:
    _, out, release = built

    assert validate_bundle(release) == []
    assert validate_bundle(out / "current") == []
    assert json.loads((out / "current" / "manifest.json").read_text(encoding="utf-8"))["release_id"] == release.name


def test_matches_only_keep_the_two_short_tournaments_with_a_parsed_date(built) -> None:
    _, _, release = built
    matches = _table(release, "matches")

    assert set(matches["tournament"]) == {"Apertura", "Clausura"}
    assert set(matches["season"]) == set(SEASONS)
    assert matches["date"].notna().all() and str(matches["date"].dtype).startswith("datetime64")


def test_team_level_is_completed_from_the_reference_even_if_a_season_lacks_it(built) -> None:
    _, _, release = built
    teams = _table(release, "teams").set_index("team_id")

    assert teams.loc[3, "level"] == "Promedio"  # 2025 no lo trae, 2026 sí
    assert teams.loc[4, "level"] == "Descenso"  # ninguna temporada lo trae: sale de la referencia
    assert teams["level"].notna().all()


def test_players_carry_the_photo_file_only_when_it_exists(built) -> None:
    _, _, release = built
    players = _table(release, "players").set_index("player_id")

    assert players.loc[11, "photo"] == "11.png"
    assert pd.isna(players.loc[12, "photo"])


def test_standings_are_built_per_round_and_the_last_one_matches_the_matches(built) -> None:
    inputs, _, release = built
    standings = _table(release, "standings")
    matches = _table(release, "matches")
    final = standings[(standings["season"] == 2025) & (standings["tournament"] == "Clausura") & (standings["round_number"] == 3)].set_index("team_id")
    clausura = matches[(matches["season"] == 2025) & (matches["tournament"] == "Clausura")]

    points = {team: 0 for team in (1, 2, 3, 4)}
    for row in clausura.itertuples():
        for team, scored, conceded in ((row.home_id, row.home_score, row.away_score), (row.away_id, row.away_score, row.home_score)):
            points[team] += 3 if scored > conceded else 1 if scored == conceded else 0
    assert {team: int(final.loc[team, "pts"]) for team in points} == points
    assert sorted(final["pos"]) == [1, 2, 3, 4]
    first_round = standings[(standings["season"] == 2025) & (standings["tournament"] == "Clausura") & (standings["round_number"] == 1)]
    assert first_round["pj"].max() == 1  # tras la fecha 1 nadie jugó más de un partido


def test_official_adjustments_apply_only_to_the_last_round_and_the_accumulated_table_exists(built) -> None:
    _, _, release = built
    standings = _table(release, "standings")
    apertura = standings[(standings["season"] == 2026) & (standings["tournament"] == "Apertura") & (standings["team_id"] == 4)].set_index("round_number")
    accumulated = standings[(standings["season"] == 2026) & (standings["tournament"] == "Acumulada")]

    matches = _table(release, "matches")

    def match_points(up_to_round: int) -> int:
        played = matches[(matches["season"] == 2026) & (matches["tournament"] == "Apertura") & (matches["round_number"] <= up_to_round) & matches["home_score"].notna()]
        total = 0
        for row in played.itertuples():
            if 4 not in (row.home_id, row.away_id):
                continue
            scored, conceded = (row.home_score, row.away_score) if row.home_id == 4 else (row.away_score, row.home_score)
            total += 3 if scored > conceded else 1 if scored == conceded else 0
        return total

    assert apertura.loc[2, "pts"] == match_points(2)  # la sanción de -3 no se aplica a las fechas intermedias
    assert apertura.loc[3, "pts"] == match_points(3) - 3  # sí a la última
    assert len(accumulated) == 4 and (accumulated["round_number"] == 0).all()


def test_shots_carry_the_xg_and_the_lineups_keep_both_flags(built) -> None:
    _, _, release = built
    shots = _table(release, "shot_events")
    lineups = _table(release, "lineups")

    assert shots["xg"].notna().all() and (shots["xg"] > 0).all()
    assert {"minute", "x", "y", "is_goal"} <= set(shots.columns)
    assert {"consistent", "defenders_ok"} <= set(lineups.columns)
    assert (~lineups["defenders_ok"]).sum() == 1


def test_coverage_counts_expected_matches_without_annulled_or_postponed_ones(built) -> None:
    inputs, _, release = built
    coverage = _table(release, "data_coverage").set_index(["season", "kind"])

    assert coverage.loc[(2025, "detail"), "expected"] == len(inputs.played[2025])
    assert coverage.loc[(2025, "detail"), "missing"] == 0
    assert coverage.loc[(2025, "momentum"), "present"] < coverage.loc[(2025, "momentum"), "expected"]
    assert (coverage["expected"] - coverage["present"] == coverage["missing"]).all()


def test_coverage_classifies_every_gap_with_the_scrape_ledger(built) -> None:
    _, _, release = built
    coverage = _table(release, "data_coverage").set_index(["season", "kind"])
    momentum = coverage.loc[(2025, "momentum")]

    # de los 5 momentum que faltan: uno dio 404, uno error, uno bloqueo y dos nunca se pidieron
    assert (momentum["missing_from_source"], momentum["failed"], momentum["blocked"], momentum["pending"]) == (1, 1, 1, 2)
    assert momentum["missing"] == 5
    states = coverage["missing_from_source"] + coverage["pending"] + coverage["failed"] + coverage["blocked"]
    assert (states == coverage["missing"]).all()  # cada hueco cae en un solo estado
    assert coverage.loc[(2026, "heatmaps"), "pending"] == coverage.loc[(2026, "heatmaps"), "missing"]  # sin registro: nunca se pidió


def test_team_cards_come_from_the_all_period_team_stats_and_omitted_reds_are_zero(built) -> None:
    inputs, _, release = built
    cards = _table(release, "team_cards")
    first = inputs.played[2025][0]
    second = inputs.played[2025][1]
    first_rows = cards[cards["match_id"] == first].set_index("team_id")

    assert first_rows.loc[1, "yellow"] == 2 and first_rows.loc[2, "yellow"] == 1  # el periodo 1ST no se suma
    assert first_rows.loc[1, "red"] == 1 and first_rows.loc[2, "red"] == 0
    assert cards[cards["match_id"] == second]["red"].tolist() == [0, 0]  # la roja se omite cuando no la hay
    assert len(cards[cards["season"] == 2025]) == 6  # 3 partidos con estadísticas de equipo; los demás no tienen fila (no se inventan ceros)


def test_manifest_lists_the_schema_version_tables_and_models(built) -> None:
    _, out, release = built
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["tables"]["matches"] == len(_table(release, "matches"))
    assert {"xg", "elo"} <= set(manifest["models"])
    assert manifest["data_as_of"] and manifest["built_at"]
    assert _table(release, "model_runs")["model"].tolist().count("xg") == 1


def test_a_second_build_keeps_the_release_log_and_replaces_current(tmp_path: Path) -> None:
    inputs = make_web_inputs(tmp_path / "inputs")
    out = tmp_path / "web"
    first = build_web_bundle(inputs.data_dir, inputs.analytics_dir, inputs.analytics_dir, out, seasons=SEASONS, images_dir=inputs.images_dir, release_id="20260101_000001")
    second = build_web_bundle(inputs.data_dir, inputs.analytics_dir, inputs.analytics_dir, out, seasons=SEASONS, images_dir=inputs.images_dir, release_id="20260101_000002")

    log = pd.read_parquet(out / "current" / "release_log.parquet")
    assert log["release_id"].tolist() == [first.name, second.name]
    assert json.loads((out / "current" / "manifest.json").read_text(encoding="utf-8"))["release_id"] == second.name


def test_stats_that_sofascore_omits_for_players_who_played_become_zero_but_cards_stay_missing(built) -> None:
    _, _, release = built
    player_match = _table(release, "player_match")
    played = player_match[player_match["minutesplayed"] > 0]

    assert played[["goals", "assists", "saves"]].notna().all().all()  # un nulo de quien jugó es un cero omitido
    assert player_match["yellowcards"].isna().all() and player_match["redcards"].isna().all()  # las tarjetas no se inventan
