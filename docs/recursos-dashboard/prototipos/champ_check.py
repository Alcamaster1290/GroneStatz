import sys, numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
base = "gronestats/data/Liga 1 Peru"
IMG = {  # lo que dice la imagen del usuario (puntos del campeón de cada torneo)
 (2022,"Apertura"):("Melgar",41),(2022,"Clausura"):("Alianza Lima",42),(2023,"Apertura"):("Alianza Lima",42),(2023,"Clausura"):("Universitario",39),
 (2024,"Apertura"):("Universitario",40),(2024,"Clausura"):("Universitario",37),(2025,"Apertura"):("Universitario",39),(2025,"Clausura"):("Universitario",40),(2026,"Apertura"):("Alianza Lima",40)}
def table(m):
    h = m.assign(t=m.home_id, gf=m.home_score, ga=m.away_score); a = m.assign(t=m.away_id, gf=m.away_score, ga=m.home_score)
    x = pd.concat([h[["t","gf","ga"]], a[["t","gf","ga"]]]); x["pts"] = np.where(x.gf > x.ga, 3, np.where(x.gf == x.ga, 1, 0))
    return x.groupby("t").agg(pts=("pts","sum"), pj=("pts","size"), gd=("gf", lambda s: 0)).assign(gd=x.assign(d=x.gf-x.ga).groupby("t").d.sum())
print(f"{'temporada':10s}{'torneo':10s}{'campeón (datos)':22s}{'pts datos':>10s}{'PJ':>4s}  {'imagen':24s}{'coincide':>9s}")
for s in (2022,2023,2024,2025,2026):
    m = pd.read_parquet(f"{base}/{s}/dashboard/current/matches.parquet"); te = pd.read_parquet(f"{base}/{s}/dashboard/current/teams.parquet").set_index("team_id").short_name
    for tour in ("Apertura","Clausura"):
        mm = m[m.tournament.astype(str).str.contains(tour) & ~m.tournament.astype(str).str.contains("Final") & m.home_score.notna()]
        if mm.empty: print(f"{s:<10d}{tour:10s}(sin partidos en el bundle)"); continue
        T = table(mm).sort_values(["pts","gd"], ascending=False); top = T.iloc[0]; name = te.get(T.index[0], str(T.index[0]))
        img = IMG.get((s, tour)); ok = "—" if not img else ("sí" if img[1] == top.pts else f"NO ({top.pts - img[1]:+d})")
        print(f"{s:<10d}{tour:10s}{str(name):22s}{int(top.pts):>10d}{int(top.pj):>4d}  {str(img):24s}{ok:>9s}   [partidos en bundle={len(mm)}]")
