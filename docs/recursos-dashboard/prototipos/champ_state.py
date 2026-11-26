"""Estado de 'camino al título' por partido, con umbral de campeón (imagen del usuario) -> módulo reutilizable + escaneo de candidatos."""
import sys
import numpy as np
import pandas as pd
from pathlib import Path

REPO = Path(r"C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz")
BASE = REPO / "gronestats/data/Liga 1 Peru"
THRESH = [41, 42, 42, 39, 40, 37, 39, 40, 40]          # puntos del campeón: A22 C22 A23 C23 A24 C24 A25 C25 A26 (imagen del usuario)
T_REF = float(np.mean(THRESH))                            # 40.0
BANDS = [("Asegurado (umbral alcanzado)", "#0a84ff"), ("Baja (puede perder 3 o más)", "#34c759"), ("Media (puede perder 2)", "#ffcc00"),
         ("Alta (puede perder 1)", "#ff9500"), ("Crítica (no puede perder)", "#ff3b30"), ("Fuera de alcance", "#8e8e93")]


def band_of(needed, remaining):
    """Importancia por 'derrotas permitidas': holgura = puntos máximos restantes - puntos necesarios; una derrota cuesta 3."""
    if remaining <= 0: return None, None
    slack = 3 * remaining - needed
    if needed <= 0: return 0, None
    if slack < 0: return 5, int(np.floor(slack / 3))
    lives = int(slack // 3)
    return (1 if lives >= 3 else 2 if lives == 2 else 3 if lives == 1 else 4), lives


def team_states(season, team, T=T_REF):
    m = pd.read_parquet(BASE / str(season) / "dashboard/current/matches.parquet")
    m = m[m.tournament.astype(str).str.contains("Apertura|Clausura") & m.home_score.notna()].copy()
    m["dt"] = pd.to_datetime(m.fecha, format="%d/%m/%Y %H:%M", errors="coerce")
    m["tour"] = np.where(m.tournament.astype(str).str.contains("Apertura"), "Apertura", "Clausura")
    # partidos por equipo = equipos - 1 (round-robin simple). NO usar rondas: con 19 equipos hay 19 rondas pero cada uno juega 18.
    R = {t: len(set(g.home_id) | set(g.away_id)) - 1 for t, g in m.groupby("tour")}
    full = {t: len(g) == (R[t] + 1) * R[t] // 2 for t, g in m.groupby("tour")}      # ¿trae todos los partidos del torneo?
    mine = m[(m.home_id == team) | (m.away_id == team)].sort_values("dt")
    rows = []
    for tour, g in mine.groupby("tour", sort=False):
        p = 0
        for k, r in enumerate(g.itertuples()):
            home = r.home_id == team; gf, ga = (r.home_score, r.away_score) if home else (r.away_score, r.home_score)
            pts = 3 if gf > ga else 1 if gf == ga else 0
            rem = R[tour] - k
            band, lives = band_of(T - p, rem)
            rows.append(dict(mid=int(r.match_id), tour=tour, k=k, p_before=p, rem=rem, needed=T - p, need_pm=(T - p) / rem if rem > 0 else np.nan,
                             band=band, lives=lives, pts=pts, p_after=p + pts, R=R[tour], idx_after=min(1.0, (p + pts) / T), complete=full[tour]))
            p += pts
    return pd.DataFrame(rows)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    te = pd.read_parquet(BASE / "2025/dashboard/current/teams.parquet").set_index("team_id")
    print(f"umbral de referencia T = {T_REF:.1f} (media de {len(THRESH)} torneos; rango {min(THRESH)}–{max(THRESH)})")
    for tid in te[te.competitiveness_level == "Candidato"].index:
        s = team_states(2025, tid)
        print(f"\n{te.loc[tid, 'short_name']} 2025: {len(s)} partidos | bandas:", {BANDS[int(b)][0].split(' (')[0]: int(c) for b, c in s.band.value_counts().sort_index().items()},
              "| puntos finales:", s.groupby("tour").p_after.max().to_dict())
