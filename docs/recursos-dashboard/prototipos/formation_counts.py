import sys, numpy as np, pandas as pd
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
D = "gronestats/data/Liga 1 Peru/2025/dashboard/current"
ap = pd.read_parquet(f"{D}/average_positions.parquet"); st = ap[ap.is_starter == True]
te = pd.read_parquet(f"{D}/teams.parquet").set_index("team_id"); ma = pd.read_parquet(f"{D}/matches.parquet")

def labels(g):
    c = g.position.value_counts(); d, m, f = c.get("D", 0), c.get("M", 0), c.get("F", 0)
    base = f"{d}-{m}-{f}"
    mm = g[g.position == "M"].sort_values("average_x"); refined = base
    if len(mm) >= 4:                                   # partir mediocampo en 2 lineas si hay un hueco claro en x
        xs = mm.average_x.values; gaps = np.diff(xs); i = int(np.argmax(gaps))
        if gaps[i] >= 5.0: refined = f"{d}-{i+1}-{len(mm)-i-1}-{f}"
    return base, refined
rows = []
for (tid, mid), g in st.groupby(["team_id", "match_id"]):
    if len(g) != 11 or (g.position == "G").sum() != 1: continue
    b, r = labels(g); rows.append((int(tid), int(mid), b, r))
L = pd.DataFrame(rows, columns=["team", "match", "dmf", "refined"])
ma["dt"] = pd.to_datetime(ma.fecha, format="%d/%m/%Y %H:%M", errors="coerce"); L = L.merge(ma[["match_id", "dt"]], left_on="match", right_on="match_id").sort_values(["team", "dt"])
rng = np.random.default_rng(1)
def metrics(col):
    modal = L.groupby("team")[col].agg(lambda s: s.value_counts(normalize=True).iloc[0]).median()
    pers = np.mean([(g[col].values[1:] == g[col].values[:-1]).mean() for _, g in L.groupby("team")])
    base_modal, base_pers = [], []
    for _ in range(200):
        L2 = L.copy(); L2[col] = rng.permutation(L2[col].values)
        base_modal.append(L2.groupby("team")[col].agg(lambda s: s.value_counts(normalize=True).iloc[0]).median())
        base_pers.append(np.mean([(g[col].values[1:] == g[col].values[:-1]).mean() for _, g in L2.groupby("team")]))
    return modal, np.mean(base_modal), pers, np.mean(base_pers), L[col].nunique()
for col in ("dmf", "refined"):
    m, bm, p, bp, k = metrics(col)
    print(f"{col:8s} etiquetas distintas={k:2d} | etiqueta modal por equipo: observada={m*100:.0f}% vs azar={bm*100:.0f}% | misma etiqueta que el partido anterior: observada={p*100:.0f}% vs azar={bp*100:.0f}%")
print("\ntop D-M-F:", L.dmf.value_counts().head(7).to_dict()); print("top refinada:", L.refined.value_counts().head(8).to_dict())

# ¿la letra de posicion es estable por jugador? (si lo es, el cambio de etiqueta viene de quién juega, no de ruido)
pl = st[st.position != "G"].groupby("player_id").position.agg(["count", lambda s: s.value_counts(normalize=True).iloc[0]]); pl.columns = ["n", "share"]
pl = pl[pl.n >= 10]; print(f"\nletra de posicion por jugador (>=10 titularidades, n={len(pl)}): se mantiene la letra modal en {pl.share.median()*100:.0f}% de sus partidos (mediana); {(pl.share>=.9).mean()*100:.0f}% de los jugadores >=90%")
# cuanta variacion de etiqueta se explica por cambios de once? comparar con partidos consecutivos con el mismo once (>=9 titulares iguales)
same = []; 
for tid, g in st.groupby("team_id"):
    mids = sorted(g.match_id.unique(), key=lambda m: ma.loc[ma.match_id == m, "dt"].iloc[0]); sets = {m: set(g[g.match_id == m].player_id) for m in mids}
    lab = L.set_index("match").dmf
    for a, b in zip(mids[:-1], mids[1:]):
        if len(sets[a] & sets[b]) >= 9 and a in lab.index and b in lab.index: same.append(lab[a] == lab[b])
print(f"partidos consecutivos con >=9 titulares iguales: n={len(same)}; misma etiqueta D-M-F en {np.mean(same)*100:.0f}%")
