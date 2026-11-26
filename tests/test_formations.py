from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from gronestats.analysis.formations import (
    check_side,
    counted_distribution,
    expected_distribution,
    formation_table,
    summarize_checks,
)


def _starters(positions: str) -> list[dict]:
    return [{"player_id": i, "name": f"J{i}", "position": position, "shirt": i + 1, "team_id": 7} for i, position in enumerate(positions)]


@pytest.mark.parametrize(
    ("formation", "expected"),
    [
        ("4-3-3", (4, 3, 3)),
        ("4-1-4-1", (4, 5, 1)),  # los medios de todas las líneas intermedias suman
        ("4-2-3-1", (4, 5, 1)),
        ("3-4-1-2", (3, 5, 2)),
        ("5-4-1", (5, 4, 1)),
        ("4-4-2", (4, 4, 2)),
    ],
)
def test_expected_distribution_adds_the_midfield_lines(formation: str, expected: tuple[int, int, int]) -> None:
    assert expected_distribution(formation) == expected


@pytest.mark.parametrize("formation", [None, "", "4-3", "x-y-z", "4-3-3-1-1", "9-1", "4-4-4", 433])
def test_expected_distribution_rejects_what_is_not_a_formation_of_ten_outfield_players(formation) -> None:
    assert expected_distribution(formation) is None


def test_counted_distribution_reads_the_position_letters_of_the_starters() -> None:
    assert counted_distribution(_starters("GDDDDMMMFFF")) == (4, 3, 3, 1)
    assert counted_distribution(_starters("GDDDMMMMFFF")) == (3, 4, 3, 1)


def test_check_side_is_consistent_when_the_starters_match_the_declared_formation() -> None:
    result = check_side({"formation": "4-3-3", "starters": _starters("GDDDDMMMFFF")})

    assert result["consistent"] is True
    assert (result["expected"], result["counted"], result["reason"]) == ("4-3-3", "4-3-3", "")


def test_check_side_explains_a_mismatch_between_formation_and_positions() -> None:
    # Declara 4-2-3-1 (4-5-1) pero las letras de los titulares dan 4-4-2: un extremo figura como delantero.
    result = check_side({"formation": "4-2-3-1", "starters": _starters("GDDDDMMMMFF")})

    assert result["consistent"] is False
    assert (result["expected"], result["counted"]) == ("4-5-1", "4-4-2")
    assert result["diff"] == "M-1 F+1"
    assert "distribución distinta" in result["reason"]
    assert result["defenders_ok"] is True  # solo se confunden medios y delanteros: los 4 defensas sí están


def test_check_side_marks_when_even_the_number_of_defenders_is_wrong() -> None:
    result = check_side({"formation": "4-3-3", "starters": _starters("GDDDMMMMFFF")})  # declara 4 defensas y hay 3

    assert (result["consistent"], result["defenders_ok"], result["diff"]) == (False, False, "D-1 M+1")


@pytest.mark.parametrize(
    ("side", "reason"),
    [
        ({"formation": None, "starters": _starters("GDDDDMMMFFF")}, "sin formación declarada"),
        ({"formation": "4-3-3", "starters": _starters("GDDDDMMMFF")}, "no son 11 titulares"),
        ({"formation": "4-3-3", "starters": _starters("DDDDDMMMFFF")}, "sin arquero único"),
        ({"formation": "4-3", "starters": _starters("GDDDDMMMFFF")}, "formación no válida"),
    ],
)
def test_check_side_flags_incomplete_data_instead_of_guessing(side: dict, reason: str) -> None:
    result = check_side(side)

    assert result["consistent"] is False
    assert result["reason"].startswith(reason)


def _write_records(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def test_formation_table_has_one_row_per_team_and_match(tmp_path: Path) -> None:
    records = [
        {"match_id": 1, "confirmed": True, "home": {"formation": "4-3-3", "team_id": 7, "starters": _starters("GDDDDMMMFFF")}, "away": {"formation": "4-2-3-1", "team_id": 8, "starters": _starters("GDDDDMMMMFF")}},
        {"match_id": 2, "confirmed": False, "home": {"formation": None, "team_id": 9, "starters": _starters("GDDDDMMMFFF")}, "away": {"formation": "5-4-1", "team_id": 7, "starters": _starters("GDDDDDMMMMF")}},
    ]
    path = tmp_path / "lineups.jsonl"
    _write_records(path, records)

    table = formation_table(path, season=2026)

    assert len(table) == 4
    assert table.columns.tolist()[:6] == ["season", "match_id", "side", "team_id", "formation", "confirmed"]
    first = table[(table["match_id"] == 1) & (table["side"] == "home")].iloc[0]
    assert (first["season"], first["team_id"], first["formation"], bool(first["consistent"])) == (2026, 7, "4-3-3", True)
    assert table[(table["match_id"] == 1) & (table["side"] == "away")].iloc[0]["diff"] == "M-1 F+1"
    assert table[(table["match_id"] == 2) & (table["side"] == "home")].iloc[0]["reason"] == "sin formación declarada"
    assert bool(table[(table["match_id"] == 2) & (table["side"] == "away")].iloc[0]["consistent"]) is True


def test_summarize_checks_reports_the_rate_and_the_most_common_mismatches() -> None:
    table = pd.DataFrame(
        {
            "season": [2026] * 5,
            "consistent": [True, True, False, False, False],
            "defenders_ok": [True, True, True, True, False],
            "formation": ["4-3-3", "4-2-3-1", "4-2-3-1", "4-2-3-1", "3-5-2"],
            "diff": ["", "", "M-1 F+1", "M-1 F+1", "D+1 M-1"],
            "reason": ["", "", "distribución distinta", "distribución distinta", "distribución distinta"],
        }
    )

    summary = summarize_checks(table)

    assert summary["by_season"].loc[2026, "consistentes"] == 2 and summary["by_season"].loc[2026, "total"] == 5
    assert summary["by_season"].loc[2026, "defensas_ok"] == 4 and summary["by_season"].loc[2026, "tasa_defensas"] == pytest.approx(0.8)
    assert summary["top_mismatches"].iloc[0].to_dict() == {"formation": "4-2-3-1", "diff": "M-1 F+1", "partidos": 2}
    assert summary["by_formation"].loc["4-2-3-1", "partidos"] == 3
    assert summary["by_formation"].loc["4-2-3-1", "tasa"] == pytest.approx(1 / 3)
