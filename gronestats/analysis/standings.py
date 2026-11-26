"""Tablas de posiciones oficiales: Apertura, Clausura y acumulada, con lo que la federacion cambia fuera de la cancha.

Se construyen desde ``matches`` del bundle (no cuentan los partidos ``annulled`` ni los que no tienen marcador) y se les aplican
los ajustes de ``ajustes_tabla.csv``: sanciones de puntos por deudas, puntos de otros torneos y los partidos que la tabla oficial
cuenta como puntos sin goles. La acumulada suma los dos torneos (con sus ajustes) mas los ajustes de la propia acumulada.

Orden: puntos, diferencia de gol, goles a favor y, solo para que sea determinista, el id del equipo.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ADJUSTMENTS_FILE = "ajustes_tabla.csv"
TOURNAMENTS = ("Apertura", "Clausura")
COUNTERS = ["pj", "pg", "pe", "pp", "gf", "gc"]
ADJUSTMENT_COLUMNS = ["season", "tournament", "team_id", "team", *COUNTERS, "points", "motivo", "fuente"]


def load_adjustments(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=ADJUSTMENT_COLUMNS)
    return pd.read_csv(path, encoding="utf-8-sig")


def _from_matches(matches: pd.DataFrame) -> pd.DataFrame:
    played = matches[matches["home_score"].notna() & matches["away_score"].notna()]
    if "status" in played.columns:
        played = played[played["status"].astype("string").fillna("").str.lower() != "annulled"]  # sin estado = se jugó
    rows = []
    for row in played.itertuples():
        for team, goals_for, goals_against in ((row.home_id, row.home_score, row.away_score), (row.away_id, row.away_score, row.home_score)):
            rows.append(
                {"team_id": int(team), "pj": 1, "pg": int(goals_for > goals_against), "pe": int(goals_for == goals_against), "pp": int(goals_for < goals_against), "gf": int(goals_for), "gc": int(goals_against)}
            )
    if not rows:
        return pd.DataFrame(columns=["team_id", *COUNTERS, "pts"]).set_index("team_id")
    table = pd.DataFrame(rows).groupby("team_id")[COUNTERS].sum()
    table["pts"] = 3 * table["pg"] + table["pe"]
    return table


def _apply(table: pd.DataFrame, adjustments: pd.DataFrame) -> pd.DataFrame:
    for row in adjustments.itertuples():
        team = int(row.team_id)
        if team not in table.index:
            table.loc[team] = 0
        for counter in COUNTERS:
            table.loc[team, counter] += int(getattr(row, counter))
        table.loc[team, "pts"] += int(row.points)
    return table


def _finish(table: pd.DataFrame) -> pd.DataFrame:
    table = table.astype(int)
    table["dg"] = table["gf"] - table["gc"]
    ordered = table.reset_index().sort_values(["pts", "dg", "gf", "team_id"], ascending=[False, False, False, True]).reset_index(drop=True)
    ordered.insert(0, "pos", range(1, len(ordered) + 1))
    return ordered[["pos", "team_id", "pj", "pg", "pe", "pp", "gf", "gc", "dg", "pts"]]


def _scope(adjustments: pd.DataFrame | None, season: int | None, tournament: str | None) -> pd.DataFrame:
    if adjustments is None or adjustments.empty or season is None or tournament is None:
        return pd.DataFrame(columns=ADJUSTMENT_COLUMNS)
    return adjustments[(adjustments["season"] == season) & (adjustments["tournament"] == tournament)]


def _raw_table(matches: pd.DataFrame, adjustments: pd.DataFrame | None, season: int | None, tournament: str | None) -> pd.DataFrame:
    return _apply(_from_matches(matches), _scope(adjustments, season, tournament))


def tournament_table(matches: pd.DataFrame, adjustments: pd.DataFrame | None = None, *, season: int | None = None, tournament: str | None = None) -> pd.DataFrame:
    """Tabla de un torneo: ``matches`` ya filtrado a ese torneo; ``season`` y ``tournament`` eligen sus ajustes."""
    return _finish(_raw_table(matches, adjustments, season, tournament))


def season_tables(matches: pd.DataFrame, season: int, adjustments: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Apertura, Clausura y Acumulada de una temporada."""
    raw = {tour: _raw_table(matches[matches["tour"] == tour], adjustments, season, tour) for tour in TOURNAMENTS}
    accumulated = raw["Apertura"].add(raw["Clausura"], fill_value=0)
    accumulated = _apply(accumulated, _scope(adjustments, season, "Acumulada"))
    return {**{tour: _finish(table) for tour, table in raw.items()}, "Acumulada": _finish(accumulated)}
