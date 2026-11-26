"""Auditoría local (sin red): ¿qué falta de verdad en cada temporada? master -> workbooks crudos -> staging -> bundle publicado."""
import sys, os, zipfile, glob
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
B = Path(r"C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz\gronestats\data\Liga 1 Peru")
MD = Path(r"C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz\gronestats\data\master_data")

def find_master(s):
    for p in (B / str(s) / "raw/master/clean" / f"Partidos_Liga 1 Peru_{s}_limpio.xlsx", MD / f"Partidos_Liga 1 Peru_{s}_limpio.xlsx", B / f"Partidos_Liga 1 Peru_{s}_limpio.xlsx",
              B / str(s) / "raw/master/raw" / f"Partidos_Liga 1 Peru_{s}.xlsx"):
        if p.exists(): return p
    return None

for s in (2022, 2023, 2024, 2025, 2026):
    print(f"\n==================== {s} ====================")
    mp = find_master(s); print("master:", mp.relative_to(B.parent.parent) if mp else "NO EXISTE")
    det_dir = B / str(s) / "raw/details/xlsx"; det_zip = B / str(s) / "raw/details/xlsx.zip"
    n_x = len(list(det_dir.glob("*.xlsx"))) if det_dir.exists() else 0
    n_z = len([n for n in zipfile.ZipFile(det_zip).namelist() if n.endswith(".xlsx")]) if det_zip.exists() else 0
    print(f"workbooks de detalle: sueltos={n_x} | dentro de xlsx.zip={n_z}")
    bundle = pd.read_parquet(B / str(s) / "dashboard/current/matches.parquet")
    print(f"bundle publicado: {len(bundle)} partidos | con fecha: {int(bundle.fecha.notna().sum())} | release: {pd.read_json(B / str(s) / 'dashboard/current/manifest.json', typ='series').get('run_id', '?') if (B / str(s) / 'dashboard/current/manifest.json').exists() else '?'}")
    if mp is None: continue
    m = pd.read_excel(mp)
    cols = {c.lower(): c for c in m.columns}
    idc = next((cols[k] for k in ("match_id", "id", "id_sofascore", "idsofascore", "sofascore_id") if k in cols), None)
    stc = next((cols[k] for k in ("status", "estado") if k in cols), None); tc = next((cols[k] for k in ("tournament", "torneo") if k in cols), None)
    fc = next((cols[k] for k in ("fecha", "date", "start_time", "starttime") if k in cols), None)
    print("columnas clave del master:", dict(id=idc, status=stc, torneo=tc, fecha=fc), "| filas:", len(m))
    if idc is None: print("  columnas:", list(m.columns)[:20]); continue
    m["_id"] = pd.to_numeric(m[idc], errors="coerce")
    fin = m[m[stc].astype(str).str.lower().str.contains("termin|finish|ended|fin")] if stc else m
    print("estados:", m[stc].value_counts().to_dict() if stc else "?", "| terminados:", len(fin), "| con fecha en master:", int(m[fc].notna().sum()) if fc else "sin columna fecha")
    have = set()
    if det_dir.exists(): have |= {int(Path(p).stem.split("_")[-1]) for p in det_dir.glob("*.xlsx")}
    if det_zip.exists(): have |= {int(Path(n).stem.split("_")[-1]) for n in zipfile.ZipFile(det_zip).namelist() if n.endswith(".xlsx")}
    fin_ids = set(fin._id.dropna().astype(int)); falta = fin_ids - have
    print(f"terminados={len(fin_ids)} | con workbook de detalle={len(fin_ids & have)} | SIN workbook={len(falta)} | workbooks sin partido terminado en master={len(have - fin_ids)}")
    if tc and falta:
        t = fin[fin._id.isin(falta)]
        print("   sin detalle por torneo/ronda:", t.groupby(tc).size().to_dict())
    inb = set(bundle.match_id.dropna().astype(int)); print(f"terminados que NO están en el bundle publicado: {len(fin_ids - inb)} | en el bundle pero no terminados: {len(inb - fin_ids)}")
    # staging: cobertura de hojas
    sc = B / str(s) / "staging/sheet_coverage.parquet"
    if sc.exists():
        c = pd.read_parquet(sc); print(f"staging/sheet_coverage: {len(c)} partidos | " + " ".join(f"{k.replace('has_','')}={int(c[k].sum())}" for k in c.columns if k.startswith("has_")))
    # qué ids con workbook faltan en staging (workbook descargado pero no procesado)
    pr = B / str(s) / "staging/player_stats_raw.parquet"
    if pr.exists():
        stg = set(pd.read_parquet(pr, columns=["match_id"]).match_id.dropna().astype(int)); print(f"en staging (player_stats_raw): {len(stg)} partidos | con workbook pero NO procesados: {len(have - stg)}")
