"""Formacion declarada de cada equipo y partido, contrastada con la posicion de sus 11 titulares.

SofaScore declara la formacion (``4-2-3-1``) y, en la misma respuesta de alineaciones, da a cada jugador la posicion que ocupo en
ese partido (G, D, M o F). De la formacion se deduce cuantos defensas, medios y delanteros debe haber: el primer numero son los
defensas, el ultimo los delanteros y los intermedios suman medios (``4-2-3-1`` = D4 M5 F1). El cruce comprueba que los titulares
cumplan esa distribucion; cuando no, la formacion declarada sigue mandando y el partido queda marcado con la razon.

Uso:
    py -3.11 -m gronestats.analysis.formations --out docs/recursos-dashboard/datos-de-apoyo/formaciones
Lee ``<temporada>/raw/lineups.jsonl`` (lo escribe ``sofascore_batches lineups``).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

FORMATION_PATTERN = re.compile(r"^\d(-\d){1,4}$")
SIDES = ("home", "away")


def expected_distribution(formation: object) -> tuple[int, int, int] | None:
    """(defensas, medios, delanteros) que implica una formacion declarada; ``None`` si no es una formacion de 10 jugadores de campo."""
    if not isinstance(formation, str) or not FORMATION_PATTERN.match(formation):
        return None
    lines = [int(token) for token in formation.split("-")]
    if sum(lines) != 10 or len(lines) < 3:
        return None
    return lines[0], sum(lines[1:-1]), lines[-1]


def counted_distribution(starters: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    """(defensas, medios, delanteros, arqueros) segun la posicion de cada titular en el partido."""
    counts = Counter(str(starter.get("position")) for starter in starters)
    return counts["D"], counts["M"], counts["F"], counts["G"]


def _label(distribution: tuple[int, int, int]) -> str:
    return "-".join(str(value) for value in distribution)


def _diff(expected: tuple[int, int, int], counted: tuple[int, int, int]) -> str:
    return " ".join(f"{letter}{got - want:+d}" for letter, want, got in zip("DMF", expected, counted) if got != want)


def check_side(side: dict[str, Any]) -> dict[str, Any]:
    """Cruce de un lado: ``consistent`` es verdadero solo si hay formacion valida, 11 titulares, un arquero y la distribucion coincide."""
    formation, starters = side.get("formation"), side.get("starters") or []
    counted = counted_distribution(starters)
    base = {"formation": formation, "expected": "", "counted": _label(counted[:3]) if starters else "", "diff": "", "consistent": False, "defenders_ok": False, "reason": ""}
    if not formation:
        return {**base, "reason": "sin formación declarada"}
    expected = expected_distribution(formation)
    if expected is None:
        return {**base, "reason": f"formación no válida ({formation})"}
    base["expected"] = _label(expected)
    if len(starters) != 11:
        return {**base, "reason": f"no son 11 titulares ({len(starters)})"}
    if counted[3] != 1:
        return {**base, "reason": f"sin arquero único ({counted[3]} arqueros)"}
    defenders_ok = counted[0] == expected[0]  # el numero de defensas es lo que mas pesa: M y F se confunden entre extremos y segundas puntas
    if counted[:3] != expected:
        diff = _diff(expected, counted[:3])
        return {**base, "diff": diff, "defenders_ok": defenders_ok, "reason": f"distribución distinta: declarada D{expected[0]}-M{expected[1]}-F{expected[2]}, titulares D{counted[0]}-M{counted[1]}-F{counted[2]}"}
    return {**base, "consistent": True, "defenders_ok": True}


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def formation_table(path: Path, season: int) -> pd.DataFrame:
    """Una fila por equipo y partido con la formacion declarada, lo esperado, lo contado y el resultado del cruce."""
    rows = []
    for record in load_records(path):
        for side in SIDES:
            data = record.get(side) or {}
            rows.append({"season": season, "match_id": record["match_id"], "side": side, "team_id": data.get("team_id"), "formation": data.get("formation"), "confirmed": record.get("confirmed"), **{k: v for k, v in check_side(data).items() if k != "formation"}})
    columns = ["season", "match_id", "side", "team_id", "formation", "confirmed", "expected", "counted", "diff", "consistent", "defenders_ok", "reason"]
    return pd.DataFrame(rows, columns=columns)


def summarize_checks(table: pd.DataFrame) -> dict[str, pd.DataFrame]:
    by_season = table.groupby("season").agg(consistentes=("consistent", "sum"), defensas_ok=("defenders_ok", "sum"), total=("consistent", "size"))
    by_season["tasa"] = by_season["consistentes"] / by_season["total"]
    by_season["tasa_defensas"] = by_season["defensas_ok"] / by_season["total"]
    declared = table[table["formation"].notna()]
    by_formation = declared.groupby("formation")["consistent"].agg(partidos="size", consistentes="sum")
    by_formation["tasa"] = by_formation["consistentes"] / by_formation["partidos"]
    mismatches = table[(~table["consistent"]) & (table["diff"] != "")]
    top = mismatches.groupby(["formation", "diff"]).size().rename("partidos").reset_index().sort_values(["partidos", "formation", "diff"], ascending=[False, True, True]).reset_index(drop=True)
    return {"by_season": by_season, "by_formation": by_formation.sort_values("partidos", ascending=False), "top_mismatches": top}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Formación declarada y cruce con las posiciones de los 11 titulares.")
    parser.add_argument("--league", default="Liga 1 Peru")
    parser.add_argument("--seasons", default="2022,2023,2024,2025,2026")
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(__file__).resolve().parents[1] / "data" / args.league
    seasons = [int(token) for token in args.seasons.split(",")]
    tables = [formation_table(base_dir / str(season) / "raw" / "lineups.jsonl", season) for season in seasons]
    table = pd.concat([t for t in tables if not t.empty], ignore_index=True)
    args.out.mkdir(parents=True, exist_ok=True)
    table.to_parquet(args.out / "formaciones_equipo_partido.parquet", index=False)
    table.to_csv(args.out / "formaciones_equipo_partido.csv", index=False, encoding="utf-8-sig")
    summary = summarize_checks(table)
    for name, frame in summary.items():
        frame.to_csv(args.out / f"resumen_{name}.csv", encoding="utf-8-sig")
    print("=== cruce formación declarada contra titulares, por temporada ===")
    print(summary["by_season"].round(3).to_string())
    print("\n=== razones de los que no coinciden ===")
    print(table[~table["consistent"]].assign(razon=lambda f: f["reason"].str.split(":").str[0].str.replace(r"\s*\(.*", "", regex=True)).groupby("razon").size().sort_values(ascending=False).to_string())
    print("\n=== formaciones más usadas y su tasa de coincidencia ===")
    print(summary["by_formation"].head(12).round(3).to_string())
    print("\n=== diferencias más frecuentes (declarada contra titulares) ===")
    print(summary["top_mismatches"].head(12).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
