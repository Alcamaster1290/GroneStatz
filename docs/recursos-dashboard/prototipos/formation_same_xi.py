import sys, numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
D = "gronestats/data/Liga 1 Peru/2025/dashboard/current"
ap = pd.read_parquet(f"{D}/average_positions.parquet"); st = ap[ap.is_starter == True]
ma = pd.read_parquet(f"{D}/matches.parquet"); ma["dt"] = pd.to_datetime(ma.fecha, format="%d/%m/%Y %H:%M", errors="coerce"); dt = ma.set_index("match_id").dt
def lab(g):
    c = g.position.value_counts(); return f"{c.get('D',0)}-{c.get('M',0)}-{c.get('F',0)}"
res = {"mismo_once(>=10 iguales)": [], "casi_igual(9)": [], "once distinto(<=8)": []}
for tid, g in st.groupby("team_id"):
    ms = sorted(g.match_id.unique(), key=lambda m: dt[m]); info = {}
    for m in ms:
        x = g[g.match_id == m]
        if len(x) == 11: info[m] = (set(x.player_id), lab(x))
    ks = [m for m in ms if m in info]
    for a, b in zip(ks[:-1], ks[1:]):
        k = len(info[a][0] & info[b][0]); same = info[a][1] == info[b][1]
        res["mismo_once(>=10 iguales)" if k >= 10 else "casi_igual(9)" if k == 9 else "once distinto(<=8)"].append(same)
for k, v in res.items(): print(f"{k:28s} n={len(v):3d}  misma etiqueta D-M-F: {np.mean(v)*100:.0f}%" if v else f"{k}: n=0")
