import sys, numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
B = "gronestats/data/Liga 1 Peru"
lv = {}; names = {}
for s in (2022, 2023, 2024, 2025, 2026):
    t = pd.read_parquet(f"{B}/{s}/dashboard/current/teams.parquet")
    for r in t.itertuples():
        names[int(r.team_id)] = str(r.short_name)
        if pd.notna(r.competitiveness_level): lv.setdefault(int(r.team_id), {})[s] = str(r.competitiveness_level)
def played(s):
    m = pd.read_parquet(f"{B}/{s}/dashboard/current/matches.parquet"); m = m[m.tournament.astype(str).str.contains("Apertura|Clausura")]
    return sorted(set(m.home_id.astype(int)) | set(m.away_id.astype(int)), key=lambda t: names[t])
rows = []
for s in (2022, 2023, 2024):
    ids = played(s); falta = [t for t in ids if s not in lv.get(t, {})]
    print(f"\n== {s}: {len(ids)} equipos jugaron Apertura/Clausura | sin nivel ese año: {len(falta)}")
    for t in falta:
        other = lv.get(t, {}); lab = sorted(set(other.values()))
        estado = f"tiene nivel en {sorted(other)} -> {lab[0] if len(lab)==1 else lab}" if other else "NUNCA tiene nivel (solo jugó antes de 2024 o falta en su referencia)"
        print(f"   {names[t]:30s} (id {t})  {estado}")
        rows.append((s, t, names[t], lab[0] if len(lab) == 1 else ("|".join(lab) if lab else "")))
pd.DataFrame(rows, columns=["temporada", "team_id", "equipo", "nivel_en_otras_temporadas"]).to_csv(
    r"C:\Users\Alvaro\AppData\Local\Temp\claude\C--Users-Alvaro\7aa9f7eb-a5d4-4175-a966-e3e7260a7f9a\scratchpad\nivel_faltante.csv", index=False, encoding="utf-8-sig")
