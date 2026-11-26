"""Verifica la orientación de coordenadas de tiros y posiciones USANDO el código funcional del usuario (gronestats.dashboard)."""
import sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(r"C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz"); sys.path.insert(0, str(REPO)); B = REPO / "gronestats/data/Liga 1 Peru"
from gronestats.dashboard.metrics import build_match_shot_events                       # <- código del usuario
from gronestats.dashboard.data import normalize_shot_events, normalize_average_positions

# 1) tiros con coordenadas completas (2023) normalizados con SU función de datos
s23 = normalize_shot_events(pd.read_parquet(B / "2023/dashboard/current/shot_events.parquet")); m23 = pd.read_parquet(B / "2023/dashboard/current/matches.parquet")
g = s23[(s23.shot_type == "goal") & (s23.goal_type.astype("string") != "own")]
print("== 1) 2023, valores CRUDOS de x por lado (is_home) — ¿misma convención para local y visita?")
for name, d in (("goles local", g[g.is_home == True]), ("goles visita", g[g.is_home == False])):
    print(f"   {name:13s} n={len(d):4d}  x medio={d.x.mean():5.1f}  y medio={d.y.mean():5.1f}  x mediana={d.x.median():5.1f}")
pen = s23[s23.situation.astype("string") == "penalty"]
for name, d in (("penal local", pen[pen.is_home == True]), ("penal visita", pen[pen.is_home == False])):
    print(f"   {name:13s} n={len(d):4d}  x medio={d.x.mean():5.1f}  y medio={d.y.mean():5.1f}  (Opta: el punto de penal está a 11,5 de la línea de fondo)")
sd = s23.dropna(subset=["x"]); print(f"   TODOS los tiros: local x medio={sd[sd.is_home == True].x.mean():.1f} | visita x medio={sd[sd.is_home == False].x.mean():.1f}")

# 2) lo que hace SU build_match_shot_events (refleja la visita para dibujar)
mid = int(s23[s23.shot_type == "goal"].match_id.iloc[10]); mrow = m23[m23.match_id == mid].iloc[0]
subset, meta = build_match_shot_events(s23, mrow)
print(f"\n== 2) build_match_shot_events (partido {mid}: {mrow.home} vs {mrow.away}) — crudo vs 'display' (lo que dibuja tu mapa)")
print(subset.groupby("side").agg(tiros=("x", "size"), x_crudo=("x", "mean"), display_x=("display_x", "mean"), y_crudo=("y", "mean"), display_y=("display_y", "mean")).round(1).to_string())
print("   nota de tu código:", meta.get("orientation_note"))
gg = subset[subset.shot_type_norm == "goal"][["side", "minute_label", "x", "y", "display_x", "display_y"]]; print("   goles de ese partido:\n" + gg.to_string(index=False))

# 3) posiciones medias: 'average_x' va en dirección de ataque (0 = arco propio)? comparar con la posición del tirador
ap = normalize_average_positions(pd.read_parquet(B / "2023/dashboard/current/average_positions.parquet"))
j = s23.dropna(subset=["x"]).merge(ap[["match_id", "player_id", "average_x", "average_y", "position"]], on=["match_id", "player_id"], how="inner")
print(f"\n== 3) posición media del tirador vs x del tiro (n={len(j)}) — se espera correlación NEGATIVA si el tiro mide 'distancia al arco atacado' y average_x mide 'avance'")
print("   corr(average_x, x_tiro) =", round(float(np.corrcoef(j.average_x, j.x)[0, 1]), 3), "| por posición (G/D/M/F) x medio del tiro:", j.groupby("position").x.mean().round(1).to_dict(), "| average_x medio por posición:", j.groupby("position").average_x.mean().round(1).to_dict())
print("   corr(average_y, y_tiro) =", round(float(np.corrcoef(j.average_y, j.y)[0, 1]), 3), "(+ = mismo sentido lateral en posiciones y tiros)")
for side in (True, False):
    jj = j[j.is_home == side]; print(f"   {'local' if side else 'visita':6s} corr(average_x, x_tiro)={np.corrcoef(jj.average_x, jj.x)[0, 1]:.3f}  corr(average_y, y_tiro)={np.corrcoef(jj.average_y, jj.y)[0, 1]:.3f}")
