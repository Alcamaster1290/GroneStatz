"""Resultados que la federacion cambio despues de jugarse el partido: adjudicados y anulados.

SofaScore guarda lo que paso en la cancha. La tabla oficial puede diferir: un partido suspendido que se adjudica 3-0, o los
resultados de un club descalificado que se anulan. ``resultados_oficiales.csv`` (junto a los maestros de la liga) declara cada
caso con su motivo y fuente; el pipeline lo aplica al maestro limpio de la corrida (nunca a la fuente) y deja el resultado en
``matches.status``:

- ``awarded``: la federacion fijo el marcador (``home_score`` y ``away_score`` del csv lo reemplazan).
- ``annulled``: se jugo, pero no cuenta en ninguna tabla. El marcador real se conserva.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

OFFICIAL_RESULTS_FILE = "resultados_oficiales.csv"
VALID_STATUSES = {"awarded", "annulled"}
COLUMNS = ["season", "match_id", "status", "home_score", "away_score", "motivo", "fuente"]


def load_official_results(path: Path, season: int) -> pd.DataFrame:
    """Las filas de una temporada; vacio si el archivo no existe."""
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    frame = pd.read_csv(path, encoding="utf-8-sig")
    return frame[frame["season"] == season].reset_index(drop=True)


def apply_official_results(master: pd.DataFrame, overrides: pd.DataFrame) -> tuple[pd.DataFrame, list[int]]:
    """Devuelve (maestro con los resultados oficiales, ids aplicados). Idempotente; falla si un id no esta en el maestro."""
    result = master.copy()
    ids = pd.to_numeric(result["match_id"], errors="coerce")
    if "status" not in result.columns:
        result["status"] = pd.NA
    result["status"] = result["status"].astype("object")
    applied: list[int] = []
    for row in overrides.itertuples():
        match_id = int(row.match_id)
        if row.status not in VALID_STATUSES:
            raise ValueError(f"status {row.status!r} no valido para el partido {match_id}: use {sorted(VALID_STATUSES)}")
        index = result.index[ids == match_id]
        if len(index) != 1:
            raise ValueError(f"el partido {match_id} de resultados_oficiales.csv no esta (una vez) en el maestro: {len(index)} coincidencias")
        if row.status == "awarded":
            if pd.isna(row.home_score) or pd.isna(row.away_score):
                raise ValueError(f"el resultado adjudicado del partido {match_id} necesita marcador (home_score y away_score)")
            result.loc[index, "home_score"] = row.home_score
            result.loc[index, "away_score"] = row.away_score
        result.loc[index, "status"] = row.status
        applied.append(match_id)
    return result, applied
