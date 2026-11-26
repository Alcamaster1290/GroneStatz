from __future__ import annotations

from pathlib import Path

import pandas as pd

from gronestats.analysis.standings import load_adjustments, season_tables, tournament_table


def _matches(rows: list[tuple]) -> pd.DataFrame:
    """(match_id, torneo, local, visita, goles_local, goles_visita, status)"""
    return pd.DataFrame(
        [
            {"match_id": match_id, "season": 2025, "tour": tour, "home_id": home, "away_id": away, "home_score": hs, "away_score": as_, "status": status}
            for match_id, tour, home, away, hs, as_, status in rows
        ]
    )


def _adjustments(*rows: dict) -> pd.DataFrame:
    columns = ["season", "tournament", "team_id", "team", "pj", "pg", "pe", "pp", "gf", "gc", "points", "motivo", "fuente"]
    return pd.DataFrame([{"pj": 0, "pg": 0, "pe": 0, "pp": 0, "gf": 0, "gc": 0, "points": 0, "team": "", "motivo": "", "fuente": "", **row} for row in rows], columns=columns)


def test_tournament_table_counts_points_goals_and_orders_by_points_then_goal_difference() -> None:
    matches = _matches(
        [
            (1, "Apertura", 1, 2, 2, 0, pd.NA),
            (2, "Apertura", 3, 1, 1, 1, "finished"),
            (3, "Apertura", 2, 3, 0, 0, pd.NA),
        ]
    )

    table = tournament_table(matches[matches["tour"] == "Apertura"])

    assert table["team_id"].tolist() == [1, 3, 2]  # el 1 con 4 puntos, el 3 con 2 y el 2 con 1
    first = table.iloc[0]
    assert (first["pj"], first["pg"], first["pe"], first["pp"], first["gf"], first["gc"], first["dg"], first["pts"]) == (2, 1, 1, 0, 3, 1, 2, 4)
    assert table["pos"].tolist() == [1, 2, 3]


def test_annulled_matches_do_not_count_and_awarded_ones_count_with_the_official_score() -> None:
    matches = _matches(
        [
            (1, "Clausura", 1, 2, 3, 0, "annulled"),  # se jugó, pero no cuenta en ninguna tabla
            (2, "Clausura", 1, 3, 3, 0, "awarded"),  # el marcador es el oficial (el pipeline ya lo puso)
            (3, "Clausura", 2, 3, None, None, "postponed"),  # sin marcador: no se juega
        ]
    )

    table = tournament_table(matches).set_index("team_id")

    assert table.loc[1, "pj"] == 1 and table.loc[1, "pts"] == 3 and table.loc[1, "gf"] == 3
    assert 2 not in table.index  # solo jugó el partido anulado y el aplazado
    assert table.loc[3, "pp"] == 1


def test_adjustments_move_points_without_touching_goals_and_can_add_matches_without_goals() -> None:
    matches = _matches([(1, "Clausura", 1, 2, 1, 0, pd.NA), (2, "Clausura", 2, 3, 2, 1, pd.NA)])  # el 1 gana al 2 y el 2 gana al 3
    adjustments = _adjustments(
        {"season": 2025, "tournament": "Clausura", "team_id": 2, "points": -2},  # deuda
        {"season": 2025, "tournament": "Clausura", "team_id": 3, "points": 3, "pj": 1, "pg": 1},  # adjudicado sin goles
        {"season": 2024, "tournament": "Clausura", "team_id": 1, "points": -9},  # otra temporada: no aplica
    )

    table = tournament_table(matches, adjustments, season=2025, tournament="Clausura").set_index("team_id")

    assert table.loc[2, "pts"] == 1  # perdió con el 1 y ganó al 3 (3 puntos), menos 2 de sanción
    assert (table.loc[3, "pj"], table.loc[3, "pg"], table.loc[3, "pts"], table.loc[3, "gf"]) == (2, 1, 3, 1)  # +1 partido y +3 puntos, los goles no se mueven
    assert table.loc[1, "pts"] == 3
    assert table.sort_values("pos").index.tolist() == [1, 3, 2]  # el 1 y el 3 con 3 puntos (mejor diferencia el 1) y el 2 con 1


def test_season_tables_builds_the_accumulated_table_from_both_tournaments_plus_its_own_adjustments() -> None:
    matches = _matches([(1, "Apertura", 1, 2, 1, 0, pd.NA), (2, "Clausura", 2, 1, 0, 0, pd.NA), (3, "Clausura", 1, 2, 3, 0, pd.NA)])
    adjustments = _adjustments(
        {"season": 2025, "tournament": "Apertura", "team_id": 2, "points": -1},
        {"season": 2025, "tournament": "Acumulada", "team_id": 1, "points": -2},
    )

    tables = season_tables(matches, 2025, adjustments)

    assert set(tables) == {"Apertura", "Clausura", "Acumulada"}
    accumulated = tables["Acumulada"].set_index("team_id")
    assert accumulated.loc[1, "pj"] == 3 and accumulated.loc[1, "gf"] == 4
    assert accumulated.loc[1, "pts"] == 3 + 1 + 3 - 2  # gana dos y empata uno, menos la sanción de la acumulada
    assert accumulated.loc[2, "pts"] == 1 - 1  # empató en el Clausura y perdió el Apertura, con -1 en el Apertura
    assert tables["Apertura"].set_index("team_id").loc[2, "pts"] == -1


def test_load_adjustments_tolerates_a_missing_file_and_reads_the_columns(tmp_path: Path) -> None:
    assert load_adjustments(tmp_path / "no_existe.csv").empty
    path = tmp_path / "ajustes_tabla.csv"
    path.write_text("season,tournament,team_id,team,pj,pg,pe,pp,gf,gc,points,motivo,fuente\n2026,Apertura,5,UTC,0,0,0,0,0,0,-5,deudas,wiki\n", encoding="utf-8")

    loaded = load_adjustments(path)

    assert loaded.iloc[0][["season", "team_id", "points"]].tolist() == [2026, 5, -5]
