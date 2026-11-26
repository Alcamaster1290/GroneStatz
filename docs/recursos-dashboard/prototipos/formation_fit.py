import sys, numpy as np, pandas as pd
from collections import Counter, defaultdict
from scipy.optimize import linear_sum_assignment
sys.stdout.reconfigure(encoding="utf-8")
D = "gronestats/data/Liga 1 Peru/2025/dashboard/current"
ap = pd.read_parquet(f"{D}/average_positions.parquet"); te = pd.read_parquet(f"{D}/teams.parquet").set_index("team_id")
# (x = profundidad 0..100, y = ancho 0..100). Plantillas de 10 jugadores de campo, en unidades de posicion media de SofaScore.
def row(x, ys): return [(x, y) for y in ys]
D4 = row(30,[12,37,63,88]); D3 = row(28,[25,50,75]); D5 = [(34,6),(28,28),(26,50),(28,72),(34,94)]
T = {
 "4-3-3":   D4+[(48,28),(45,50),(48,72)]+[(66,16),(68,50),(66,84)],
 "4-4-2":   D4+[(48,12),(46,38),(46,62),(48,88)]+[(66,38),(66,62)],
 "4-2-3-1": D4+[(42,38),(42,62)]+[(58,14),(58,50),(58,86)]+[(70,50)],
 "4-1-4-1": D4+[(38,50)]+[(52,12),(50,38),(50,62),(52,88)]+[(68,50)],
 "4-4-1-1": D4+[(46,12),(44,38),(44,62),(46,88)]+[(58,50),(68,50)],
 "3-5-2":   D3+[(48,8),(42,30),(40,50),(42,70),(48,92)]+[(66,38),(66,62)],
 "3-4-3":   D3+[(44,38),(44,62),(50,10),(50,90)]+[(66,20),(68,50),(66,80)],
 "5-3-2":   D5+[(46,28),(44,50),(46,72)]+[(66,38),(66,62)],
 "3-4-2-1": D3+[(44,38),(44,62),(50,10),(50,90)]+[(58,35),(58,65),(68,50)],
}
Tn = {k: np.array(v, float) for k, v in T.items()}
def fit(P):
    P = np.array(P, float); out = {}
    for k, tpl in Tn.items():
        Q = P.copy(); Q[:,0] += tpl[:,0].mean() - Q[:,0].mean()      # alinear profundidad media (el bloque sube/baja)
        C = ((Q[:,None,:] - tpl[None,:,:]) * np.array([1.05, 0.68]))**2  # a metros
        r, c = linear_sum_assignment(C.sum(2)); out[k] = float(np.sqrt(C.sum(2)[r, c].mean()))
    return sorted(out.items(), key=lambda kv: kv[1])
st = ap[ap.is_starter==True]; res = []
for (tid, mid), g in st.groupby(["team_id","match_id"]):
    out = g[g.position!="G"]
    if len(out)!=10: continue
    f = fit(list(zip(out.average_x, out.average_y)))
    res.append((int(tid), int(mid), f[0][0], f[0][1], f[1][1]-f[0][1]))
R = pd.DataFrame(res, columns=["team","match","label","rmse","margin"])
print("partidos ajustados:", len(R))
print("error medio de ajuste (m): mediana=%.1f p90=%.1f" % (R.rmse.median(), R.rmse.quantile(.9)))
print("margen contra 2da mejor plantilla (m): mediana=%.2f | partidos con margen<1.0 m: %.0f%%" % (R.margin.median(), (R.margin<1.0).mean()*100))
print("distribucion de etiquetas (liga 2025):", R.label.value_counts().to_dict())
# estabilidad por equipo: fraccion de partidos con su etiqueta modal
stab = R.groupby("team").label.agg(lambda s: s.value_counts(normalize=True).iloc[0])
print("etiqueta modal cubre (por equipo): mediana=%.0f%% min=%.0f%% max=%.0f%%" % (stab.median()*100, stab.min()*100, stab.max()*100))
print("\nAlianza Universidad:", R[R.team==306660].label.value_counts().to_dict(), "| rmse mediana %.1f" % R[R.team==306660].rmse.median())
# comparacion honesta: ajuste de una plantilla ALEATORIA (barajando y) para ver si el ajuste es mejor que el azar
rng = np.random.default_rng(0); base=[]
for (tid, mid), g in list(st.groupby(["team_id","match_id"]))[:400]:
    out = g[g.position!="G"]
    if len(out)!=10: continue
    P = np.c_[out.average_x.values, rng.permutation(out.average_y.values)]
    base.append(fit(P)[0][1])
print("referencia: error de ajuste con ancho (y) barajado al azar: mediana=%.1f m" % np.median(base))
