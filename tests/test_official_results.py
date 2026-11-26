from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from gronestats.processing.official_results import apply_official_results, load_official_results


def _master() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": [1, 2, 3],
            "home": ["Ayacucho", "Binacional", "Cusco"],
            "away": ["Comerciantes", "Cristal", "Binacional"],
            "home_score": [1, 1, 2],
            "away_score": [0, 3, 0],
            "status": [pd.NA, pd.NA, pd.NA],
        }
    )


def _overrides(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["season", "match_id", "status", "home_score", "away_score", "motivo", "fuente"])


def test_an_awarded_result_replaces_the_played_score_and_marks_the_match() -> None:
    # Ayacucho iba 1-0 cuando se suspendió el partido; la federación lo adjudicó 3-0 a Comerciantes.
    overrides = _overrides({"season": 2025, "match_id": 1, "status": "awarded", "home_score": 0, "away_score": 3, "motivo": "suspendido", "fuente": "FPF"})

    result, applied = apply_official_results(_master(), overrides)

    row = result[result["match_id"] == 1].iloc[0]
    assert (row["home_score"], row["away_score"], row["status"]) == (0, 3, "awarded")
    assert applied == [1]
    assert result[result["match_id"] == 2].iloc[0]["home_score"] == 1  # el resto queda igual


def test_an_annulled_match_keeps_its_played_score_but_is_marked() -> None:
    overrides = _overrides({"season": 2025, "match_id": 2, "status": "annulled", "home_score": None, "away_score": None, "motivo": "descalificado", "fuente": "FPF"})

    result, _ = apply_official_results(_master(), overrides)

    row = result[result["match_id"] == 2].iloc[0]
    assert (row["home_score"], row["away_score"], row["status"]) == (1, 3, "annulled")  # se jugó: el marcador real sigue ahí


def test_applying_twice_gives_the_same_master() -> None:
    overrides = _overrides(
        {"season": 2025, "match_id": 1, "status": "awarded", "home_score": 0, "away_score": 3, "motivo": "x", "fuente": "y"},
        {"season": 2025, "match_id": 3, "status": "annulled", "home_score": None, "away_score": None, "motivo": "x", "fuente": "y"},
    )

    once, _ = apply_official_results(_master(), overrides)
    twice, _ = apply_official_results(once, overrides)

    pd.testing.assert_frame_equal(once, twice)


def test_an_override_for_a_match_that_is_not_in_the_master_fails_loudly() -> None:
    overrides = _overrides({"season": 2025, "match_id": 99, "status": "annulled", "home_score": None, "away_score": None, "motivo": "x", "fuente": "y"})

    with pytest.raises(ValueError, match="99"):
        apply_official_results(_master(), overrides)  # ignorarlo en silencio dejaría una tabla distinta de la oficial sin avisar


def test_an_unknown_status_or_an_awarded_result_without_score_is_rejected() -> None:
    with pytest.raises(ValueError, match="status"):
        apply_official_results(_master(), _overrides({"season": 2025, "match_id": 1, "status": "raro", "home_score": 0, "away_score": 3, "motivo": "x", "fuente": "y"}))
    with pytest.raises(ValueError, match="marcador"):
        apply_official_results(_master(), _overrides({"season": 2025, "match_id": 1, "status": "awarded", "home_score": None, "away_score": 3, "motivo": "x", "fuente": "y"}))


def test_load_official_results_filters_by_season_and_tolerates_a_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "resultados_oficiales.csv"
    path.write_text("season,match_id,status,home_score,away_score,motivo,fuente\n2025,1,awarded,0,3,a,b\n2023,7,annulled,,,c,d\n", encoding="utf-8")

    assert load_official_results(path, 2025)["match_id"].tolist() == [1]
    assert load_official_results(path, 2026).empty
    assert load_official_results(tmp_path / "no_existe.csv", 2025).empty
