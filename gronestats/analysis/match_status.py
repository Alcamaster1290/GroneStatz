"""Estado de un partido en el bundle (`matches.status`).

Viene de SofaScore (``finished``, ``postponed``, ``canceled``) o de ``resultados_oficiales.csv`` (``awarded``, ``annulled``).
Sin estado = se jugo con normalidad (2024-2026 no traen estado).
"""

from __future__ import annotations

import pandas as pd

# Un marcador con estos estados es un resultado administrativo (3-0 sin partido jugado): suma puntos en la tabla,
# pero no hay tiros, estadisticas ni ratings que sacar de el.
ADMINISTRATIVE_STATUSES = {"postponed", "canceled"}
AWARDED_STATUS = "awarded"  # se jugo (o se empezo), pero la federacion fijo otro marcador
ANNULLED_STATUS = "annulled"  # se jugo, pero no cuenta en ninguna tabla


def _lower(status: pd.Series) -> pd.Series:
    return status.astype("string").fillna("").str.lower()


def is_administrative(status: pd.Series) -> pd.Series:
    """No se jugo: el marcador es una adjudicacion. Sin tiros ni estadisticas de partido."""
    return _lower(status).isin(ADMINISTRATIVE_STATUSES)


def is_official_award(status: pd.Series) -> pd.Series:
    """El marcador no es lo que paso en la cancha (no se jugo o la federacion lo cambio): no debe mover ratings."""
    return _lower(status).isin(ADMINISTRATIVE_STATUSES | {AWARDED_STATUS})


def is_annulled(status: pd.Series) -> pd.Series:
    return _lower(status) == ANNULLED_STATUS
