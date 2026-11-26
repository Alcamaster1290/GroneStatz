"""Prueba de humo de la web con datos reales: cada página responde 200 y trae su contenido clave.

Requiere la API (127.0.0.1:8000) y la web (127.0.0.1:3000) en marcha:
    py -3.11 -m gronestats.api            # en una terminal
    cd web && npm run dev                 # en otra
    py -3.11 scripts/smoke_web.py
"""

from __future__ import annotations

import sys

import httpx

WEB = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000"


def main() -> int:
    api = httpx.Client(base_url=API, timeout=30)
    web = httpx.Client(base_url=WEB, timeout=60, follow_redirects=True)
    release = api.get("/v1/release").json()
    season = release["seasons"][0]
    standings = api.get(f"/v1/seasons/{season}/standings", params={"tournament": "Clausura"}).json()
    leader = standings["rows"][0]
    strip = api.get(f"/v1/teams/{leader['team_id']}/seasons/{season}/matches").json()
    first_match = next(match for match in strip["tournaments"]["Clausura"] if match["result"])
    squad = api.get(f"/v1/teams/{leader['team_id']}/seasons/{season}/players").json()["players"]
    with_photo = next(player for player in squad if player["photo"])
    without_photo = next((player for player in squad if not player["photo"]), squad[-1])

    checks = [
        ("/", ["Tabla tras la fecha", leader["name"]]),
        (f"/liga/{season}/Clausura", ["Probabilidad de campeonar", "Pts"]),
        (f"/liga/{season}/Apertura?fecha=5", ["Tabla tras la fecha 5"]),
        (f"/liga/{season}/Acumulada", ["Tabla acumulada"]),
        (f"/equipos/{leader['team_id']}-x?season={season}&torneo=Clausura", ["Partido a partido", "Plantel", "Próximamente", leader["name"]]),
        (f"/jugadores/{with_photo['player_id']}-x?season={season}", ["Mapa de tiros", "Por temporada", with_photo["name"]]),
        (f"/jugadores/{without_photo['player_id']}-x?season={season}", [without_photo["name"]]),
        (f"/partidos/{first_match['match_id']}", ["Tiros y xG", "Formación declarada", "Jugadores"]),
        ("/estado", ["Cobertura por temporada", "Huecos conocidos", "Modelos", "Últimos releases"]),
    ]
    failures = 0
    for path, needles in checks:
        response = web.get(path)
        missing = [needle for needle in needles if needle not in response.text]
        ok = response.status_code == 200 and not missing
        failures += not ok
        print(f"{'OK ' if ok else 'FALLA'} {response.status_code} {path}" + (f"  → falta: {missing}" if missing else ""))
    for path in ("/equipos/abc", "/liga/2026/Verano", "/partidos/1"):
        status = web.get(path).status_code
        failures += status != 404
        print(f"{'OK ' if status == 404 else 'FALLA'} {status} {path} (debe ser 404)")
    print(f"\n{len(checks) + 3 - failures} de {len(checks) + 3} comprobaciones correctas")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
