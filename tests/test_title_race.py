from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest

from gronestats.analysis.title_race import (
    BAND_NAMES,
    EloParams,
    band_of,
    FLOOR_THRESHOLD,
    champion_points_by_tournament,
    importance_band,
    load_matches,
    match_importance,
    parse_match_dates,
    simulate_title_probabilities,
    tournament_of,
)


def test_band_of_reproduces_the_alianza_lima_example() -> None:
    # Apertura 2025, antes de su partido 11: 19 puntos, quedan 8 partidos (no 9: cada equipo juega 18).
    # Para llegar a 40 faltan 21; con 8 partidos hay 24 puntos posibles, sobran 3: puede perder 1.
    band, lives = band_of(needed=21, remaining=8)

    assert (BAND_NAMES[band], lives) == ("Alta", 1)


@pytest.mark.parametrize(
    ("needed", "remaining", "name", "lives"),
    [
        (0, 5, "Asegurado", None),
        (-3, 5, "Asegurado", None),
        (10, 10, "Baja", 6),
        (15, 9, "Baja", 4),
        (18, 8, "Media", 2),
        (21, 8, "Alta", 1),
        (24, 8, "Crítica", 0),
        (25, 8, "Fuera de alcance", -1),
        (30, 3, "Fuera de alcance", -7),
    ],
)
def test_band_of_covers_every_band(needed: float, remaining: int, name: str, lives: int | None) -> None:
    band, got_lives = band_of(needed=needed, remaining=remaining)

    assert BAND_NAMES[band] == name
    assert got_lives == lives


def test_out_of_reach_means_not_reaching_even_the_lowest_champion_total() -> None:
    # Sport Huancayo, Clausura 2026, antes de su partido 15: 28 puntos y 3 partidos. Para 40 faltan 12 y hay 9: fuera.
    # Para 37 (el campeón más bajo observado) faltan 9 y hay 9: tiene que ganar los tres, es Crítica. Ganó los tres.
    band, lives, used = importance_band(points=28, remaining=3, threshold=40, floor=FLOOR_THRESHOLD)

    assert (BAND_NAMES[band], lives, used) == ("Crítica", 0, 37)


def test_out_of_reach_stays_out_of_reach_when_not_even_the_floor_is_possible() -> None:
    band, lives, used = importance_band(points=20, remaining=3, threshold=40, floor=FLOOR_THRESHOLD)  # 29 posibles

    assert (BAND_NAMES[band], used) == ("Fuera de alcance", 40)
    assert lives == -4


def test_importance_band_uses_the_reference_threshold_while_it_is_reachable() -> None:
    assert importance_band(points=19, remaining=8, threshold=40, floor=FLOOR_THRESHOLD)[0] == 3  # Alta, como el ejemplo de Alianza Lima
    assert importance_band(points=19, remaining=8, threshold=40, floor=None) == (3, 1, 40)
    assert FLOOR_THRESHOLD == 37


def test_band_of_without_matches_left_is_undefined() -> None:
    assert band_of(needed=5, remaining=0) == (None, None)


def test_tournament_of_keeps_only_apertura_and_clausura() -> None:
    assert tournament_of("Liga 1, Apertura") == "Apertura"
    assert tournament_of("Primera Division, Clausura") == "Clausura"
    assert tournament_of("Liga 1, Clausura") == "Clausura"
    assert tournament_of("Primera Division, Grand Final") is None
    assert tournament_of("Liga 1, Relegation/Promotion Playoffs") is None
    assert tournament_of(None) is None


def test_parse_match_dates_reads_the_bundle_format() -> None:
    parsed = parse_match_dates(pd.Series(["08/02/2025 19:00", "31/01/2026 15:15", None]))

    assert parsed.iloc[0] == pd.Timestamp("2025-02-08 19:00")
    assert parsed.iloc[1] == pd.Timestamp("2026-01-31 15:15")
    assert pd.isna(parsed.iloc[2])


def _tournament(rows: list[tuple]) -> pd.DataFrame:
    """(match_id, ronda, fecha, local, visita, goles_local, goles_visita)"""
    return pd.DataFrame(
        [
            {
                "season": 2025,
                "tour": "Apertura",
                "match_id": match_id,
                "round_number": round_number,
                "date": pd.Timestamp(date),
                "home_id": home,
                "away_id": away,
                "home_score": hs,
                "away_score": as_,
                "awarded": False,
            }
            for match_id, round_number, date, home, away, hs, as_ in rows
        ]
    )


def test_match_importance_counts_remaining_matches_from_each_teams_schedule_not_from_rounds() -> None:
    # Cuatro equipos, todos contra todos a una vuelta (3 partidos c/u). El equipo 4 solo juega 2 (como Binacional).
    matches = _tournament(
        [
            (1, 1, "2025-02-01", 1, 2, 2, 0),
            (2, 1, "2025-02-01", 3, 4, 1, 1),
            (3, 2, "2025-02-08", 1, 3, 0, 0),
            (4, 2, "2025-02-08", 2, 4, 3, 0),
            (5, 3, "2025-02-15", 1, 4, 1, 0),
            (6, 3, "2025-02-15", 2, 3, 0, 1),
        ]
    )
    matches = matches[matches["match_id"] != 4]  # el equipo 4 no jugó contra el 2: tiene 2 partidos programados

    rows = match_importance(matches, threshold=6)

    team1 = rows[rows["team_id"] == 1].sort_values("date").reset_index(drop=True)
    assert team1["matches_before"].tolist() == [0, 1, 2]
    assert team1["points_before"].tolist() == [0, 3, 4]
    assert team1["matches_remaining"].tolist() == [3, 2, 1]
    team4 = rows[rows["team_id"] == 4].sort_values("date").reset_index(drop=True)
    assert team4["matches_remaining"].tolist() == [2, 1]  # equipos - 1 habría dicho 3
    first = team1.iloc[0]
    assert (first["points_needed"], first["lives"], BAND_NAMES[first["band"]]) == (6, 1, "Alta")  # 9 posibles, sobran 3
    assert first["round_number"] == 1 and first["match_id"] == 1


def test_match_importance_follows_calendar_dates_when_a_match_is_played_late() -> None:
    # El partido de la ronda 1 entre 1 y 3 se jugó después de la ronda 2: para el equipo 1 es su segundo partido.
    matches = _tournament(
        [
            (1, 1, "2025-02-01", 1, 2, 1, 0),
            (2, 1, "2025-02-20", 1, 3, 1, 0),
            (3, 2, "2025-02-08", 1, 4, 0, 1),
            (4, 2, "2025-02-08", 2, 3, 0, 0),
            (5, 3, "2025-02-15", 2, 4, 1, 1),
            (6, 3, "2025-02-15", 3, 4, 2, 0),
        ]
    )

    rows = match_importance(matches, threshold=6)

    team1 = rows[rows["team_id"] == 1].sort_values("date")
    assert team1["match_id"].tolist() == [1, 3, 2]
    assert team1["matches_before"].tolist() == [0, 1, 2]
    assert team1["points_before"].tolist() == [0, 3, 3]


def test_champion_points_by_tournament_uses_points_then_goal_difference() -> None:
    matches = _tournament(
        [
            (1, 1, "2025-02-01", 1, 2, 1, 0),
            (2, 1, "2025-02-01", 3, 4, 0, 0),
            (3, 2, "2025-02-08", 3, 2, 3, 0),
            (4, 2, "2025-02-08", 1, 4, 0, 1),
        ]
    )

    champions = champion_points_by_tournament(matches)

    # Terminan con 4 puntos el equipo 3 (empate y 3-0) y el 4 (empate y 1-0); el 3 gana por diferencia de gol (+3 contra +1).
    assert champions[(2025, "Apertura")] == (3, 4)


def test_match_importance_rescues_a_team_from_out_of_reach_when_it_can_still_reach_the_floor() -> None:
    # Un equipo con 3 partidos programados: 9 puntos posibles. Con umbral 12 no llega; con piso 7 sí, ganando los tres sobran 2.
    matches = _tournament(
        [
            (1, 1, "2025-02-01", 1, 2, 3, 0),
            (2, 2, "2025-02-08", 1, 3, 3, 0),
            (3, 3, "2025-02-15", 1, 4, 3, 0),
        ]
    )

    strict = match_importance(matches, threshold=12, floor_threshold=None)
    with_floor = match_importance(matches, threshold=12, floor_threshold=7)

    first_strict = strict[strict["team_id"] == 1].sort_values("date").iloc[0]
    first_floor = with_floor[with_floor["team_id"] == 1].sort_values("date").iloc[0]
    assert BAND_NAMES[first_strict["band"]] == "Fuera de alcance" and first_strict["threshold_used"] == 12
    assert BAND_NAMES[first_floor["band"]] == "Crítica" and first_floor["threshold_used"] == 7
    assert first_floor["points_needed"] == 7 and first_floor["lives"] == 0


def test_load_matches_flags_awards_and_drops_annulled_matches_using_the_bundle_status(tmp_path: Path) -> None:
    dataset = tmp_path / "2023" / "dashboard" / "current"
    dataset.mkdir(parents=True)
    pd.DataFrame(
        {
            "match_id": [1, 2, 3, 4, 5],
            "tournament": ["Liga 1, Apertura"] * 5,
            "round_number": [3, 3, 3, 3, 3],
            # postponed con marcador = 3-0 administrativo; awarded = marcador fijado por la federación; annulled = no cuenta; NA = se jugó
            "status": ["finished", "postponed", pd.NA, "awarded", "annulled"],
            "home_id": [10, 11, 12, 13, 14],
            "away_id": [20, 21, 22, 23, 24],
            "home_score": [1, 3, 0, 0, 2],
            "away_score": [0, 0, 0, 3, 0],
            "fecha": ["05/02/2023 15:00", "04/02/2023 20:30", "06/02/2023 15:00", "07/02/2023 15:00", "08/02/2023 15:00"],
        }
    ).to_parquet(dataset / "matches.parquet")

    loaded = load_matches(tmp_path, [2023])

    assert loaded["match_id"].tolist() == [1, 2, 3, 4]  # el anulado no está: no puntúa ni ocupa lugar en el calendario
    assert loaded["awarded"].tolist() == [False, True, False, True]  # los adjudicados no mueven ratings, pero sí suman puntos
    assert loaded["tour"].tolist() == ["Apertura"] * 4


def _simulation_matches(played: list[tuple], pending: list[tuple]) -> pd.DataFrame:
    rows = []
    for index, (home, away, hs, as_) in enumerate(played + pending):
        rows.append(
            {
                "season": 2025,
                "tour": "Apertura",
                "match_id": index + 1,
                "round_number": index // 2 + 1,
                "date": pd.Timestamp("2025-02-01") + pd.Timedelta(days=index),
                "home_id": home,
                "away_id": away,
                "home_score": hs,
                "away_score": as_,
                "awarded": False,
            }
        )
    return pd.DataFrame(rows)


PARAMS = EloParams(k=20, home=100, altitude=0, regression=0.0, draw_max=0.32, initial=1500)


def test_title_probabilities_sum_to_one_and_split_evenly_between_equal_teams() -> None:
    # Cuatro equipos iguales, sin partidos jugados y con calendario simétrico (todos contra todos, ida y vuelta): cada uno tiene ~25 %.
    pairs = list(itertools.combinations([1, 2, 3, 4], 2))
    pending = [(home, away, None, None) for home, away in pairs] + [(away, home, None, None) for home, away in pairs]
    matches = _simulation_matches([], pending)

    table = simulate_title_probabilities(matches, PARAMS, n_sim=4000, sigma=0.0, seed=3)

    start = table[table["k"] == 0]
    assert start["p_title"].sum() == pytest.approx(1.0)
    assert start["p_title"].between(0.15, 0.35).all()


def test_title_probabilities_reach_one_when_a_team_cannot_be_caught() -> None:
    played = [(1, 2, 3, 0), (1, 3, 3, 0), (1, 4, 3, 0), (2, 3, 0, 0), (2, 4, 0, 0)]
    matches = _simulation_matches(played, [(3, 4, None, None)])

    table = simulate_title_probabilities(matches, PARAMS, n_sim=2000, sigma=0.0, seed=1)

    after_third = table[(table["team_id"] == 1) & (table["k"] == 3)].iloc[0]
    assert after_third["p_title"] == pytest.approx(1.0)  # 9 puntos contra un máximo de 6 posibles para cualquiera de los demás
    assert table[(table["team_id"] == 4) & (table["k"] == 2)]["p_title"].iloc[0] == pytest.approx(0.0)


def test_title_probabilities_are_reproducible_for_the_same_seed() -> None:
    played = [(1, 2, 2, 0), (3, 4, 1, 1)]
    pending = [(1, 3, None, None), (2, 4, None, None), (1, 4, None, None), (2, 3, None, None)]
    matches = _simulation_matches(played, pending)

    first = simulate_title_probabilities(matches, PARAMS, n_sim=500, sigma=60.0, seed=11)
    second = simulate_title_probabilities(matches, PARAMS, n_sim=500, sigma=60.0, seed=11)

    pd.testing.assert_frame_equal(first, second)
    assert set(first.columns) >= {"season", "tour", "match_id", "team_id", "k", "p_title"}


def test_awarded_results_count_for_points_but_not_for_ratings() -> None:
    played = [(1, 2, 3, 0), (3, 4, 1, 1)]
    matches = _simulation_matches(played, [(1, 3, None, None), (2, 4, None, None)])
    awarded = matches.copy()
    awarded.loc[awarded["match_id"] == 1, "awarded"] = True

    normal = simulate_title_probabilities(matches, PARAMS, n_sim=3000, sigma=0.0, seed=5)
    flagged = simulate_title_probabilities(awarded, PARAMS, n_sim=3000, sigma=0.0, seed=5)

    # Los 3 puntos del 3-0 administrativo siguen contando en ambos casos...
    assert flagged[(flagged["match_id"] == 1) & (flagged["team_id"] == 1)]["points"].iloc[0] == 3
    # ...pero un resultado que no se jugó no mueve el rating de nadie, así que no cambia la fuerza relativa que usa la simulación.
    assert flagged[(flagged["match_id"] == 1)]["rating"].between(1499.9, 1500.1).all()
    assert normal[(normal["match_id"] == 1) & (normal["team_id"] == 1)]["rating"].iloc[0] > 1500
