"""Prototipo de xG propio (regresión logística, solo numpy/scipy) para tiros de la Liga 1 con los datos de SofaScore.
Metodología inspirada en (sin copiar código): soccer_xg (Apache-2.0, ML-KULeuven), expected-goals-thesis (MIT, A. Rowlinson), xGils (MIT, C. Gilson):
variables geométricas (distancia y ángulo a portería), parte del cuerpo y situación de juego, calibración y validación por temporada.
Validación cruzada dejando UNA TEMPORADA FUERA (cada temporada se predice con un modelo que no la vio)."""
import sys, ast, json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import rankdata

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(r"C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz"); B = REPO / "gronestats/data/Liga 1 Peru"; OUT = Path(__file__).parent
SEASONS = (2022, 2023, 2024, 2025, 2026)
SIT = ["regular", "corner", "set-piece", "free-kick", "fast-break", "throw-in-set-piece"]          # base: 'assisted'


def parse_obj(v):
    """Lee los valores anidados del formato nuevo de SofaScore (texto tipo {'x': 28.5, ...}); sirve para JSON y para literales de Python."""
    if isinstance(v, dict): return v
    if v is None or (isinstance(v, float) and np.isnan(v)): return {}
    for fn in (json.loads, ast.literal_eval):
        try:
            d = fn(str(v))
            if isinstance(d, dict): return d
        except Exception:
            pass
    return {}


def load():
    frames = []
    for s in SEASONS:
        cur = pd.read_parquet(B / str(s) / "dashboard/current/shot_events.parquet")
        stg = pd.read_parquet(B / str(s) / "staging/shotmap_raw.parquet")
        sx = pd.to_numeric(stg["x"], errors="coerce") if "x" in stg else pd.Series(np.nan, index=stg.index)
        sy = pd.to_numeric(stg["y"], errors="coerce") if "y" in stg else pd.Series(np.nan, index=stg.index)
        if "playerCoordinates" in stg:
            xy = stg["playerCoordinates"].map(parse_obj); sx = sx.fillna(xy.map(lambda d: d.get("x", np.nan))); sy = sy.fillna(xy.map(lambda d: d.get("y", np.nan)))
        pid = pd.to_numeric(stg["id.1"], errors="coerce") if "id.1" in stg else pd.Series(np.nan, index=stg.index)
        pname = pd.Series(pd.NA, index=stg.index, dtype="object"); ppos = pd.Series(pd.NA, index=stg.index, dtype="object")
        if "player" in stg:                                                      # formato nuevo: el jugador viene en un diccionario anidado
            po = stg["player"].map(parse_obj); pid = pid.fillna(pd.to_numeric(po.map(lambda d: d.get("id", np.nan)), errors="coerce"))
            pname = po.map(lambda d: d.get("name")); ppos = po.map(lambda d: d.get("position"))
        if "id_1" in stg: pid = pid.fillna(pd.to_numeric(stg["id_1"], errors="coerce"))        # variante de nombre de columna en algunos workbooks de 2025
        if "name" in stg: pname = pname.where(pname.notna(), stg["name"])
        if "position" in stg: ppos = ppos.where(ppos.notna(), stg["position"])
        stg = pd.DataFrame({"match_id": stg.match_id.astype(int), "shot_id": pd.to_numeric(stg["id"], errors="coerce"), "sx": sx, "sy": sy, "pid": pid, "pname": pname, "ppos": ppos}).drop_duplicates(["match_id", "shot_id"])
        cur = cur.drop(columns=["x", "y"]).merge(stg, on=["match_id", "shot_id"], how="left").rename(columns={"sx": "x", "sy": "y"})
        cur["player_src"] = np.where(cur.player_id.notna(), "parquet curado", np.where(cur.pid.notna(), "formato anidado", "sin dato"))
        cur["player_id"] = cur.player_id.fillna(cur.pid).astype("Int64"); cur["name"] = cur.name.astype("object").where(cur.name.notna(), cur.pname); cur["position"] = cur.position.astype("object").where(cur.position.notna(), cur.ppos)
        cur["season"] = s; frames.append(cur.drop(columns=["pid", "pname", "ppos"]))
    return pd.concat(frames, ignore_index=True)


GOAL_HALF_M = (55.8 - 44.2) / 2 * 0.68                                           # poste a poste en el sistema Opta de tu cancha (VerticalPitch 'opta'): y de 44,2 a 55,8


def geometry(df):
    """x = distancia a la línea de fondo del arco ATACADO (misma convención para local y visita: verificado). y = ancho. Escalas de la cancha Opta 105 x 68 m."""
    dx = df.x.values * 1.05; dy = (df.y.values - 50) * 0.68
    dist = np.hypot(dx, dy); ang = np.arctan2(2 * GOAL_HALF_M * dx, dx ** 2 + dy ** 2 - GOAL_HALF_M ** 2); ang = np.where(ang < 0, ang + np.pi, ang)
    return dist, ang


def features(df, stats=None):
    dist, ang = geometry(df); head = (df.body_part == "head").fillna(False).astype(float).values; other = (df.body_part == "other").fillna(False).astype(float).values
    ld = np.log(np.maximum(dist, .5)); cols = {"dist": dist, "log_dist": ld, "dist2": dist ** 2, "angle": ang, "head": head, "head_x_logd": head * ld, "otro_cuerpo": other}
    for s in SIT: cols["sit_" + s] = (df.situation == s).fillna(False).astype(float).values
    cols["fk_x_logd"] = cols["sit_free-kick"] * ld
    X = pd.DataFrame(cols, index=df.index)
    if stats is None: stats = (X.mean(), X.std().replace(0, 1))
    return (X - stats[0]) / stats[1], stats


def fit(X, y, l2=1.0):
    A = np.c_[np.ones(len(X)), X.values]
    def f(b):
        z = A @ b; p = 1 / (1 + np.exp(-z)); loss = np.sum(np.logaddexp(0, z) - y * z) + .5 * l2 * np.sum(b[1:] ** 2)
        return loss, A.T @ (p - y) + l2 * np.r_[0, b[1:]]
    return minimize(f, np.zeros(A.shape[1]), jac=True, method="L-BFGS-B").x


def predict(X, b): return 1 / (1 + np.exp(-(np.c_[np.ones(len(X)), X.values] @ b)))
def logloss(y, p): p = np.clip(p, 1e-6, 1 - 1e-6); return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
def auc(y, p): r = rankdata(p); n1 = y.sum(); n0 = len(y) - n1; return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


S = load()
eq = lambda col, val: (col == val).fillna(False).astype(bool)             # las columnas de texto traen <NA>: sin esto el filtro descarta todo lo que no sea gol
S["is_goal"] = eq(S.shot_type, "goal").astype(int); S["is_pen"] = eq(S.situation, "penalty"); S["is_own"] = eq(S.goal_type, "own"); S["is_so"] = eq(S.situation, "shootout")
S["has_xy"] = S.x.notna() & S.y.notna()
print("TIROS:", S.groupby("season").size().to_dict(), "| con coordenadas (tras leer playerCoordinates):", (S.groupby("season").has_xy.mean() * 100).round(1).to_dict())
print("penales:", int(S.is_pen.sum()), "| autogoles:", int(S.is_own.sum()), "| tanda:", int(S.is_so.sum()))
print("\n=== VERIFICACIONES con datos y código locales ===")
print("jugador del tiro (origen):", S.groupby(["season", "player_src"]).size().unstack(fill_value=0).to_dict("index"))
# (a) los jugadores recuperados existen en las estadísticas de ese partido y pertenecen al equipo que tira (is_home)
chk = []
for s in SEASONS:
    ps = pd.read_parquet(B / str(s) / "staging/player_stats_raw.parquet")                    # el id del jugador viene en 'id', 'sofascoreId' o 'sofascoreid' según el workbook
    ps["id"] = pd.to_numeric(ps["id"], errors="coerce")
    for alt in ("sofascoreId", "sofascoreid"):
        if alt in ps: ps["id"] = ps["id"].fillna(pd.to_numeric(ps[alt], errors="coerce"))
    ps["teamId"] = pd.to_numeric(ps["teamId"], errors="coerce")
    if "teamid" in ps: ps["teamId"] = ps["teamId"].fillna(pd.to_numeric(ps["teamid"], errors="coerce"))
    ps = ps[["match_id", "id", "teamId"]].dropna(subset=["id"]); ps["id"] = ps["id"].astype(int)
    mt = pd.read_parquet(B / str(s) / "dashboard/current/matches.parquet")[["match_id", "home_id", "away_id"]]
    t = S[(S.season == s) & S.player_id.notna() & ~S.is_own].merge(mt, on="match_id", how="left"); t["tid"] = np.where(t.is_home.astype(bool), t.home_id, t.away_id)
    t = t.merge(ps.drop_duplicates(["match_id", "id"]).rename(columns={"id": "player_id", "teamId": "ps_team"}), on=["match_id", "player_id"], how="left")
    chk.append(dict(temporada=s, tiros_con_jugador=len(t), jugador_en_estadisticas_del_partido=float(t.ps_team.notna().mean()), equipo_coincide=float((t.ps_team.astype(float) == t.tid.astype(float))[t.ps_team.notna()].mean())))
print(pd.DataFrame(chk).set_index("temporada").round(4).to_string())
# (b) goles en el mapa de tiros vs marcador (partidos sin autogoles): valida que is_home y la lista de tiros están completos
sc = pd.concat([pd.read_parquet(B / str(s) / "dashboard/current/matches.parquet")[["match_id", "home_score", "away_score"]].assign(season=s) for s in SEASONS])
gl = S[S.is_goal.astype(bool) & ~S.is_own].groupby(["match_id", "is_home"]).size().unstack(fill_value=0).rename(columns={True: "g_local", False: "g_visita"}).reset_index()
own = S[S.is_own].groupby("match_id").size().rename("autogoles")
j = sc.merge(gl, on="match_id", how="left").fillna({"g_local": 0, "g_visita": 0}).merge(own, on="match_id", how="left").fillna({"autogoles": 0})
sin_au = j[j.autogoles == 0]; ok_m = ((sin_au.g_local == sin_au.home_score) & (sin_au.g_visita == sin_au.away_score))
print(f"goles del mapa de tiros = marcador (partidos sin autogoles): {int(ok_m.sum())} de {len(sin_au)} ({ok_m.mean()*100:.1f} %)")
print("   por temporada:", (sin_au.assign(ok=ok_m).groupby("season").ok.mean() * 100).round(1).to_dict())

ok = S[~S.is_pen & ~S.is_own & ~S.is_so & S.has_xy]
xg = pd.Series(np.nan, index=S.index); src = pd.Series("", index=S.index)
rows = []
for s in SEASONS:
    tr = ok[ok.season != s]; te = S[(S.season == s)]
    Xtr, st = features(tr); b = fit(Xtr, tr.is_goal.values)
    pen_rate = float(S[(S.season != s) & S.is_pen].is_goal.mean())
    sit_rate = tr.groupby("situation").is_goal.mean()
    m_ok = (te.index.isin(ok.index))
    Xte, _ = features(te[m_ok], st); xg.loc[te[m_ok].index] = predict(Xte, b); src.loc[te[m_ok].index] = "modelo"
    xg.loc[te[te.is_pen].index] = pen_rate; src.loc[te[te.is_pen].index] = "penal (constante)"
    xg.loc[te[te.is_own].index] = 0.0; src.loc[te[te.is_own].index] = "autogol (0)"
    m_nx = ~te.has_xy & ~te.is_pen & ~te.is_own & ~te.is_so
    xg.loc[te[m_nx].index] = te[m_nx].situation.map(sit_rate).fillna(tr.is_goal.mean()); src.loc[te[m_nx].index] = "sin coordenadas (media por situación)"
    # métricas fuera de muestra (solo tiros del modelo)
    y = te[m_ok].is_goal.values; p = xg.loc[te[m_ok].index].values
    base = float(tr.is_goal.mean()); Xd = Xtr[["dist", "log_dist"]]; bd = fit(Xd, tr.is_goal.values); pd_ = predict(((te[m_ok].pipe(lambda d: features(d, st)[0])[["dist", "log_dist"]])), bd)
    rows.append(dict(temporada=s, tiros_modelo=len(y), log_loss_modelo=logloss(y, p), log_loss_solo_distancia=logloss(y, pd_), log_loss_constante=logloss(y, np.full(len(y), base)), auc=auc(y, p), brier=float(np.mean((p - y) ** 2)),
                     xG_total=float(p.sum()), goles=int(y.sum())))
M = pd.DataFrame(rows).set_index("temporada"); print("\n=== VALIDACIÓN dejando una temporada fuera ==="); print(M.round(4).to_string())
S["xg"] = xg; S["xg_source"] = src
# coeficientes (modelo con todas las temporadas, variables estandarizadas)
Xa, sta = features(ok); ba = fit(Xa, ok.is_goal.values); print("\ncoeficientes (estandarizados; + sube el xG):", dict(zip(["const"] + list(Xa.columns), ba.round(2))))
# calibración por deciles (todos los tiros del modelo, predichos fuera de muestra)
mm = S[S.xg_source == "modelo"].copy(); mm["dec"] = pd.qcut(mm.xg.rank(method="first"), 10, labels=False)
cal = mm.groupby("dec").agg(xg_medio=("xg", "mean"), tasa_gol=("is_goal", "mean"), n=("xg", "size")); print("\n=== calibración por deciles de xG (fuera de muestra) ==="); print(cal.round(3).to_string())

# ---- validación contra el xG de EQUIPO del proveedor (suma de xG de tiros por equipo y partido) ----
res = []
for s in SEASONS:
    ts = pd.read_parquet(B / str(s) / "dashboard/current/team_stats.parquet"); ts = ts[(ts.KEY == "expectedGoals") & (ts.PERIOD.astype(str).str.upper() == "ALL")].drop_duplicates("MATCH_ID")
    mine = S[S.season == s].groupby(["match_id", "is_home"]).xg.sum().unstack(); mine.columns = ["xg_visita", "xg_local"]
    j = ts.set_index("MATCH_ID")[["HOMEVALUE", "AWAYVALUE"]].join(mine, how="inner").dropna()
    a = np.r_[j.HOMEVALUE.values, j.AWAYVALUE.values]; b_ = np.r_[j.xg_local.values, j.xg_visita.values]
    res.append(dict(temporada=s, equipo_partidos=len(a), correlacion=float(np.corrcoef(a, b_)[0, 1]), proveedor_medio=float(a.mean()), propio_medio=float(b_.mean()), ratio=float(b_.sum() / a.sum()), MAE=float(np.mean(np.abs(a - b_)))))
print("\n=== CONTRA EL xG DE EQUIPO DEL PROVEEDOR (por equipo y partido) ==="); print(pd.DataFrame(res).set_index("temporada").round(3).to_string())

# ---- tablas por jugador ----
S["player_id"] = S.player_id.astype("Int64")
per_match = S[~S.is_so].groupby(["season", "match_id", "player_id", "name", "team_name"], dropna=False).agg(tiros=("xg", "size"), xG=("xg", "sum"), goles=("is_goal", "sum")).reset_index()
per_match["goles_menos_xG"] = per_match.goles - per_match.xG
per_season = S[~S.is_so].groupby(["season", "player_id", "name", "team_name"], dropna=False).agg(partidos=("match_id", "nunique"), tiros=("xg", "size"), xG=("xg", "sum"), goles=("is_goal", "sum"),
                                                                                              xG_sin_penales=("xg", lambda v: v[~S.loc[v.index, "is_pen"]].sum())).reset_index()
per_season["xG_por_tiro"] = per_season.xG / per_season.tiros; per_season["goles_menos_xG"] = per_season.goles - per_season.xG
per_match.round(4).to_csv(OUT / "xg_jugador_partido.csv", index=False, encoding="utf-8-sig"); per_season.round(4).to_csv(OUT / "xg_jugador_temporada.csv", index=False, encoding="utf-8-sig")
S[["season", "match_id", "shot_id", "player_id", "name", "team_id", "team_name", "is_home", "shot_type", "situation", "body_part", "minute" if "minute" in S else "time", "x", "y", "is_goal", "xg", "xg_source"]].to_parquet(OUT / "xg_tiros.parquet", index=False)
t = per_season[(per_season.season == 2025) & (per_season.tiros >= 25)]
print("\n=== 2025: más xG (≥25 tiros) ==="); print(t.sort_values("xG", ascending=False).head(8)[["name", "team_name", "tiros", "xG", "goles", "goles_menos_xG"]].round(2).to_string(index=False))
print("\n=== 2025: más por encima de su xG ==="); print(t.sort_values("goles_menos_xG", ascending=False).head(5)[["name", "team_name", "tiros", "xG", "goles", "goles_menos_xG"]].round(2).to_string(index=False))
print("\nfuentes de xG:", S.xg_source.value_counts().to_dict()); print("archivos:", [p.name for p in OUT.glob("xg_*")])
