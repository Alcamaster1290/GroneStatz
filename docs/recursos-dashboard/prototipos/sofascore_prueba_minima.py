"""Prueba mínima y de solo lectura contra SofaScore (autorizada por Alvaro el 2026-11-25). Máximo 2 peticiones.
Reglas: 1 intento por petición, pausa de 2,5 s, parar en el primer error, sin heatmaps, sin escribir en el repo, cerrar el navegador al terminar."""
import os, sys, json, time
from pathlib import Path

os.environ["GRONESTATS_SOFASCORE_ATTEMPTS"] = "1"
os.environ["GRONESTATS_SOFASCORE_MIN_INTERVAL"] = "2.5"
os.environ["GRONESTATS_SOFASCORE_HEADLESS"] = "0"          # sesión visible, la única que ha funcionado
REPO = Path(r"C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz")
OUT = Path(__file__).parent
sys.path.insert(0, str(REPO))
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd
from gronestats.processing import sofascore_session as ss

log = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "calls": []}
def call(label, path):
    t0 = time.time()
    r = ss.get_json("https://api.sofascore.com" + path)
    blocked = (not isinstance(r, dict)) or ("error" in r)
    log["calls"].append({"label": label, "path": path, "seconds": round(time.time() - t0, 1), "blocked": blocked, "top_keys": list(r.keys())[:12] if isinstance(r, dict) else None,
                         "error": r.get("error") if isinstance(r, dict) else None})
    print(f"[{label}] {'BLOQUEADO ' + json.dumps(r.get('error')) if blocked else 'OK'} en {time.time() - t0:.1f}s")
    return r, blocked

try:
    m = pd.read_excel(REPO / "gronestats/data/Liga 1 Peru/2026/raw/master/raw/Partidos_Liga 1 Peru_2026.xlsx")
    season_id = int(m.season.iloc[0]) if "season" in m.columns and str(m.season.iloc[0]).isdigit() else 88529
    print("season id usado:", season_id, "| columnas del maestro crudo:", [c for c in m.columns if "season" in c.lower() or "id" in c.lower()][:8])
    # 1) alineaciones de un partido que YA tenemos (2025, ronda 1): comprueba el transporte y si trae 'formation'
    r1, b1 = call("alineaciones", "/api/v1/event/13352931/lineups")
    if not b1:
        (OUT / "lineups_13352931.json").write_text(json.dumps(r1, ensure_ascii=False), encoding="utf-8")
        for side in ("home", "away"):
            d = r1.get(side, {}); print(f"  {side}: claves={list(d.keys())} | formation={d.get('formation')!r} | jugadores={len(d.get('players', []))}")
        # 2) lista de partidos más recientes del torneo: ¿hay partidos posteriores al 2026-10-18?
        r2, b2 = call("lista de partidos 2026 (página 0, últimos)", f"/api/v1/unique-tournament/406/season/{season_id}/events/last/0")
        if not b2:
            (OUT / "events_last0.json").write_text(json.dumps(r2, ensure_ascii=False), encoding="utf-8")
            ev = r2.get("events", []); print("  eventos en la página:", len(ev), "| hay más páginas:", r2.get("hasNextPage"))
            known = set(pd.to_numeric(m.match_id, errors="coerce").dropna().astype(int))
            rows = [(e["id"], pd.to_datetime(e["startTimestamp"], unit="s"), e.get("status", {}).get("description"), e.get("roundInfo", {}).get("round"), e["homeTeam"]["name"], e["awayTeam"]["name"],
                     e.get("homeScore", {}).get("current"), e.get("awayScore", {}).get("current")) for e in ev]
            df = pd.DataFrame(rows, columns=["id", "inicio_utc", "estado", "ronda", "local", "visita", "gl", "gv"]); df["en_maestro"] = df.id.isin(known)
            print("  rango de fechas:", df.inicio_utc.min(), "→", df.inicio_utc.max(), "| estados:", df.estado.value_counts().to_dict())
            print("  NO están en tu maestro crudo:", int((~df.en_maestro).sum()), "de", len(df))
            print(df[~df.en_maestro].sort_values("inicio_utc").head(12).to_string(index=False))
            df.to_csv(OUT / "events_last0_resumen.csv", index=False, encoding="utf-8-sig")
finally:
    log["finished"] = time.strftime("%Y-%m-%d %H:%M:%S"); (OUT / "sofascore_test_result.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    ss._close_driver(); print("navegador cerrado; resultado guardado en sofascore_test_result.json")
