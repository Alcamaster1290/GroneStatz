"""Contrato del bundle de servicio: tablas, columnas y claves.

El constructor (``build``) lo escribe, ``validate`` lo comprueba y la API lo lee. Un cambio de versión mayor rompe a la API:
ella rechaza un release con otra versión mayor y sigue sirviendo el anterior.

Coordenadas (verificadas con el código de Streamlit, ver ``docs/recursos-dashboard/coordenadas-y-orientacion.md``):
- ``shot_events.x``: distancia a la línea de fondo del arco que se ataca (0 = línea de gol), igual para local y visita;
  ``y`` va de 0 a 100, centrado en 50.
- ``heatmap_points.x``: dirección de ataque (0 = arco propio, 100 = arco rival).
"""

from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION = "1.0.0"
TOURNAMENTS = ("Apertura", "Clausura")  # los torneos cortos; ``standings`` agrega "Acumulada"


@dataclass(frozen=True)
class TableSpec:
    columns: tuple[str, ...]
    key: tuple[str, ...] = ()  # vacío = sin clave única


TABLES: dict[str, TableSpec] = {
    "matches": TableSpec(
        ("season", "tournament", "round_number", "match_id", "status", "home_id", "away_id", "home_score", "away_score", "date", "estadio", "ciudad", "arbitro"),
        ("match_id",),
    ),
    "teams": TableSpec(("team_id", "name", "full_name", "color", "level", "stadium", "department", "region"), ("team_id",)),
    "players": TableSpec(("player_id", "name", "short_name", "position", "team_id", "photo"), ("player_id",)),
    "player_match": TableSpec(
        ("season", "match_id", "player_id", "team_id", "position", "minutesplayed", "goals", "assists", "yellowcards", "redcards", "saves", "rating"),
        ("season", "match_id", "player_id"),
    ),
    "shot_events": TableSpec(
        ("season", "match_id", "shot_id", "player_id", "team_id", "is_home", "shot_type", "situation", "body_part", "minute", "x", "y", "is_goal", "xg"),
        ("season", "match_id", "shot_id"),
    ),
    "heatmap_points": TableSpec(("season", "match_id", "player_id", "team_id", "x", "y")),
    "lineups": TableSpec(("season", "match_id", "side", "team_id", "formation", "expected", "counted", "consistent", "defenders_ok"), ("season", "match_id", "side")),
    "match_importance": TableSpec(
        ("season", "tournament", "match_id", "round_number", "team_id", "matches_before", "points_before", "matches_remaining", "threshold_used", "points_needed", "lives", "band", "band_name"),
        ("season", "match_id", "team_id"),
    ),
    "title_probability": TableSpec(("season", "tournament", "match_id", "team_id", "k", "p_title", "points", "rating"), ("season", "tournament", "team_id", "k")),
    "standings": TableSpec(
        ("season", "tournament", "round_number", "team_id", "pos", "pj", "pg", "pe", "pp", "gf", "gc", "dg", "pts"),
        ("season", "tournament", "round_number", "team_id"),
    ),
    "venues": TableSpec(("estadio", "ciudad", "altitud_msnm", "precision", "fuente"), ("estadio", "ciudad")),
    "model_runs": TableSpec(("model", "version", "trained_on", "params", "metrics"), ("model", "version")),
    "data_coverage": TableSpec(("season", "kind", "expected", "present", "missing"), ("season", "kind")),
    "known_gaps": TableSpec(("season", "kind", "scope", "reason", "source")),
    "release_log": TableSpec(("release_id", "built_at", "matches", "data_as_of"), ("release_id",)),
}


def major(version: str) -> int:
    return int(str(version).split(".")[0])
