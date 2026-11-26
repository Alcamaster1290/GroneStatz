"""Compara mis tablas con las de Wikipedia, fila por fila.
Uso: py -3.11 comparar_tablas.py <carpeta con wikipedia_tablas.txt> [tablas_oficiales.csv]"""
import re
import sys
import unicodedata
from difflib import get_close_matches
from pathlib import Path

import pandas as pd

sp = Path(sys.argv[1])  # carpeta con wikipedia_tablas.txt; aqui se escribe comparacion_tablas.csv
sys.stdout.reconfigure(encoding="utf-8")
mine_path = Path(sys.argv[2]) if len(sys.argv) > 2 else sp / "mis_tablas.csv"
mine = pd.read_csv(mine_path, encoding="utf-8-sig")
if "pj" in mine.columns:  # tablas_oficiales.csv de gronestats.analysis.title_race
    mine = mine.assign(torneo=mine["season"].astype(str) + " " + mine["torneo"]).rename(
        columns={"pos": "Pos", "team": "Equipo", "team_id": "id", "pj": "PJ", "pg": "PG", "pe": "PE", "pp": "PP", "gf": "GF", "gc": "GC", "dg": "DG", "pts": "Pts"}
    )


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", "", text).strip()


ALIAS = {
    "binacional": "deportivo binacional", "academia cantolao": "ad cantolao", "universidad san martin": "deportivo usmp", "cusco": "cusco fc",
    "deportivo moquegua": "cd moquegua", "cajamarca": "fc cajamarca", "alianza universidad": "alianza universidad", "ayacucho": "ayacucho",
    "carlos stein": "fc carlos stein", "carlos a mannucci": "carlos a mannucci", "universidad cesar vallejo": "universidad cesar vallejo",
}
rows = []
current = None
for line in (sp / "wikipedia_tablas.txt").read_text(encoding="utf-8").splitlines():
    if line.startswith("## "):
        current = line[3:]
        continue
    m = re.match(r"^(\d+)\s+(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([+\-−]?\d+)\s+(\d+)$", line)
    assert m, line
    pos, team, pj, pg, pe, pp, gf, gc, dg, pts = m.groups()
    rows.append((current, int(pos), team, int(pj), int(pg), int(pe), int(pp), int(gf), int(gc), int(dg.replace("−", "-")), int(pts)))
wiki = pd.DataFrame(rows, columns=["torneo", "pos_w", "equipo_w", "PJ_w", "PG_w", "PE_w", "PP_w", "GF_w", "GC_w", "DG_w", "Pts_w"])

names = {norm(n): n for n in mine.Equipo.unique()}
mapping, unmatched = {}, []
for w in wiki.equipo_w.unique():
    key = ALIAS.get(norm(w), norm(w))
    if key in names:
        mapping[w] = names[key]
    else:
        close = get_close_matches(key, names.keys(), n=1, cutoff=0.6)
        if close:
            mapping[w] = names[close[0]]
            print(f"  aviso: «{w}» se asoció a «{names[close[0]]}» por semejanza")
        else:
            unmatched.append(w)
if unmatched:
    print("SIN ASOCIAR:", unmatched, "| mis nombres:", sorted(names.values()))
    sys.exit(1)
wiki["Equipo"] = wiki.equipo_w.map(mapping)
merged = wiki.merge(mine, on=["torneo", "Equipo"], how="outer", indicator=True)
print(f"filas Wikipedia {len(wiki)} | filas mías {len(mine)} | solo en una de las dos: {int((merged._merge != 'both').sum())}")
print(merged[merged._merge != "both"][["torneo", "Equipo", "_merge"]].to_string(index=False))

both = merged[merged._merge == "both"].copy()
for col in ("PJ", "PG", "PE", "PP", "GF", "GC", "DG"):
    both[f"d_{col}"] = both[col] - both[f"{col}_w"]
both["d_Pts"] = both["Pts"] - both["Pts_w"]
both["d_pos"] = both["Pos"] - both["pos_w"]
cols = ["d_PJ", "d_PG", "d_PE", "d_PP", "d_GF", "d_GC", "d_DG"]
both["iguales_sin_puntos"] = (both[cols] == 0).all(axis=1)
both["igual_todo"] = both["iguales_sin_puntos"] & (both.d_Pts == 0)
resumen = both.groupby("torneo", sort=False).agg(equipos=("Equipo", "size"), filas_identicas=("igual_todo", "sum"), partidos_y_goles_identicos=("iguales_sin_puntos", "sum"), mismo_puesto=("d_pos", lambda s: int((s == 0).sum())))
print("\n=== resumen por tabla (mías contra Wikipedia) ===")
print(resumen.to_string())
dif = both[~both.igual_todo]
print("\n=== filas que difieren (mías − Wikipedia) ===")
pd.set_option("display.width", 250)
print(dif[["torneo", "Equipo", "d_PJ", "d_PG", "d_PE", "d_PP", "d_GF", "d_GC", "d_DG", "d_Pts", "Pts", "Pts_w", "Pos", "pos_w"]].to_string(index=False))
both.to_csv(sp / "comparacion_tablas.csv", index=False, encoding="utf-8-sig")
