"""Una función por endpoint. Reciben el ``Release`` abierto y devuelven diccionarios listos para JSON.

Aquí solo se filtra, se une y se agrega según lo que el usuario elige; las reglas de dominio (importancia, probabilidad,
formaciones, tablas oficiales) vienen ya calculadas en el release. Un dato que falta en origen se devuelve como ``None`` con
``missing_reason``, nunca como cero.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from gronestats.api.store import Release, records

STALE_AFTER_HOURS = 48
TOURNAMENT_ORDER = ("Apertura", "Clausura", "Acumulada")
HEATMAP_BINS = 20  # cuadrícula de 5 unidades sobre la cancha de 100 × 100


class NotFound(LookupError):
    """El recurso pedido no existe en el release."""


def _py(value: Any) -> Any:
    """Escalar de pandas/numpy a Python; los nulos pasan a ``None``."""
    if value is None or (not isinstance(value, (str, bytes)) and pd.isna(value)):
        return None
    return value.item() if hasattr(value, "item") else value


def _int(value: Any) -> int | None:
    value = _py(value)
    return None if value is None else int(value)


def _iso(value: Any) -> str | None:
    value = _py(value)
    return None if value is None else pd.Timestamp(value).isoformat()


def _ref(release: Release, team_id: Any) -> dict[str, Any] | None:
    return release.team(_int(team_id))


def _default_tournament(available: list[str]) -> str | None:
    return "Clausura" if "Clausura" in available else "Apertura" if "Apertura" in available else (available[0] if available else None)


def release_info(release: Release) -> dict[str, Any]:
    manifest = release.manifest
    return {
        "release_id": release.release_id,
        "schema_version": manifest["schema_version"],
        "built_at": manifest.get("built_at"),
        "data_as_of": manifest.get("data_as_of"),
        "seasons": sorted(manifest.get("seasons", []), reverse=True),
        "models": manifest.get("models", {}),
    }


def seasons(release: Release) -> dict[str, Any]:
    table = release.q("SELECT season, tournament, MAX(round_number) AS rounds FROM standings GROUP BY 1, 2")
    result = []
    for season in sorted({int(value) for value in table["season"]}, reverse=True):
        rows = table[table["season"] == season]
        tournaments = [name for name in TOURNAMENT_ORDER if name in set(rows["tournament"])]
        result.append({"season": season, "tournaments": tournaments, "rounds": {row.tournament: int(row.rounds) for row in rows.itertuples() if row.tournament != "Acumulada"}})
    return {"release_id": release.release_id, "seasons": result}


def teams(release: Release, season: int | None) -> dict[str, Any]:
    if season is None:
        frame = release.q("SELECT team_id FROM teams ORDER BY name")
    else:
        frame = release.q("SELECT t.team_id FROM teams t WHERE t.team_id IN (SELECT home_id FROM matches WHERE season = ? UNION SELECT away_id FROM matches WHERE season = ?) ORDER BY t.name", [season, season])
    return {"release_id": release.release_id, "teams": [release.team(int(team_id)) for team_id in frame["team_id"]]}


def standings(release: Release, season: int, tournament: str | None, round_number: int | None) -> dict[str, Any]:
    available = [str(name) for name in release.q("SELECT DISTINCT tournament FROM standings WHERE season = ?", [season])["tournament"]]
    if not available:
        raise NotFound(f"no hay tabla de posiciones de {season}")
    tournament = tournament or _default_tournament(available)
    if tournament not in available:
        raise NotFound(f"{season} no tiene el torneo {tournament}")
    rounds = int(release.q("SELECT MAX(round_number) AS r FROM standings WHERE season = ? AND tournament = ?", [season, tournament])["r"].iloc[0])
    selected = 0 if tournament == "Acumulada" else (rounds if round_number is None else round_number)
    frame = release.q("SELECT pos, team_id, pj, pg, pe, pp, gf, gc, dg, pts FROM standings WHERE season = ? AND tournament = ? AND round_number = ? ORDER BY pos", [season, tournament, selected])
    if frame.empty:
        raise NotFound(f"{season} {tournament} no tiene la fecha {selected}")
    rows = [{**row, **{key: value for key, value in (release.team(row["team_id"]) or {}).items() if key != "team_id"}} for row in records(frame)]
    return {"release_id": release.release_id, "season": season, "tournament": tournament, "round_number": selected, "rounds": 0 if tournament == "Acumulada" else rounds, "rows": rows}


def team_matches(release: Release, team_id: int, season: int) -> dict[str, Any]:
    team = release.team(team_id)
    if team is None:
        raise NotFound(f"no existe el equipo {team_id}")
    matches = release.q(
        "SELECT m.match_id, m.tournament, m.round_number, m.date, m.status, m.home_id, m.away_id, m.home_score, m.away_score, m.estadio, m.ciudad, v.altitud_msnm AS altitude_m "
        "FROM matches m LEFT JOIN venues v ON v.estadio = m.estadio AND v.ciudad = m.ciudad "
        "WHERE m.season = ? AND (m.home_id = ? OR m.away_id = ?) ORDER BY m.date, m.match_id",
        [season, team_id, team_id],
    )
    if matches.empty:
        return {"release_id": release.release_id, "team": team, "season": season, "tournaments": {}, "missing_reason": "team_not_in_season"}
    own_altitudes = matches.loc[matches["home_id"] == team_id, "altitude_m"].dropna()
    base_altitude = float(own_altitudes.median()) if len(own_altitudes) else None
    lineups = {int(row.match_id): row for row in release.q("SELECT match_id, formation, defenders_ok, consistent FROM lineups WHERE season = ? AND team_id = ?", [season, team_id]).itertuples()}
    importance = {int(row["match_id"]): row for row in records(release.q("SELECT match_id, band, band_name, lives, threshold_used, matches_before, matches_remaining, points_before, points_needed FROM match_importance WHERE season = ? AND team_id = ?", [season, team_id]))}
    xg = {(int(row.match_id), int(row.team_id)): float(row.xg) for row in release.q("SELECT s.match_id, s.team_id, SUM(s.xg) AS xg FROM shot_events s JOIN matches m ON m.match_id = s.match_id WHERE m.season = ? AND (m.home_id = ? OR m.away_id = ?) GROUP BY 1, 2", [season, team_id, team_id]).itertuples()}
    cards = {
        (int(row.match_id), int(row.team_id)): (int(row.yellow), int(row.red))
        for row in release.q("SELECT c.match_id, c.team_id, c.yellow, c.red FROM team_cards c JOIN matches m ON m.match_id = c.match_id WHERE c.season = ? AND (m.home_id = ? OR m.away_id = ?)", [season, team_id, team_id]).itertuples()
    }
    after: dict[int, float] = {}
    before: dict[int, float] = {}
    for _, group in release.q("SELECT tournament, match_id, k, p_title FROM title_probability WHERE season = ? AND team_id = ? ORDER BY tournament, k", [season, team_id]).groupby("tournament"):
        previous = None
        for row in group.itertuples():
            if pd.notna(row.match_id):
                after[int(row.match_id)] = float(row.p_title)
                before[int(row.match_id)] = previous if previous is not None else float(row.p_title)
            previous = float(row.p_title)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in matches.itertuples():
        match_id, is_home = int(row.match_id), int(row.home_id) == team_id
        rival_id = int(row.away_id if is_home else row.home_id)
        scored, conceded = (_int(row.home_score), _int(row.away_score)) if is_home else (_int(row.away_score), _int(row.home_score))
        result = None if scored is None or conceded is None else "G" if scored > conceded else "E" if scored == conceded else "P"
        lineup = lineups.get(match_id)
        altitude = _py(row.altitude_m)
        own_cards, rival_cards = cards.get((match_id, team_id)), cards.get((match_id, rival_id))  # None = el partido no tiene estadísticas de equipo
        grouped.setdefault(str(row.tournament), []).append(
            {
                "match_id": match_id,
                "tournament": row.tournament,
                "round_number": _int(row.round_number),
                "date": _iso(row.date),
                "status": _py(row.status),
                "is_home": is_home,
                "rival": release.team(rival_id),
                "estadio": _py(row.estadio),
                "ciudad": _py(row.ciudad),
                "altitude_m": altitude,
                "altitude_diff_m": None if altitude is None or base_altitude is None else float(altitude) - base_altitude,
                "goals_for": scored,
                "goals_against": conceded,
                "result": result,
                "xg_for": xg.get((match_id, team_id)),
                "xg_against": xg.get((match_id, rival_id)),
                "yellow_for": own_cards[0] if own_cards else None,
                "yellow_against": rival_cards[0] if rival_cards else None,
                "red_for": own_cards[1] if own_cards else None,
                "red_against": rival_cards[1] if rival_cards else None,
                "formation": _py(lineup.formation) if lineup is not None else None,
                "defenders_ok": bool(lineup.defenders_ok) if lineup is not None else None,
                "importance": importance.get(match_id),
                "p_title_before": before.get(match_id),
                "p_title_after": after.get(match_id),
            }
        )
    return {"release_id": release.release_id, "team": team, "season": season, "base_altitude_m": base_altitude, "tournaments": grouped}


def team_title_race(release: Release, team_id: int, season: int, tournament: str | None) -> dict[str, Any]:
    team = release.team(team_id)
    if team is None:
        raise NotFound(f"no existe el equipo {team_id}")
    available = [str(name) for name in release.q("SELECT DISTINCT tournament FROM title_probability WHERE season = ?", [season])["tournament"]]
    tournament = tournament or _default_tournament(available)
    if tournament is None or tournament not in available:
        return {"release_id": release.release_id, "season": season, "tournament": tournament, "team": team, "teams": [], "missing_reason": "no_data"}
    frame = release.q("SELECT team_id, k, p_title, points, match_id FROM title_probability WHERE season = ? AND tournament = ? ORDER BY team_id, k", [season, tournament])
    series = []
    for current_id, group in frame.groupby("team_id"):
        ref = release.team(int(current_id)) or {"team_id": int(current_id), "name": str(current_id)}
        points = [{"k": int(row.k), "p_title": float(row.p_title), "points": _int(row.points), "match_id": _int(row.match_id)} for row in group.itertuples()]
        series.append({**{key: ref.get(key) for key in ("team_id", "name", "color", "crest")}, "final_points": points[-1]["points"], "series": points})
    series.sort(key=lambda item: (-(item["series"][-1]["p_title"]), item["team_id"]))
    return {"release_id": release.release_id, "season": season, "tournament": tournament, "team": team, "teams": series}


def team_players(release: Release, team_id: int, season: int) -> dict[str, Any]:
    team = release.team(team_id)
    if team is None:
        raise NotFound(f"no existe el equipo {team_id}")
    frame = release.q(
        "SELECT pm.player_id, p.name, p.short_name, p.position, p.photo, "
        "COUNT(*) FILTER (WHERE pm.minutesplayed > 0) AS matches, SUM(pm.minutesplayed) AS minutes, SUM(pm.goals) AS goals, SUM(pm.assists) AS assists, "
        "AVG(pm.rating) FILTER (WHERE pm.minutesplayed > 0 AND pm.rating IS NOT NULL) AS rating "
        "FROM player_match pm JOIN players p ON p.player_id = pm.player_id JOIN matches m ON m.match_id = pm.match_id "
        "WHERE pm.season = ? AND pm.team_id = ? GROUP BY 1, 2, 3, 4, 5 ORDER BY minutes DESC, pm.player_id",
        [season, team_id],
    )
    shots = {int(row.player_id): row for row in release.q("SELECT player_id, COUNT(*) AS shots, SUM(xg) AS xg FROM shot_events WHERE season = ? AND team_id = ? GROUP BY 1", [season, team_id]).itertuples()}
    players = []
    for row in records(frame):
        shot = shots.get(int(row["player_id"]))
        players.append({**row, "photo": Release.photo_url(row["photo"]), "shots": int(shot.shots) if shot is not None else 0, "xg": float(shot.xg) if shot is not None else 0.0})
    return {"release_id": release.release_id, "team": team, "season": season, "players": players, "missing_reason": None if players else "no_data"}


def match_detail(release: Release, match_id: int) -> dict[str, Any]:
    frame = release.q("SELECT m.*, v.altitud_msnm AS altitude_m FROM matches m LEFT JOIN venues v ON v.estadio = m.estadio AND v.ciudad = m.ciudad WHERE m.match_id = ?", [match_id])
    if frame.empty:
        raise NotFound(f"no existe el partido {match_id}")
    row = frame.iloc[0]
    season, tournament = int(row["season"]), str(row["tournament"])
    shots = release.q("SELECT s.shot_id, s.player_id, p.name AS player_name, s.team_id, s.is_home, s.minute, s.x, s.y, s.xg, s.is_goal, s.situation, s.body_part, s.shot_type FROM shot_events s LEFT JOIN players p ON p.player_id = s.player_id WHERE s.match_id = ? ORDER BY s.minute", [match_id])
    lineups = {str(item.side): item for item in release.q("SELECT side, formation, defenders_ok FROM lineups WHERE match_id = ?", [match_id]).itertuples()}
    importance = {int(item["team_id"]): item for item in records(release.q("SELECT team_id, band, band_name, lives, threshold_used, matches_before, matches_remaining, points_before, points_needed FROM match_importance WHERE match_id = ?", [match_id]))}
    after = {int(item.team_id): float(item.p_title) for item in release.q("SELECT team_id, p_title FROM title_probability WHERE match_id = ? AND tournament = ?", [match_id, tournament]).itertuples()}

    def side(name: str) -> dict[str, Any]:
        team_id = int(row["home_id" if name == "home" else "away_id"])
        lineup = lineups.get(name)
        return {
            "team": release.team(team_id),
            "score": _int(row["home_score" if name == "home" else "away_score"]),
            "formation": _py(lineup.formation) if lineup is not None else None,
            "defenders_ok": bool(lineup.defenders_ok) if lineup is not None else None,
            "xg": float(shots.loc[shots["is_home"] == (name == "home"), "xg"].sum()) if not shots.empty else None,
            "importance": importance.get(team_id),
            "p_title_after": after.get(team_id),
        }

    players = release.q("SELECT pm.player_id, p.name, p.photo, pm.team_id, pm.position, pm.minutesplayed, pm.goals, pm.assists, pm.rating FROM player_match pm JOIN players p ON p.player_id = pm.player_id WHERE pm.match_id = ? ORDER BY pm.team_id, pm.minutesplayed DESC", [match_id])
    match = {
        "match_id": match_id, "season": season, "tournament": tournament, "round_number": _int(row["round_number"]), "date": _iso(row["date"]), "status": _py(row["status"]),
        "estadio": _py(row["estadio"]), "ciudad": _py(row["ciudad"]), "arbitro": _py(row["arbitro"]), "altitude_m": _py(row["altitude_m"]), "home": side("home"), "away": side("away"),
    }
    return {
        "release_id": release.release_id,
        "match": match,
        "shots": records(shots),
        "players": [{**item, "photo": Release.photo_url(item["photo"])} for item in records(players)],
    }


def _player_row(release: Release, player_id: int) -> pd.Series:
    frame = release.q("SELECT * FROM players WHERE player_id = ?", [player_id])
    if frame.empty:
        raise NotFound(f"no existe el jugador {player_id}")
    return frame.iloc[0]


def player_profile(release: Release, player_id: int, season: int | None) -> dict[str, Any]:
    player = _player_row(release, player_id)
    stats = release.q(
        "SELECT pm.season, arg_max(pm.team_id, pm.minutesplayed) AS team_id, COUNT(*) FILTER (WHERE pm.minutesplayed > 0) AS matches, SUM(pm.minutesplayed) AS minutes, "
        "SUM(pm.goals) AS goals, SUM(pm.assists) AS assists, SUM(pm.yellowcards) AS yellow, SUM(pm.redcards) AS red, "
        "AVG(pm.rating) FILTER (WHERE pm.minutesplayed > 0 AND pm.rating IS NOT NULL) AS rating "
        "FROM player_match pm JOIN matches m ON m.match_id = pm.match_id WHERE pm.player_id = ? GROUP BY 1 ORDER BY 1 DESC",
        [player_id],
    )
    shots = {int(row.season): row for row in release.q("SELECT season, COUNT(*) AS shots, SUM(xg) AS xg FROM shot_events WHERE player_id = ? GROUP BY 1", [player_id]).itertuples()}
    seasons_list = []
    for row in records(stats):
        shot = shots.get(int(row["season"]))
        xg = float(shot.xg) if shot is not None else 0.0
        seasons_list.append({**row, "team": release.team(row["team_id"]), "shots": int(shot.shots) if shot is not None else 0, "xg": xg, "goals_minus_xg": (row["goals"] or 0) - xg})
    selected = season if season is not None else (seasons_list[0]["season"] if seasons_list else None)
    season_stats = next((item for item in seasons_list if item["season"] == selected), None)
    return {
        "release_id": release.release_id,
        "player": {"player_id": player_id, "name": _py(player["name"]), "short_name": _py(player["short_name"]), "position": _py(player["position"]), "team": release.team(_int(player["team_id"])), "photo": Release.photo_url(_py(player["photo"]))},
        "seasons": seasons_list,
        "selected_season": selected,
        "season_stats": season_stats,
        "missing_reason": None if season_stats is not None else "no_data_for_season",
    }


def player_shots(release: Release, player_id: int, season: int | None) -> dict[str, Any]:
    _player_row(release, player_id)
    condition, params = ("AND s.season = ?", [player_id, season]) if season is not None else ("", [player_id])
    frame = release.q(
        "SELECT s.match_id, s.season, s.minute, s.x, s.y, s.xg, s.is_goal, s.situation, s.body_part, s.shot_type, m.date, "
        "CASE WHEN s.team_id = m.home_id THEN m.away_id ELSE m.home_id END AS rival_id "
        f"FROM shot_events s JOIN matches m ON m.match_id = s.match_id WHERE s.player_id = ? {condition} ORDER BY m.date, s.minute",
        params,
    )
    shots = [{**row, "rival": (release.team(row["rival_id"]) or {}).get("name")} for row in records(frame)]
    return {"release_id": release.release_id, "player_id": player_id, "season": season, "shots": shots, "missing_reason": None if shots else "no_data"}


def player_heatmap(release: Release, player_id: int, season: int | None) -> dict[str, Any]:
    _player_row(release, player_id)
    condition, params = ("AND season = ?", [player_id, season]) if season is not None else ("", [player_id])
    last = HEATMAP_BINS - 1
    cells = release.q(
        f"SELECT LEAST(CAST(floor(x / {100 // HEATMAP_BINS}) AS INTEGER), {last}) AS ix, LEAST(CAST(floor(y / {100 // HEATMAP_BINS}) AS INTEGER), {last}) AS iy, COUNT(*) AS n "
        f"FROM heatmap_points WHERE player_id = ? {condition} AND x IS NOT NULL AND y IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2",
        params,
    )
    matches = release.q(f"SELECT COUNT(DISTINCT match_id) AS n FROM heatmap_points WHERE player_id = ? {condition}", params)["n"].iloc[0]
    total = int(cells["n"].sum()) if not cells.empty else 0
    return {
        "release_id": release.release_id, "player_id": player_id, "season": season, "cols": HEATMAP_BINS, "rows": HEATMAP_BINS, "total": total, "matches": int(matches),
        "cells": [{"ix": int(row.ix), "iy": int(row.iy), "n": int(row.n)} for row in cells.itertuples()], "missing_reason": None if total else "no_data",
    }


def status(release: Release) -> dict[str, Any]:
    cutoff = datetime.now() - timedelta(hours=STALE_AFTER_HOURS)
    overdue = int(release.q("SELECT COUNT(*) AS n FROM matches WHERE date < ? AND home_score IS NULL AND (status IS NULL OR status = 'finished')", [cutoff])["n"].iloc[0])
    coverage = records(release.q("SELECT * FROM data_coverage ORDER BY season DESC, kind"))
    models = []
    for row in records(release.q("SELECT * FROM model_runs")):
        for key in ("params", "metrics"):
            try:
                row[key] = json.loads(row[key]) if isinstance(row[key], str) else row[key]
            except ValueError:
                pass
        models.append(row)
    return {
        "release_id": release.release_id,
        "built_at": release.manifest.get("built_at"),
        "data_as_of": release.manifest.get("data_as_of"),
        "stale": overdue > 0,
        "stale_after_hours": STALE_AFTER_HOURS,
        "overdue_matches": overdue,
        "coverage": coverage,
        # lo que sí se puede recuperar: nunca se pidió, dio error o se cortó por bloqueo (un 404 de SofaScore no es recuperable)
        "actionable": [
            {"season": row["season"], "kind": row["kind"], "pending": row["pending"], "failed": row["failed"], "blocked": row["blocked"]}
            for row in coverage
            if row["pending"] + row["failed"] + row["blocked"] > 0
        ],
        "known_gaps": records(release.q("SELECT * FROM known_gaps")),
        "ledger": release.manifest.get("ledger", {}),
        "models": models,
        "release_log": records(release.q("SELECT * FROM release_log ORDER BY built_at DESC")),
    }
