import sys, glob, os, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
base = Path("gronestats/data/Liga 1 Peru/2026")
G = Path("gronestats/images/players")
have_png = {int(p.stem) for p in G.glob("*.png") if p.stem.isdigit()}
have_any = {int(p.stem) for p in G.iterdir() if p.is_file() and p.stem.isdigit()}
rows, bad, nosheet = [], 0, 0
files = sorted(glob.glob(str(base/"raw/details/xlsx/*.xlsx")))
for f in files:
    mid = int(Path(f).stem.split("_")[-1])
    try:
        df = pd.read_excel(f, sheet_name="Player Stats")
    except ValueError:
        nosheet += 1; continue
    except Exception:
        bad += 1; continue
    cols = {c.lower(): c for c in df.columns}
    idc = "id" if "id" in df.columns else cols.get("sofascoreid") or cols.get("id.1")
    mc = cols.get("minutesplayed")
    if idc is None: nosheet += 1; continue
    sub = pd.DataFrame({"pid": pd.to_numeric(df[idc], errors="coerce"),
                        "mp": pd.to_numeric(df[mc], errors="coerce").fillna(0) if mc else 0,
                        "name": df[cols["name"]] if "name" in cols else "",
                        "team": df[cols["teamname"]] if "teamname" in cols else ""})
    sub["match_id"] = mid; rows.append(sub)
print(f"workbooks: {len(files)} | leidos: {len(rows)} | sin hoja Player Stats: {nosheet} | ilegibles: {bad}")
A = pd.concat(rows).dropna(subset=["pid"]); A["pid"] = A.pid.astype(int)
agg = A.groupby("pid").agg(name=("name","last"), team=("team","last"), minutes=("mp","sum"), pj=("match_id","nunique")).reset_index()
agg["png"] = agg.pid.isin(have_png); agg["any"] = agg.pid.isin(have_any)
pl = agg[agg.minutes>0]
print(f"partidos con datos de jugador: {A.match_id.nunique()} | jugadores con minutos: {len(pl)}")
print(f"con PNG: {int(pl.png.sum())}/{len(pl)} = {pl.png.mean()*100:.1f}% | con cualquier formato: {pl['any'].mean()*100:.1f}%")
print(f"ponderado por minutos (PNG): {pl.loc[pl.png,'minutes'].sum()/pl.minutes.sum()*100:.1f}%")
for thr in (450, 900, 1200):
    s = pl[pl.minutes>=thr]; print(f">= {thr} min: {int(s.png.sum())}/{len(s)} = {s.png.mean()*100:.1f}%")
miss = pl[~pl.png].sort_values("minutes", ascending=False)
print(f"\nSin PNG: {len(miss)} jugadores. Top 20 por minutos:")
print(miss.head(20)[["pid","name","team","minutes","pj"]].to_string(index=False))
print("\nMinutos acumulados de los sin foto en el top-250 de minutos:", int(miss[miss.pid.isin(pl.nlargest(250,'minutes').pid)].shape[0]), "jugadores")
by = pl.groupby("team").agg(n=("pid","count"), sin=("png", lambda s: int((~s).sum()))).assign(pct=lambda d: (1-d.sin/d.n)*100).sort_values("pct")
print("\nPeores equipos:"); print(by.head(8).round(1).to_string())
out = Path(os.environ["TEMP"])/"photo_missing_2026.csv"; miss.to_csv(out, index=False, encoding="utf-8-sig"); print("\nCSV de faltantes:", out)
