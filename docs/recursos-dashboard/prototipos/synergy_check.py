import sys, itertools, collections, pandas as pd, numpy as np
sys.stdout.reconfigure(encoding="utf-8")
base = "gronestats/data/Liga 1 Peru"
for s in (2025, 2026):
    d = f"{base}/{s}/dashboard/current"
    ap = pd.read_parquet(f"{d}/average_positions.parquet")
    m  = pd.read_parquet(f"{d}/matches.parquet")
    ts = pd.read_parquet(f"{d}/team_stats.parquet")
    print(f"\n########## {s}")
    # --- figura: titulares con posicion media por equipo-partido
    st = ap[ap.is_starter == True]
    per = st.groupby(["match_id","team_id"]).size()
    print(f"equipo-partidos con posiciones: {len(per)} | con exactamente 11 titulares: {(per==11).mean()*100:.1f}% | rango x: {ap.average_x.min():.0f}-{ap.average_x.max():.0f}, y: {ap.average_y.min():.0f}-{ap.average_y.max():.0f}")
    print(f"campos por jugador-partido: position={ap.position.notna().mean()*100:.0f}% x,y={ap.average_x.notna().mean()*100:.0f}% puntos(pointsCount)={ap.points_count.notna().mean()*100:.0f}%")
    # --- sinergia por co-titularidad
    pairs = collections.Counter()
    for (mid, tid), g in st.groupby(["match_id","team_id"]):
        ids = sorted(g.player_id.dropna().astype(int).unique())
        for a, b in itertools.combinations(ids, 2): pairs[(tid, a, b)] += 1
    c = pd.Series(pairs)
    print(f"pares de companeros que alguna vez fueron titulares juntos: {len(c)} | co-titularidades: mediana={c.median():.0f} p90={c.quantile(.9):.0f} max={c.max()}")
    for k in (3, 5, 8, 10):
        print(f"   pares con >= {k:2d} partidos juntos de titulares: {(c>=k).sum():5d} ({(c>=k).mean()*100:4.1f}%)")
    # --- estilo de equipo: claves de team_stats
    allp = ts[ts.PERIOD.astype(str).str.upper().isin(["ALL","1ST","2ND"])] if "PERIOD" in ts else ts
    keys = ts[ts.PERIOD.astype(str).str.upper()=="ALL"].groupby(["GROUP","KEY"]).MATCH_ID.nunique().reset_index().rename(columns={"MATCH_ID":"partidos"})
    print(f"team_stats: {ts.MATCH_ID.nunique()} partidos, {keys.shape[0]} metricas (periodo ALL). Cobertura por metrica (>=90% de partidos):")
    cov = keys[keys.partidos >= 0.9*ts.MATCH_ID.nunique()]
    print("  ", ", ".join(f"{r.KEY}" for r in cov.itertuples())[:900])
    # --- eje temporal
    fm = m[m.status.astype(str).str.lower().isin(["finished","ended","finalizado","ft"])] if "status" in m else m
    print(f"partidos terminados en matches.parquet: {len(fm)} | torneos: {sorted(m.tournament.dropna().unique())[:4]} | rondas: {int(m.round_number.min())}-{int(m.round_number.max())}")
