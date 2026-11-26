"""Entradas sintéticas del constructor del bundle: dos temporadas, cuatro equipos y las salidas de análisis con las columnas reales.

Sirven para probar ``build_web_bundle`` y, con su resultado, la API. Nada depende de los datos reales del repo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

SEASONS = (2025, 2026)
TEAMS = {1: ("Alfa", "#112548", "Candidato"), 2: ("Beta", "#aa0000", "Competitivo"), 3: ("Gama", "#007a33", "Promedio"), 4: ("Delta", "#f2a900", None)}
ROUNDS = {1: [(1, 2), (3, 4)], 2: [(1, 3), (2, 4)], 3: [(1, 4), (2, 3)]}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@dataclass(frozen=True)
class WebInputs:
    data_dir: Path
    analytics_dir: Path
    images_dir: Path
    played: dict[int, list[int]]  # temporada -> partidos jugados con marcador normal


def _match_rows(season: int) -> list[dict]:
    rows = []
    for tournament, name in (("Apertura", "Liga 1, Apertura"), ("Clausura", "Liga 1, Clausura")):
        for round_number, pairs in ROUNDS.items():
            for number, (home, away) in enumerate(pairs):
                match_id = season * 1000 + (0 if tournament == "Apertura" else 100) + round_number * 10 + number
                kickoff = datetime(season, 2 if tournament == "Apertura" else 8, 1, 15, 15) + timedelta(days=7 * (round_number - 1) + number)
                status, home_score, away_score = None, match_id % 3, (match_id // 3) % 2
                if season == 2026 and tournament == "Clausura" and (round_number, number) == (3, 1):
                    status, home_score, away_score = "postponed", None, None  # aplazado: sin marcador
                if season == 2025 and tournament == "Apertura" and (round_number, number) == (3, 0):
                    status = "annulled"  # se jugó pero no cuenta
                rows.append(
                    {"match_id": match_id, "round_number": round_number, "tournament": name, "season": season, "status": status, "home_id": home, "away_id": away,
                     "home": TEAMS[home][0], "away": TEAMS[away][0], "home_score": home_score, "away_score": away_score, "resultado_final": "x",
                     "fecha": kickoff.strftime("%d/%m/%Y %H:%M"), "estadio": f"Estadio {TEAMS[home][0]}", "ciudad": f"Ciudad {TEAMS[home][0]}", "arbitro": "Árbitro Uno"}
                )
    return rows


def make_web_inputs(root: Path) -> WebInputs:
    data_dir, analytics_dir, images_dir = root / "data", root / "analytics", root / "images" / "players"
    images_dir.mkdir(parents=True)
    (images_dir / "11.png").write_bytes(PNG)  # solo el jugador 11 tiene foto
    played: dict[int, list[int]] = {}
    shots, probability, importance, lineups = [], [], [], []

    for season in SEASONS:
        folder = data_dir / str(season) / "dashboard" / "current"
        folder.mkdir(parents=True)
        matches = pd.DataFrame(_match_rows(season))
        matches.to_parquet(folder / "matches.parquet", index=False)
        pd.DataFrame(
            [
                {"team_id": team, "short_name": name, "full_name": f"Club {name}", "team_colors": color, "is_altitude_team": False,
                 "competitiveness_level": level if (season == 2026 or team != 3) else None, "stadium_id": team, "stadium_name_city": f"Estadio {name} / Ciudad {name}",
                 "province": "Lima", "department": "Lima", "region": "Centro"}
                for team, (name, color, level) in TEAMS.items()
            ]
        ).to_parquet(folder / "teams.parquet", index=False)
        pd.DataFrame(
            [{"player_id": team * 10 + n, "name": f"Jugador {team}{n}", "short_name": f"J{team}{n}", "position": "F", "team_id": team, "dateofbirth": None, "age_jan_2026": 25} for team in TEAMS for n in (1, 2)]
        ).to_parquet(folder / "players.parquet", index=False)

        normal = matches[matches["home_score"].notna() & (matches["status"] != "annulled")]
        played[season] = [int(match_id) for match_id in normal["match_id"]]
        pm_rows, hm_rows, momentum, stats, positions = [], [], [], [], []
        for row in normal.itertuples():
            for team in (row.home_id, row.away_id):
                for n in (1, 2):
                    pm_rows.append({"match_id": row.match_id, "player_id": team * 10 + n, "name": f"Jugador {team}{n}", "team_id": team, "position": "F", "minutesplayed": 90 if n == 1 else 20,
                                    "goals": int(n == 1 and team == row.home_id and row.home_score > 0), "assists": 0, "yellowcards": 0, "redcards": 0, "saves": 0, "fouls": 1,
                                    "penaltywon": 0, "penaltysave": 0, "penaltyconceded": 0, "rating": 6.5 + n / 10})
        for match_id in played[season][:2]:
            hm_rows += [{"match_id": match_id, "player_id": 11, "team_id": 1, "team_name": "Alfa", "name": "Jugador 11", "x": 40 + i * 5, "y": 30 + i * 8} for i in range(5)]
        for match_id in played[season][::2]:
            momentum.append({"match_id": match_id, "minute": 1, "value": 5, "dominant_side": "home"})
        for match_id in played[season][:3]:
            stats.append({"MATCH_ID": match_id, "KEY": "expectedGoals", "PERIOD": "ALL", "HOMEVALUE": 1.1, "AWAYVALUE": 0.8})
            positions.append({"match_id": match_id, "player_id": 11, "team_id": 1, "average_x": 50, "average_y": 50})
        pd.DataFrame(pm_rows).to_parquet(folder / "player_match.parquet", index=False)
        pd.DataFrame(hm_rows).to_parquet(folder / "heatmap_points.parquet", index=False)
        pd.DataFrame(momentum).to_parquet(folder / "match_momentum.parquet", index=False)
        pd.DataFrame(stats).to_parquet(folder / "team_stats.parquet", index=False)
        pd.DataFrame(positions).to_parquet(folder / "average_positions.parquet", index=False)

        for row in normal.itertuples():
            for side, team in (("home", row.home_id), ("away", row.away_id)):
                for n in range(2):
                    shots.append({"season": season, "match_id": row.match_id, "shot_id": row.match_id * 10 + (0 if side == "home" else 5) + n, "player_id": team * 10 + 1, "name": f"Jugador {team}1",
                                  "team_id": team, "team_name": TEAMS[team][0], "is_home": side == "home", "shot_type": "miss", "situation": "regular", "body_part": "right-foot",
                                  "time": 10 + n * 30, "x": 8.0 + 6 * n, "y": 45.0 + 5 * n, "is_goal": int(n == 0 and side == "home" and row.home_score > 0), "xg": 0.1 + 0.2 * n, "xg_source": "oos"})
                lineups.append({"season": season, "match_id": row.match_id, "side": side, "team_id": team, "formation": "4-3-3", "confirmed": True, "expected": "4-3-3", "counted": "4-3-3",
                                "diff": "", "consistent": True, "defenders_ok": not (season == 2026 and row.match_id == played[2026][0] and side == "away"), "reason": ""})
        for tournament in ("Apertura", "Clausura"):
            names = matches[matches["tournament"] == f"Liga 1, {tournament}"]
            seen: dict[int, int] = {}
            for row in names.sort_values(["round_number", "match_id"]).itertuples():
                if row.match_id not in played[season]:
                    continue
                for team in (row.home_id, row.away_id):
                    before = seen.get(team, 0)
                    importance.append({"season": season, "tour": tournament, "match_id": row.match_id, "round_number": row.round_number, "date": pd.NaT, "team_id": team, "matches_before": before,
                                       "points_before": before * 1.0, "matches_remaining": 3 - before, "threshold_used": 40.0 if before < 2 else 37.0, "points_needed": 40.0 - before,
                                       "lives": 3 - before, "band": 1, "band_name": "Baja", "team_name": TEAMS[team][0]})
                    seen[team] = before + 1
            for k in range(4):
                for team in TEAMS:
                    probability.append({"season": season, "tour": tournament, "match_id": float("nan") if k == 0 else float(names["match_id"].iloc[k - 1]), "team_id": team, "k": k, "p_title": 0.25,
                                        "points": k, "rating": 1450.0, "team_name": TEAMS[team][0]})

    for folder_name, frame, filename in (("xg-prototipo", pd.DataFrame(shots), "xg_tiros.parquet"), ("title-race", pd.DataFrame(importance), "importancia_equipo_partido.parquet"),
                                         ("title-race", pd.DataFrame(probability), "probabilidad_titulo.parquet"), ("formaciones", pd.DataFrame(lineups), "formaciones_equipo_partido.parquet")):
        (analytics_dir / folder_name).mkdir(parents=True, exist_ok=True)
        frame.to_parquet(analytics_dir / folder_name / filename, index=False)
    pd.DataFrame([{"season": s, "tiros_modelo": 10, "log_loss_modelo": 0.25, "log_loss_solo_distancia": 0.26, "log_loss_constante": 0.3, "auc": 0.79, "brier": 0.07, "xG_total": 5.0, "goles": 5} for s in SEASONS]).to_csv(
        analytics_dir / "xg-prototipo" / "xg_validacion.csv", index=False
    )
    (analytics_dir / "title-race" / "parametros_elo.json").write_text(
        json.dumps({"params": {"k": 20, "home": 70, "altitude": 60, "regression": 0.0, "draw_max": 0.32, "initial": 1450}, "sigma": 120.0, "n_sim": 3000, "fit_seasons": [2025], "perdida_ajuste": 0.94, "fuera_de_muestra": {}}), encoding="utf-8"
    )
    pd.DataFrame(
        [{"estadio": f"Estadio {name}", "ciudad_en_el_maestro": f"Ciudad {name}", "latitud": -12.0, "longitud": -77.0, "precision_ubicacion": "estadio", "altitud_msnm": 100 * team, "fuente_altitud": "prueba"} for team, (name, _, _) in TEAMS.items()]
    ).to_csv(analytics_dir / "altitud_estadios_medida.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{"team_id": 3, "equipo": "Gama", "nivel_asignado": "Promedio", "origen": "prueba"}, {"team_id": 4, "equipo": "Delta", "nivel_asignado": "Descenso", "origen": "prueba"}]).to_csv(
        analytics_dir / "nivel_competitividad_faltante.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([{"season": 2026, "tournament": "Apertura", "team_id": 4, "team": "Delta", "pj": 0, "pg": 0, "pe": 0, "pp": 0, "gf": 0, "gc": 0, "points": -3, "motivo": "deuda", "fuente": "prueba"}]).to_csv(
        data_dir / "ajustes_tabla.csv", index=False
    )
    pd.DataFrame([{"season": 2026, "kind": "venue", "scope": "partidos de local de Delta", "reason": "sin estadio en origen", "source": "prueba"}]).to_csv(data_dir / "known_gaps.csv", index=False)
    return WebInputs(data_dir, analytics_dir, images_dir, played)
