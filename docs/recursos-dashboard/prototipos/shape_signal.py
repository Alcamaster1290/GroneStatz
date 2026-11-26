import sys, numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
D = "gronestats/data/Liga 1 Peru/2025/dashboard/current"
ap = pd.read_parquet(f"{D}/average_positions.parquet"); st = ap[ap.is_starter==True]
# 1) etiqueta por letras de posicion (D-M-F) de SofaScore
labs, rows = [], []
for (tid, mid), g in st.groupby(["team_id","match_id"]):
    if len(g)!=11: continue
    c = g.position.value_counts()
    labs.append((int(tid), int(mid), f"{c.get('D',0)}-{c.get('M',0)}-{c.get('F',0)}"))
    out = g[g.position!="G"].sort_values("average_x")
    xs, ys = out.average_x.values, out.average_y.values
    rows.append(dict(team=int(tid), match=int(mid),
        def_line=xs[:4].mean(), front=xs[-3:].mean(), depth=xs[-3:].mean()-xs[:4].mean(),
        centroid=xs.mean(), width=(ys.max()-ys.min()), spread_y=ys.std(), 
        compact=np.mean([np.hypot((xs[i]-xs[j])*1.05,(ys[i]-ys[j])*.68) for i in range(10) for j in range(i+1,10)])))
L = pd.DataFrame(labs, columns=["team","match","dmf"])
print("etiquetas D-M-F (liga 2025):", L.dmf.value_counts().head(8).to_dict())
stab = L.groupby("team").dmf.agg(lambda s: s.value_counts(normalize=True).iloc[0])
print("etiqueta modal D-M-F cubre por equipo: mediana=%.0f%% min=%.0f%% max=%.0f%%" % (stab.median()*100, stab.min()*100, stab.max()*100))
# 2) senal de los descriptores de forma: varianza entre equipos / total (ICC aprox.)
S = pd.DataFrame(rows)
print("\ndescriptor        media   desv_total  %varianza_entre_equipos")
for c in ["def_line","front","depth","centroid","width","spread_y","compact"]:
    tot = S[c].var(); mean_t = S.groupby("team")[c].mean(); between = mean_t.var()
    n = S.groupby("team").size().mean(); within = S.groupby("team")[c].var().mean()
    icc = max(0, (between - within/n)) / (max(0,(between - within/n)) + within)
    print(f"{c:12s} {S[c].mean():8.1f} {np.sqrt(tot):10.1f} {icc*100:14.0f}%")
