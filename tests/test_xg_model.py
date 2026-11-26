from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gronestats.analysis.xg_model import (
    auc,
    fit_model,
    leave_one_season_out,
    load_shots,
    log_loss,
    player_tables,
    shot_geometry,
)


def _synthetic_shots(seasons=(2024, 2025, 2026), per_season=700, seed=7) -> pd.DataFrame:
    """Tiros con una verdad conocida: la probabilidad de gol cae con la distancia y sube con la cabeza... al revés."""
    rng = np.random.default_rng(seed)
    rows = []
    for season in seasons:
        x = rng.uniform(3, 45, per_season)
        y = rng.uniform(20, 80, per_season)
        head = rng.random(per_season) < 0.2
        dist = np.hypot(x * 1.05, (y - 50) * 0.68)
        p = np.clip(0.45 * np.exp(-dist / 9) * np.where(head, 0.6, 1.0), 0.005, 0.9)
        rows.append(
            pd.DataFrame(
                {
                    "season": season,
                    "match_id": rng.integers(1, 40, per_season) + season * 1000,
                    "shot_id": np.arange(per_season),
                    "x": x,
                    "y": y,
                    "body_part": np.where(head, "head", "right-foot"),
                    "situation": "regular",
                    "shot_type": np.where(rng.random(per_season) < p, "goal", "miss"),
                    "goal_type": None,
                    "player_id": rng.integers(1, 30, per_season),
                    "name": "Jugador",
                    "team_name": "Equipo",
                    "is_home": rng.random(per_season) < 0.5,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def test_shot_geometry_matches_the_pitch_dimensions() -> None:
    # Penal: x = 11,5 (por 1,05 m) frente al arco; el ángulo depende de los postes a 3,94 m del centro.
    distance, angle = shot_geometry(pd.Series([11.5, 11.5]), pd.Series([50.0, 70.0]))

    assert distance[0] == pytest.approx(11.5 * 1.05)
    assert distance[1] == pytest.approx(np.hypot(11.5 * 1.05, 20 * 0.68))
    assert angle[0] > angle[1] > 0  # de frente el arco se ve más ancho que desde un lado
    near, _ = shot_geometry(pd.Series([3.0]), pd.Series([50.0]))
    assert near[0] < distance[0]


def test_model_gives_more_xg_to_closer_shots_and_less_to_headers() -> None:
    shots = _synthetic_shots()
    model = fit_model(shots)
    probe = pd.DataFrame(
        {
            "x": [6.0, 25.0, 6.0],
            "y": [50.0, 50.0, 50.0],
            "body_part": ["right-foot", "right-foot", "head"],
            "situation": ["regular"] * 3,
            "shot_type": ["miss"] * 3,
            "goal_type": [None] * 3,
        }
    )

    xg, source = model.predict(probe)

    assert xg.iloc[0] > xg.iloc[1] * 3  # cerca vale mucho más que lejos
    assert xg.iloc[2] < xg.iloc[0]  # con la verdad sintética, el cabezazo cuesta
    assert (source == "modelo").all()
    assert xg.between(0, 1).all()


def test_penalties_use_the_historical_rate_own_goals_zero_and_missing_coordinates_the_situation_mean() -> None:
    shots = _synthetic_shots(seasons=(2024, 2025), per_season=400)
    penalties = pd.DataFrame(
        {
            "season": 2024,
            "x": 11.5,
            "y": 50.0,
            "body_part": "right-foot",
            "situation": "penalty",
            "shot_type": ["goal"] * 3 + ["miss"],
            "goal_type": None,
        }
    )
    shots = pd.concat([shots, penalties], ignore_index=True)
    model = fit_model(shots)
    probe = pd.DataFrame(
        {
            "x": [11.5, 20.0, np.nan, 12.0],
            "y": [50.0, 50.0, np.nan, 50.0],
            "body_part": ["right-foot"] * 4,
            "situation": ["penalty", "regular", "regular", "shootout"],
            "shot_type": ["miss", "goal", "miss", "goal"],
            "goal_type": [None, "own", None, None],
        }
    )

    xg, source = model.predict(probe)

    assert source.tolist() == ["penal (constante)", "autogol (0)", "sin coordenadas (media por situación)", "tanda (excluida)"]
    assert xg.iloc[0] == pytest.approx(0.75)  # 3 de 4 penales convertidos
    assert xg.iloc[1] == 0.0
    assert 0 < xg.iloc[2] < 0.2
    assert xg.iloc[3] == 0.0


def test_leave_one_season_out_never_sees_the_season_it_predicts() -> None:
    shots = _synthetic_shots()
    xg_before, _, _ = leave_one_season_out(shots)

    scrambled = shots.copy()
    mask = scrambled["season"] == 2026
    scrambled.loc[mask, "shot_type"] = np.where(np.arange(mask.sum()) % 2 == 0, "goal", "miss")  # resultados de 2026 inventados
    xg_after, _, _ = leave_one_season_out(scrambled)

    # El xG de 2026 sale de 2024 y 2025: cambiar lo que pasó en 2026 no lo mueve.
    assert xg_after[mask].to_numpy() == pytest.approx(xg_before[mask].to_numpy())
    # En cambio el de 2025 sí cambia, porque ese modelo sí entrenó con 2026.
    assert not np.allclose(xg_after[shots["season"] == 2025], xg_before[shots["season"] == 2025])


def test_leave_one_season_out_reports_honest_metrics() -> None:
    shots = _synthetic_shots()

    xg, source, metrics = leave_one_season_out(shots)

    assert metrics.index.tolist() == [2024, 2025, 2026]
    assert (metrics["log_loss_modelo"] < metrics["log_loss_constante"]).all()
    assert (metrics["auc"] > 0.7).all()
    assert metrics["tiros_modelo"].sum() == len(shots)
    assert source.eq("modelo").all()
    # Calibrado: el xG total queda cerca de los goles reales de cada temporada.
    assert (metrics["xG_total"] / metrics["goles"]).between(0.8, 1.25).all()


def test_leave_one_season_out_needs_at_least_two_seasons() -> None:
    with pytest.raises(ValueError, match="dos temporadas"):
        leave_one_season_out(_synthetic_shots(seasons=(2026,)))


def test_log_loss_and_auc_known_values() -> None:
    y = np.array([1, 0, 1, 0])
    assert log_loss(y, np.array([0.5] * 4)) == pytest.approx(np.log(2))
    assert auc(y, np.array([0.9, 0.1, 0.8, 0.2])) == 1.0
    assert auc(y, np.array([0.1, 0.9, 0.2, 0.8])) == 0.0
    assert auc(y, np.array([0.5] * 4)) == 0.5


def test_player_tables_sum_xg_per_match_and_season_excluding_shootouts() -> None:
    shots = pd.DataFrame(
        {
            "season": [2026, 2026, 2026, 2026],
            "match_id": [1, 1, 2, 2],
            "player_id": [10, 10, 10, 11],
            "name": ["A", "A", "A", "B"],
            "team_name": ["X", "X", "X", "Y"],
            "xg": [0.1, 0.3, 0.76, 0.05],
            "is_goal": [0, 1, 1, 0],
            "is_pen": [False, False, True, False],
            "is_shootout": [False, False, False, True],
        }
    )

    per_match, per_season = player_tables(shots)

    a_match1 = per_match[(per_match["player_id"] == 10) & (per_match["match_id"] == 1)].iloc[0]
    assert (a_match1["tiros"], a_match1["xG"], a_match1["goles"]) == (2, pytest.approx(0.4), 1)
    a = per_season[per_season["player_id"] == 10].iloc[0]
    assert (a["partidos"], a["tiros"], a["goles"]) == (2, 3, 2)
    assert a["xG"] == pytest.approx(1.16) and a["xG_sin_penales"] == pytest.approx(0.4)
    assert a["goles_menos_xG"] == pytest.approx(2 - 1.16)
    assert 11 not in per_season["player_id"].tolist()  # su único tiro fue de la tanda


def test_load_shots_drops_shots_of_administrative_matches(tmp_path) -> None:
    dataset = tmp_path / "2023" / "dashboard" / "current"
    dataset.mkdir(parents=True)
    pd.DataFrame({"match_id": [1, 2, 3], "status": ["finished", "postponed", pd.NA]}).to_parquet(dataset / "matches.parquet")
    pd.DataFrame({"match_id": [1, 2, 3, 3], "shot_id": [1, 1, 1, 2], "x": [10.0] * 4, "y": [50.0] * 4}).to_parquet(dataset / "shot_events.parquet")

    shots = load_shots(tmp_path, [2023])

    assert sorted(shots["match_id"].tolist()) == [1, 3, 3]  # el 3-0 administrativo no aporta tiros
    assert shots["season"].eq(2023).all()
