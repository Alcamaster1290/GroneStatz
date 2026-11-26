"""Mockups v2 con datos reales 2025: (1) Compañeros fusionando A+B, (2) Estilo del equipo y su evolución.
Material de diseño desechable (scratchpad). Interacciones solo con CSS (:has), sin JS salvo stopPropagation inline."""
import sys, io, base64, html, math, re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from PIL import Image
from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(r"C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz")
SCREEN = REPO / ".superpowers/brainstorm/431-1795646387/content"
D = REPO / "gronestats/data/Liga 1 Peru/2025/dashboard/current"
IMG = REPO / "gronestats/images/players"
TEAM, PID, K = 306660, 846742, 8          # Alianza Universidad, Marcos Lliuya, contracción
GREEN, RED, AMBER = "#34c759", "#ff3b30", "#f5b301"

ap = pd.read_parquet(D / "average_positions.parquet")
ma = pd.read_parquet(D / "matches.parquet")
ts = pd.read_parquet(D / "team_stats.parquet")
pl = pd.read_parquet(D / "player_identity.parquet").drop_duplicates("player_id").set_index("player_id")
pt = pd.read_parquet(D / "player_totals_full_season.parquet").drop_duplicates("player_id").set_index("player_id")
te = pd.read_parquet(D / "teams.parquet").set_index("team_id")
team_name = te.loc[TEAM, "short_name"]
ALL = ts[ts.PERIOD.astype(str).str.upper() == "ALL"].drop_duplicates(["MATCH_ID", "KEY"])
TSI = ALL.set_index(["MATCH_ID", "KEY"])


def tsv(mid, key, side, total=False):
    try:
        r = TSI.loc[(mid, key)]
    except KeyError:
        return np.nan
    v = r[("HOME" if side == "h" else "AWAY") + ("TOTAL" if total else "VALUE")]
    return float(v) if pd.notna(v) else np.nan


# ---------- partidos del equipo, por fecha
tm = ma[(ma.home_id == TEAM) | (ma.away_id == TEAM)].copy()
tm["dt"] = pd.to_datetime(tm.fecha, format="%d/%m/%Y %H:%M", errors="coerce")
tm = tm.sort_values("dt").reset_index(drop=True)
M = []
for r in tm.itertuples():
    mid, home = int(r.match_id), r.home_id == TEAM
    side, opp = ("h", "a") if home else ("a", "h")
    gf, ga = (r.home_score, r.away_score) if home else (r.away_score, r.home_score)
    M.append(dict(mid=mid, dt=r.dt, tour=str(r.tournament), rnd=int(r.round_number), home=home, gf=int(gf), ga=int(ga),
                  rival=str(te.loc[r.away_id if home else r.home_id, "short_name"]), side=side, opp=opp))
st = ap[(ap.team_id == TEAM) & (ap.is_starter == True)]
SP = {}
for mid, g in st.groupby("match_id"):
    SP[int(mid)] = [dict(pid=int(x.player_id), x=float(x.average_x), y=float(x.average_y), pos=str(x.position),
                         dor=(int(x.shirt_number) if pd.notna(x.shirt_number) else None)) for x in g.itertuples()]
M = [m for m in M if m["mid"] in SP and len(SP[m["mid"]]) == 11]
S = {m["mid"]: {p["pid"]: (p["x"], p["y"]) for p in SP[m["mid"]]} for m in M}
gd = {m["mid"]: m["gf"] - m["ga"] for m in M}
xg_for = {m["mid"]: tsv(m["mid"], "expectedGoals", m["side"]) for m in M}
xg_ag = {m["mid"]: tsv(m["mid"], "expectedGoals", m["opp"]) for m in M}
xgd = {k: xg_for[k] - xg_ag[k] for k in xg_for if not (np.isnan(xg_for[k]) or np.isnan(xg_ag[k]))}
mids = [m["mid"] for m in M if m["mid"] in xgd]
cnt = Counter(p for m in M for p in S[m["mid"]])
XI = [p for p, _ in cnt.most_common(11)]
if PID not in XI:
    XI = [PID] + XI[:10]
typ = {p: tuple(np.mean([S[m["mid"]][p] for m in M if p in S[m["mid"]]], axis=0)) for p in XI}
dorsal = {}
for p in XI:
    c = Counter(d["dor"] for mm in M for d in SP[mm["mid"]] if d["pid"] == p and d["dor"] is not None)
    dorsal[p] = c.most_common(1)[0][0] if c else None
print(f"{team_name}: {len(M)} partidos, con xG={len(mids)}; XI={[(pl.loc[p,'short_name'], dorsal[p], cnt[p]) for p in XI]}")


def name(p): return str(pl.loc[p, "short_name"]) if p in pl.index else str(p)
def full(p): return str(pl.loc[p, "name"]) if p in pl.index else str(p)
def dor(p): return str(dorsal[p]) if dorsal.get(p) is not None else "–"


# ---------- pares: dos medidas (xGD y diferencia de goles), contraídas por la muestra más chica
def pair(a, b):
    both = [m for m in mids if a in S[m] and b in S[m]]
    rest = [m for m in mids if m not in both]
    n, nr = len(both), len(rest)
    if n < 3 or nr < 3:
        return None
    n_eff = min(n, nr)
    f = n_eff / (n_eff + K)
    out = dict(n=n, nr=nr, conf=(1 if n_eff < 5 else 2 if n_eff < 8 else 3 if n_eff < 15 else 4),
               dist=float(np.mean([math.hypot((S[m][b][0] - S[m][a][0]) * 1.05, (S[m][b][1] - S[m][a][1]) * .68) for m in both])))
    for key, src in (("xg", xgd), ("gl", gd)):
        vb, vr = np.mean([src[m] for m in both]), np.mean([src[m] for m in rest])
        out[key] = dict(both=float(vb), rest=float(vr), raw=float(vb - vr), s=float((vb - vr) * f))
    out["gf"] = float(np.mean([next(x for x in M if x["mid"] == m)["gf"] for m in both]))
    out["ga"] = float(np.mean([next(x for x in M if x["mid"] == m)["ga"] for m in both]))
    return out


PR = {}
for a in XI:
    for b in XI:
        if a < b:
            r = pair(a, b)
            if r and r["n"] >= 5:
                PR[(a, b)] = PR[(b, a)] = r
mx = {k: max(abs(r[k]["s"]) for r in PR.values()) or 1 for k in ("xg", "gl")}
print("pares con >=5 PJ juntos:", len(PR) // 2, "| max |s| xg=%.2f gl=%.2f" % (mx["xg"], mx["gl"]))

# ---------- fotos
_uri = {}
def avatar_uri(p):
    if p in _uri: return _uri[p]
    f, uri = IMG / f"{p}.png", None
    if f.exists():
        im = Image.open(f).convert("RGBA"); w, h = im.size; s = min(w, h)
        im = im.crop(((w - s) // 2, 0, (w - s) // 2 + s, s)).resize((72, 72), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "PNG", optimize=True); uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    _uri[p] = uri; return uri
def initials(p):
    parts = name(p).replace(".", "").split(); return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
def photo(p, px):
    u = avatar_uri(p)
    if u: return f'<img src="{u}" width="{px}" height="{px}" style="border-radius:50%;object-fit:cover;background:var(--bg-tertiary);flex:none" alt="">'
    return (f'<span style="width:{px}px;height:{px}px;border-radius:50%;background:var(--bg-tertiary);color:var(--text-secondary);display:inline-flex;'
            f'align-items:center;justify-content:center;font-size:{px*.38:.0f}px;font-weight:600;flex:none">{initials(p)}</span>')
def chip(p, px=22):
    return (f'<span class="mk-dor" style="width:{px}px;height:{px}px;font-size:{px*.5:.0f}px">{dor(p)}</span>')


# ---------- cancha vertical (ataque arriba)
def to_svg(x, y): return y * .68, 105 - x * 1.05
def pitch_lines():
    ln = 'fill="none" stroke="var(--text-tertiary)" stroke-width=".35"'
    return ('<rect x="0" y="0" width="68" height="105" rx="1.2" fill="var(--bg-tertiary)" fill-opacity=".45" stroke="var(--text-tertiary)" stroke-width=".4"/>'
            f'<line x1="0" y1="52.5" x2="68" y2="52.5" {ln}/><circle cx="34" cy="52.5" r="9.15" {ln}/>'
            f'<rect x="13.84" y="0" width="40.32" height="16.5" {ln}/><rect x="24.84" y="0" width="18.32" height="5.5" {ln}/>'
            f'<rect x="13.84" y="88.5" width="40.32" height="16.5" {ln}/><rect x="24.84" y="99.5" width="18.32" height="5.5" {ln}/>')
def node(cx, cy, label, ring, r=3.5, ring_w=.7, fill="var(--bg-secondary)"):
    return (f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r}" fill="{fill}" stroke="{ring}" stroke-width="{ring_w}"/>'
            f'<text x="{cx:.2f}" y="{cy + r*.36:.2f}" font-size="{r*.95:.1f}" text-anchor="middle" font-weight="700" fill="var(--text-primary)">{label}</text>')


# =====================================================================================
# PARTE 1 · COMPAÑEROS (A+B fusionadas): red con dorsales + panel de detalle al pasar el mouse
# =====================================================================================
edges, nodes, panels, dyn = [], [], [], []
conf_dots = lambda c: "●" * c + f'<span style="opacity:.25">{"●" * (4 - c)}</span>'
for (a, b), r in sorted(PR.items()):
    if a > b: continue
    (ax, ay), (bx, by) = to_svg(*typ[a]), to_svg(*typ[b])
    for key in ("xg", "gl"):
        s = r[key]["s"]; w = .35 + 2.6 * abs(s) / mx[key]; col = GREEN if s >= 0 else RED
        op = .4 + .15 * r["conf"]; dash = "" if r["conf"] >= 3 else ' stroke-dasharray="1.2 1"'
        foc = " f" if PID in (a, b) else ""
        edges.append(f'<line class="edge m-{key} e-{a} e-{b}{foc}" style="--op:{op:.2f}" x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" '
                     f'stroke="{col}" stroke-width="{w:.2f}" stroke-linecap="round"{dash}/>')
for p in XI:
    cx, cy = to_svg(*typ[p]); is_p = p == PID
    pr = PR.get((PID, p)); ring = "var(--accent)" if is_p else (GREEN if pr and pr["xg"]["s"] >= 0 else RED if pr else "var(--text-tertiary)")
    g = int(pt.loc[p, "goals"]) if p in pt.index else 0
    badge = (f'<circle cx="{cx+3.4:.2f}" cy="{cy-3.4:.2f}" r="2.1" fill="{AMBER}" stroke="var(--bg-secondary)" stroke-width=".4"/>'
             f'<text x="{cx+3.4:.2f}" y="{cy-2.55:.2f}" font-size="2.4" text-anchor="middle" font-weight="800" fill="#1d1d1f">{g}</text>') if g > 0 else ""
    nodes.append(f'<g class="node n-{p}" tabindex="0"><circle cx="{cx:.2f}" cy="{cy:.2f}" r="5.2" fill="transparent"/>'
                 + node(cx, cy, dor(p), ring, 3.6, 1.1 if is_p else .8) + badge
                 + f'<text x="{cx:.2f}" y="{cy+6.9:.2f}" font-size="2.4" text-anchor="middle" font-weight="{700 if is_p else 500}" fill="var(--text-primary)" '
                   f'paint-order="stroke" stroke="var(--bg-secondary)" stroke-width=".7">{html.escape(name(p))}</text></g>')
svg_net = (f'<svg viewBox="-1 -1 70 107" width="340" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Red de sinergia del once habitual">'
           + pitch_lines() + "".join(edges) + "".join(nodes) + "</svg>")

for q in XI:
    tot = pt.loc[q] if q in pt.index else None
    g_, a_, mn = (int(tot.goals), int(tot.assists), int(tot.minutesplayed)) if tot is not None else (0, 0, 0)
    rows = []
    others = sorted([o for o in XI if o != q and (q, o) in PR], key=lambda o: -PR[(q, o)]["xg"]["s"])
    for o in others[:8]:
        r = PR[(q, o)]
        cells = ""
        for key, unit in (("xg", "xGD"), ("gl", "GD")):
            s = r[key]["s"]; wpx = 52 * abs(s) / mx[key]
            cells += (f'<span class="m-{key} mk-bar"><i style="{"left:50%" if s >= 0 else "right:50%"};width:{wpx:.0f}px;background:{GREEN if s >= 0 else RED}"></i></span>'
                      f'<b class="m-{key}" style="width:42px;text-align:right;color:{GREEN if s >= 0 else RED}">{s:+.2f}</b>')
        rows.append(f'<div class="mk-li">{chip(o, 24)}<div style="flex:1;min-width:0;line-height:1.15"><b>{html.escape(name(o))}</b><br>'
                    f'<span class="mk-dim">{r["n"]} PJ juntos · GF {r["gf"]:.1f}–GC {r["ga"]:.1f} · {r["dist"]:.0f} m</span></div>{cells}'
                    f'<span class="mk-conf">{conf_dots(r["conf"])}</span></div>')
    if not rows:
        rows = ['<div class="mk-dim" style="padding:.6rem 0">Muestra insuficiente: menos de 5 partidos de titulares juntos con sus compañeros.</div>']
    foc = " f" if q == PID else ""
    panels.append(f'''<div class="panel p-{q}{foc}">
  <div style="display:flex;gap:.75rem;align-items:center">{photo(q, 56)}<div style="line-height:1.2"><b style="font-size:1rem">{html.escape(full(q))}</b><br>
    <span class="mk-dim">#{dor(q)} · {html.escape(str(pl.loc[q, 'position']) if q in pl.index else '')} · {cnt[q]} titularidades · {mn:,} min</span></div></div>
  <div class="mk-stats"><div><b style="color:{AMBER}">{g_}</b><span>goles</span></div><div><b>{a_}</b><span>asistencias</span></div><div><b>{cnt[q]}</b><span>titular</span></div></div>
  <div class="mk-label" style="margin:.6rem 0 .2rem">Conexiones <span style="text-transform:none;letter-spacing:0">· mayor a menor sinergia</span></div>{"".join(rows)}</div>''')

goals_rows = []
gmax = max((int(pt.loc[p, "goals"]) if p in pt.index else 0) for p in XI) or 1
for p in sorted(XI, key=lambda p: -(int(pt.loc[p, "goals"]) if p in pt.index else 0)):
    g = int(pt.loc[p, "goals"]) if p in pt.index else 0
    goals_rows.append(f'<div class="mk-gr">{chip(p, 20)}<span style="width:78px">{html.escape(name(p))}</span>'
                      f'<i style="width:{140 * g / gmax:.0f}px;background:{AMBER}"></i><b>{g}</b></div>')

for q in XI:
    dyn.append(f".net:has(.n-{q}:hover) .e-{q},.net:has(.n-{q}:focus) .e-{q}{{opacity:var(--op)}}"
               f".net:has(.n-{q}:hover) .p-{q},.net:has(.n-{q}:focus) .p-{q}{{display:block}}")

part1 = f'''
<div class="net">
  <input type="radio" name="ms" id="ms-xg" checked class="mk-hide"><input type="radio" name="ms" id="ms-gl" class="mk-hide">
  <div class="mk-chips"><span style="border:0;padding-left:0">Medida de la conexión:</span><label for="ms-xg">xGD (calidad de ocasiones)</label><label for="ms-gl">Goles (diferencia GF–GC)</label>
    <span style="margin-left:auto;border:0">Pasa el mouse sobre un dorsal</span></div>
  <div class="mk-row" style="align-items:flex-start">
    <div>{svg_net}
      <div class="mk-legend" style="max-width:340px"><span style="color:{GREEN}">━</span> rinde mejor juntos · <span style="color:{RED}">━</span> peor · <span>┅</span> muestra baja · grosor = fuerza · <span style="color:{AMBER}">●</span> goles de la temporada</div></div>
    <div style="flex:1;min-width:300px">{"".join(panels)}
      <div class="mk-label" style="margin:1rem 0 .3rem">Goles del once habitual · 2025</div>{"".join(goals_rows)}</div>
  </div>
</div>'''

# =====================================================================================
# PARTE 2 · ESTILO DEL EQUIPO Y SU EVOLUCIÓN
# =====================================================================================
def shape(mid):
    out = sorted([d for d in SP[mid] if d["pos"] != "G"], key=lambda d: d["x"])
    xs, ys = np.array([d["x"] for d in out]), np.array([d["y"] for d in out])
    comp = np.mean([math.hypot((xs[i]-xs[j])*1.05, (ys[i]-ys[j])*.68) for i in range(len(xs)) for j in range(i+1, len(xs))])
    return dict(defl=float(xs[:4].mean()*1.05), front=float(xs[-3:].mean()*1.05), width=float((ys.max()-ys.min())*.68), comp=float(comp))
for m in M:
    sh = shape(m["mid"]); m.update(sh)
    ps = tsv(m["mid"], "passes", m["side"])
    m["poss"] = tsv(m["mid"], "ballPossession", m["side"])
    m["pacc"] = tsv(m["mid"], "accuratePasses", m["side"]) / ps * 100 if ps else np.nan
    m["long"] = tsv(m["mid"], "accurateLongBalls", m["side"], total=True) / ps * 100 if ps else np.nan
    m["f3"] = tsv(m["mid"], "finalThirdEntries", m["side"])
    m["xgf"], m["xga"] = xg_for[m["mid"]], xg_ag[m["mid"]]
    m["res"] = "G" if m["gf"] > m["ga"] else "E" if m["gf"] == m["ga"] else "P"
N = len(M)

# referencia de liga (todos los equipos, todos los partidos 2025)
stl = ap[ap.is_starter == True]; lg_def, lg_front, lg_w, lg_c = [], [], [], []
for (tid, mid), g in stl.groupby(["team_id", "match_id"]):
    o = g[g.position != "G"].sort_values("average_x")
    if len(g) != 11 or len(o) != 10: continue
    xs, ys = o.average_x.values, o.average_y.values
    lg_def.append(xs[:4].mean()*1.05); lg_front.append(xs[-3:].mean()*1.05); lg_w.append((ys.max()-ys.min())*.68)
LG = dict(defl=np.mean(lg_def), front=np.mean(lg_front), width=np.mean(lg_w))
lgp, lgl, lgx = [], [], []
for mid in ALL.MATCH_ID.unique():
    for side in ("h", "a"):
        v = tsv(mid, "ballPossession", side); ps = tsv(mid, "passes", side); lt = tsv(mid, "accurateLongBalls", side, total=True); xg_ = tsv(mid, "expectedGoals", side)
        if not np.isnan(v): lgp.append(v)
        if ps and not np.isnan(lt): lgl.append(lt / ps * 100)
        if not np.isnan(xg_): lgx.append(xg_)
LG.update(poss=np.mean(lgp), long=np.mean(lgl), xg=np.mean(lgx))
print("liga:", {k: round(float(v), 1) for k, v in LG.items()})

def roll(v, w=5): return [float(np.nanmean(v[max(0, i-w+1):i+1])) for i in range(len(v))]
def ser(k): return [m[k] for m in M]

# ¿cambió de verdad?  Apertura vs Clausura (Welch)
A_i = [i for i, m in enumerate(M) if "Apertura" in m["tour"]]; C_i = [i for i, m in enumerate(M) if "Clausura" in m["tour"]]
def change(k, unit, dec=1):
    a, c = np.array([ser(k)[i] for i in A_i]), np.array([ser(k)[i] for i in C_i])
    a, c = a[~np.isnan(a)], c[~np.isnan(c)]
    t = stats.ttest_ind(c, a, equal_var=False); d = c.mean() - a.mean()
    verdict = "cambio probable" if t.pvalue < .05 else "no concluyente"
    return d, t.pvalue, verdict, f"{d:+.{dec}f} {unit}"
CH = {k: change(k, u, dd) for k, u, dd in (("defl", "m", 1), ("width", "m", 1), ("comp", "m", 1), ("poss", "pp", 1), ("long", "pp", 1), ("xgf", "xG", 2), ("xga", "xG", 2))}
for k, v in CH.items(): print(f"Apertura→Clausura {k:6s} {v[3]:>10s} p={v[1]:.3f} {v[2]}")

# ---------- Opción A: línea de tiempo + cancha con estela
CSS_TL = []
ticks, shapes, infos, radios = [], [], [], []
colr = {"G": GREEN, "E": "#8e8e93", "P": RED}
prev_tour = None
for i, m in enumerate(M, start=1):
    radios.append(f'<input type="radio" name="md" id="md{i}" class="mk-hide"{" checked" if i == N else ""}>')
    gap = ' style="margin-left:10px"' if prev_tour and m["tour"] != prev_tour else ""
    prev_tour = m["tour"]
    ticks.append(f'<label for="md{i}" class="tk"{gap} title="{m["dt"]:%d/%m} vs {html.escape(m["rival"])} {m["gf"]}-{m["ga"]}"><i style="background:{colr[m["res"]]}"></i><span>{i if i % 5 == 0 or i == 1 else ""}</span></label>')
    g = []
    for d in SP[m["mid"]]:                          # estela: posiciones del mismo jugador en los 4 partidos previos
        trail = [S[M[j]["mid"]][d["pid"]] for j in range(max(0, i-5), i-1) if d["pid"] in S[M[j]["mid"]]]
        pts = [to_svg(*t) for t in trail] + [to_svg(d["x"], d["y"])]
        if len(pts) > 1:
            g.append(f'<polyline points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in pts)}" fill="none" stroke="var(--text-tertiary)" stroke-width=".35" stroke-opacity=".7"/>')
            g.extend(f'<circle cx="{x:.2f}" cy="{y:.2f}" r=".8" fill="var(--text-tertiary)" fill-opacity=".55"/>' for x, y in pts[:-1])
    dl, fr = 105 - m["defl"], 105 - m["front"]
    g.append(f'<line x1="0" y1="{dl:.2f}" x2="68" y2="{dl:.2f}" stroke="var(--accent)" stroke-width=".4" stroke-dasharray="1.6 1.2"/>'
             f'<line x1="0" y1="{fr:.2f}" x2="68" y2="{fr:.2f}" stroke="var(--accent)" stroke-width=".4" stroke-dasharray="1.6 1.2"/>'
             f'<line x1="0" y1="{105-LG["defl"]:.2f}" x2="68" y2="{105-LG["defl"]:.2f}" stroke="var(--text-secondary)" stroke-width=".3" stroke-dasharray=".6 1.4"/>'
             f'<text x="1" y="{dl-.8:.2f}" font-size="2.3" fill="var(--accent)">línea defensiva {m["defl"]:.0f} m</text>'
             f'<text x="1" y="{fr-.8:.2f}" font-size="2.3" fill="var(--accent)">línea de ataque {m["front"]:.0f} m</text>')
    for d in SP[m["mid"]]:
        cx, cy = to_svg(d["x"], d["y"]); g.append(node(cx, cy, str(d["dor"]) if d["dor"] is not None else "–", "var(--text-secondary)" if d["pos"] != "G" else AMBER, 3.1, .7))
    shapes.append(f'<g class="sh sh-{i}">{"".join(g)}</g>')
    def delta(k, dec=1):
        prevv = [M[j][k] for j in range(max(0, i-6), i-1) if not np.isnan(M[j][k])]
        if not prevv or np.isnan(m[k]): return ""
        d = m[k] - np.mean(prevv); return f'<span class="mk-dim"> ({d:+.{dec}f} vs 5 previos)</span>'
    infos.append(f'''<div class="inf inf-{i}"><div style="font-weight:700">Fecha {i} · {m["dt"]:%d %b} · {html.escape(m["tour"].replace("Liga 1, ", ""))} R{m["rnd"]}</div>
  <div class="mk-dim" style="margin-bottom:.5rem">{"Local" if m["home"] else "Visita"} vs {html.escape(m["rival"])} · <b style="color:{colr[m["res"]]}">{m["gf"]}–{m["ga"]}</b></div>
  <div class="mk-kv"><span>Línea defensiva</span><b>{m["defl"]:.0f} m{delta("defl")}</b></div>
  <div class="mk-kv"><span>Línea de ataque</span><b>{m["front"]:.0f} m{delta("front")}</b></div>
  <div class="mk-kv"><span>Ancho del equipo</span><b>{m["width"]:.0f} m{delta("width")}</b></div>
  <div class="mk-kv"><span>Posesión</span><b>{m["poss"]:.0f} %{delta("poss", 0)}</b></div>
  <div class="mk-kv"><span>Balones largos / pases</span><b>{m["long"]:.0f} %{delta("long", 0)}</b></div>
  <div class="mk-kv"><span>xG a favor · en contra</span><b>{m["xgf"]:.2f} · {m["xga"]:.2f}</b></div></div>''')
    CSS_TL.append(f".tl:has(#md{i}:checked) .sh-{i},.tl:has(#md{i}:checked) .inf-{i}{{display:block}}"
                  f".tl:has(#md{i}:checked) label[for=md{i}]{{background:var(--selected-bg);outline:1.5px solid var(--accent)}}")
svg_tl = ('<svg viewBox="-1 -1 70 107" width="330" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Figura del equipo por fecha">'
          + pitch_lines() + "".join(shapes) + "</svg>")
opt_a = f'''<div class="tl" onclick="event.stopPropagation()">{"".join(radios)}
  <div class="mk-row" style="align-items:flex-start"><div>{svg_tl}</div>
    <div style="flex:1;min-width:270px"><div class="mk-label">Elige una fecha en la línea de tiempo</div><div class="mk-strip">{"".join(ticks)}</div>
      <div class="mk-dim" style="margin:.2rem 0 .8rem">Apertura ◂ ▸ Clausura · verde = ganó, gris = empató, rojo = perdió</div>{"".join(infos)}
      <div class="mk-dim" style="margin-top:.6rem">Líneas azules: altura media de la línea defensiva (4 más retrasados) y de ataque (3 más adelantados). Punteada gris: promedio de la liga. Estela: dónde jugó cada uno en los 4 partidos previos.</div></div></div></div>'''

# ---------- Opción B: multiples pequeños por bloque de 5 partidos
blocks = [M[i:i+5] for i in range(0, N, 5)]
cells = []
for bi, blk in enumerate(blocks):
    acc = {}
    for m in blk:
        for d in SP[m["mid"]]: acc.setdefault(d["pid"], []).append((d["x"], d["y"], d["dor"], d["pos"]))
    g = []
    for pid_, v in acc.items():
        if len(v) < max(2, len(blk) // 2): continue
        x_, y_ = np.mean([a[0] for a in v]), np.mean([a[1] for a in v]); cx, cy = to_svg(x_, y_)
        g.append(node(cx, cy, str(v[0][2]) if v[0][2] is not None else "–", "var(--text-secondary)" if v[0][3] != "G" else AMBER, 3.6, .8))
    dl, fr = float(np.mean([m["defl"] for m in blk])), float(np.mean([m["front"] for m in blk]))
    prev = blocks[bi-1] if bi else None
    dd = f'{dl - np.mean([m["defl"] for m in prev]):+.1f} m' if prev else "—"
    lines = (f'<line x1="0" y1="{105-dl:.2f}" x2="68" y2="{105-dl:.2f}" stroke="var(--accent)" stroke-width=".5" stroke-dasharray="1.6 1.2"/>'
             f'<line x1="0" y1="{105-fr:.2f}" x2="68" y2="{105-fr:.2f}" stroke="var(--accent)" stroke-width=".5" stroke-dasharray="1.6 1.2"/>')
    cells.append(f'<div class="mk-sm"><svg viewBox="-1 -1 70 107" width="150" xmlns="http://www.w3.org/2000/svg">{pitch_lines()}{lines}{"".join(g)}</svg>'
                 f'<div style="font-size:.72rem;line-height:1.3"><b>{blk[0]["dt"]:%d %b} – {blk[-1]["dt"]:%d %b}</b><br>L. def. {dl:.0f} m <span class="mk-dim">({dd})</span><br>'
                 f'<span class="mk-dim">{sum(1 for m in blk if m["res"]=="G")}G {sum(1 for m in blk if m["res"]=="E")}E {sum(1 for m in blk if m["res"]=="P")}P · {np.mean([m["poss"] for m in blk]):.0f} % pos.</span></div></div>')
opt_b = f'<div class="mk-smgrid">{"".join(cells)}</div><div class="mk-dim" style="margin-top:.6rem">Cada recuadro promedia 5 partidos y solo muestra a quienes fueron titulares en la mitad o más de ellos. La línea azul es la altura de la línea defensiva y de ataque del bloque.</div>'

# ---------- Opción C: tendencias de estilo con promedio móvil y promedio de la liga
def linechart(title, keys, lg, fmt, colors, ylo=None, yhi=None, W=290, H=120):
    pad_l, pad_r, pad_t, pad_b = 34, 8, 8, 18
    allv = [v for k in keys for v in ser(k) if not np.isnan(v)] + [lg]
    lo = ylo if ylo is not None else min(allv) - (max(allv) - min(allv)) * .1
    hi = yhi if yhi is not None else max(allv) + (max(allv) - min(allv)) * .1
    X = lambda i: pad_l + i * (W - pad_l - pad_r) / (N - 1)
    Y = lambda v: pad_t + (hi - v) * (H - pad_t - pad_b) / (hi - lo)
    g = [f'<line x1="{pad_l}" y1="{Y(lg):.1f}" x2="{W-pad_r}" y2="{Y(lg):.1f}" stroke="var(--text-secondary)" stroke-width=".8" stroke-dasharray="3 3"/>']
    sp = next((i for i, m in enumerate(M) if "Clausura" in m["tour"]), None)
    if sp: g.append(f'<line x1="{X(sp-.5):.1f}" y1="{pad_t}" x2="{X(sp-.5):.1f}" y2="{H-pad_b}" stroke="var(--border)" stroke-width="1"/>'
                    f'<text x="{X(sp/2):.1f}" y="{H-4}" font-size="8" fill="var(--text-secondary)" text-anchor="middle">Apertura</text>'
                    f'<text x="{X((sp+N)/2):.1f}" y="{H-4}" font-size="8" fill="var(--text-secondary)" text-anchor="middle">Clausura</text>')
    for t in (lo, (lo + hi) / 2, hi):
        g.append(f'<text x="{pad_l-4}" y="{Y(t)+3:.1f}" font-size="8" fill="var(--text-secondary)" text-anchor="end">{fmt(t)}</text>')
    for k, c in zip(keys, colors):
        v = ser(k)
        g.extend(f'<circle cx="{X(i):.1f}" cy="{Y(x):.1f}" r="1.6" fill="{c}" fill-opacity=".28"/>' for i, x in enumerate(v) if not np.isnan(x))
        r = roll(v); g.append(f'<polyline points="{" ".join(f"{X(i):.1f},{Y(x):.1f}" for i, x in enumerate(r))}" fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round"/>')
    return (f'<div class="mk-ch"><div style="font-size:.8rem;font-weight:600">{title}</div>'
            f'<svg viewBox="0 0 {W} {H}" width="{W}" xmlns="http://www.w3.org/2000/svg">{"".join(g)}</svg></div>')
def chip_change(label, k):
    d, p, verdict, txt = CH[k]; ok = verdict == "cambio probable"
    return (f'<span class="mk-cc" style="border-color:{"var(--accent)" if ok else "var(--border)"}"><b>{label}</b> {txt} <span style="color:{"var(--accent)" if ok else "var(--text-secondary)"}">· {verdict}</span></span>')
ch_html = (linechart("Altura de la línea defensiva (m)", ["defl"], LG["defl"], lambda v: f"{v:.0f}", ["var(--accent)"])
           + linechart("Posesión (%)", ["poss"], LG["poss"], lambda v: f"{v:.0f}", ["var(--accent)"])
           + linechart("Balones largos (% de pases)", ["long"], LG["long"], lambda v: f"{v:.0f}", ["var(--accent)"])
           + linechart("xG a favor (azul) y en contra (rojo)", ["xgf", "xga"], LG["xg"], lambda v: f"{v:.1f}", ["var(--accent)", RED], ylo=0))
opt_c = (f'<div class="mk-chgrid">{ch_html}</div>'
         f'<div class="mk-label" style="margin:.9rem 0 .35rem">¿Cambió de verdad? Apertura → Clausura (prueba de Welch, p &lt; 0,05)</div>'
         f'<div>{chip_change("Línea defensiva", "defl")}{chip_change("Ancho", "width")}{chip_change("Posesión", "poss")}{chip_change("Balones largos", "long")}{chip_change("xG a favor", "xgf")}{chip_change("xG en contra", "xga")}</div>'
         f'<div class="mk-dim" style="margin-top:.5rem">Puntos = cada partido (ruidoso). Línea = promedio de los últimos 5. Punteada = promedio de la liga.</div>')

# =====================================================================================
CSS = '''<style>
.mk-hide{position:absolute;opacity:0;pointer-events:none}
.mk-row{display:flex;gap:1.4rem;flex-wrap:wrap}
.mk-label{font-size:.68rem;text-transform:uppercase;letter-spacing:.06em;color:var(--text-secondary)}
.mk-dim{color:var(--text-secondary);font-size:.78rem}
.mk-kv{display:flex;justify-content:space-between;gap:1rem;padding:.26rem 0;border-bottom:1px solid var(--border);font-size:.84rem}
.mk-kv span{color:var(--text-secondary)}
.mk-legend{margin-top:.6rem;font-size:.72rem;color:var(--text-secondary)}
.mk-chips{display:flex;gap:.4rem;margin-bottom:.8rem;font-size:.76rem;flex-wrap:wrap;align-items:center}
.mk-chips span,.mk-chips label{padding:.22rem .7rem;border:1px solid var(--border);border-radius:999px;color:var(--text-secondary);cursor:pointer}
.net:has(#ms-xg:checked) label[for=ms-xg],.net:has(#ms-gl:checked) label[for=ms-gl]{background:var(--accent);border-color:var(--accent);color:#fff}
.net:has(#ms-xg:checked) .m-gl{display:none}.net:has(#ms-gl:checked) .m-xg{display:none}
.net .edge{opacity:0;transition:opacity .12s}.net .edge.f{opacity:var(--op)}
.net:has(.node:hover) .edge,.net:has(.node:focus) .edge{opacity:0}
.net .node{cursor:pointer;outline:none}
.net .panel{display:none}.net .panel.f{display:block}
.net:has(.node:hover) .panel,.net:has(.node:focus) .panel{display:none}
.mk-li{display:flex;align-items:center;gap:.5rem;padding:.34rem 0;border-bottom:1px solid var(--border);font-size:.82rem}
.mk-bar{position:relative;width:104px;height:14px;background:var(--bg-primary);border-radius:4px;flex:none}
.mk-bar:before{content:"";position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--border)}
.mk-bar i{position:absolute;top:3px;bottom:3px;border-radius:3px}
.mk-conf{letter-spacing:1px;font-size:.6rem;width:40px;text-align:right}
.mk-dor{display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:var(--bg-tertiary);border:1px solid var(--border);font-weight:700;flex:none}
.mk-stats{display:flex;gap:1.2rem;margin:.7rem 0 .2rem}.mk-stats div{display:flex;flex-direction:column;line-height:1.1}
.mk-stats b{font-size:1.25rem}.mk-stats span{font-size:.68rem;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.05em}
.mk-gr{display:flex;align-items:center;gap:.5rem;font-size:.78rem;margin:.14rem 0}.mk-gr i{height:9px;border-radius:2px;display:inline-block}
.tl .sh,.tl .inf{display:none}
.mk-strip{display:flex;gap:2px;margin:.4rem 0 .3rem;overflow-x:auto;padding-bottom:2px}
.tk{display:flex;flex-direction:column;align-items:center;gap:2px;width:15px;padding:3px 0;border-radius:4px;cursor:pointer;flex:none}
.tk i{display:block;width:9px;height:22px;border-radius:2px}.tk span{font-size:.6rem;color:var(--text-secondary);height:10px}
.mk-smgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:.9rem}
.mk-sm{display:flex;gap:.6rem;align-items:flex-start;background:var(--bg-primary);border:1px solid var(--border);border-radius:8px;padding:.5rem}
.mk-chgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:.9rem}
.mk-ch{background:var(--bg-primary);border:1px solid var(--border);border-radius:8px;padding:.5rem .6rem}
.mk-cc{display:inline-block;border:1px solid var(--border);border-radius:999px;padding:.2rem .65rem;margin:0 .35rem .35rem 0;font-size:.76rem}
.mk-note{font-size:.82rem;color:var(--text-secondary);margin:.2rem 0 1rem}
.mk-warn{border-left:3px solid var(--warning);background:var(--bg-primary);padding:.6rem .9rem;border-radius:0 8px 8px 0;font-size:.82rem;margin:.4rem 0 1rem}
.mk-box{background:var(--bg-secondary);border:1px solid var(--border);border-radius:12px;padding:1.1rem 1.25rem;margin-bottom:1.2rem}
.mk-nav{display:flex;gap:1.2rem;font-size:.85rem;margin:.2rem 0 1.2rem}.mk-nav a{color:var(--accent);text-decoration:none}
.cards.mk-stack{grid-template-columns:1fr}.mk-body{padding:1.1rem 1.25rem}
'''
CSS += "".join(dyn) + "".join(CSS_TL) + "</style>"

page = f'''{CSS}
<h2>Pantallas v2 · datos reales de {html.escape(team_name)} 2025</h2>
<p class="subtitle">Mockups con fotos, dorsales, goles y xG reales. Interacciones solo con CSS, así que funcionan sin cargar nada extra (necesitan un navegador reciente).</p>
<div class="mk-nav"><a href="#p1">1 · Compañeros (A + B fusionadas)</a><a href="#p2">2 · Estilo del equipo y su evolución</a></div>

<h3 id="p1">1 · Compañeros: red con dorsales y detalle al pasar el mouse</h3>
<p class="mk-note">Ejemplo: {html.escape(full(PID))}. La red muestra sus conexiones por defecto; al pasar el mouse sobre otro dorsal verás las conexiones de ese jugador, su foto y sus datos. La lista de la derecha es la versión B y es la que queda sola en móvil. El conmutador cambia la medida entre xGD y goles reales.</p>
<div class="mk-box">{part1}</div>

<h3 id="p2" style="margin-top:2rem">2 · Estilo del equipo y su evolución</h3>
<div class="mk-warn"><b>Sin etiquetas de formación (4-3-3…).</b> Con posiciones medias no son fiables: el ajuste a plantillas da 8,5 m de error mediano frente a 9,6 m con el ancho barajado al azar. En su lugar se mide la <b>figura</b> (líneas, ancho, compacidad) y se muestra con promedios móviles, porque un solo partido es ruidoso: la identidad del equipo explica solo 15–30 % de la variación entre partidos.</div>
<div class="cards mk-stack" data-multiselect>
  <div class="card" data-choice="a-linea-de-tiempo" onclick="toggleSelect(this)"><div class="mk-body">{opt_a}</div>
    <div class="card-body"><h3>A · Figura fecha a fecha</h3><p>Eliges una fecha y ves a los 11 titulares con su dorsal, la estela de los 4 partidos previos y cuánto se movió cada línea. Es lo más cercano a «cómo cambia la figura con los días».</p></div></div>
  <div class="card" data-choice="b-bloques" onclick="toggleSelect(this)"><div class="mk-body">{opt_b}</div>
    <div class="card-body"><h3>B · Bloques de 5 partidos</h3><p>Pequeños múltiplos para ver la película completa de la temporada de un vistazo. Menos detalle por partido, más fácil de leer y de compartir como imagen.</p></div></div>
  <div class="card" data-choice="c-tendencias" onclick="toggleSelect(this)"><div class="mk-body">{opt_c}</div>
    <div class="card-body"><h3>C · Tendencias de estilo</h3><p>Curvas de línea defensiva, posesión, balones largos y xG contra el promedio de la liga, con la prueba de si el cambio Apertura → Clausura es real o ruido. Muestra estilo, no solo posiciones.</p></div></div>
</div>'''

out = SCREEN / "pantallas-v2.html"
out.write_text(page, encoding="utf-8")

# ---------- validaciones: SVG bien formado + etiquetas HTML balanceadas
bad = 0
for m_ in re.finditer(r"<svg.*?</svg>", page, flags=re.S):
    try: ET.fromstring(m_.group(0))
    except ET.ParseError as ex: bad += 1; print("SVG mal formado:", ex)
VOID = {"img", "input", "br", "hr", "meta", "link"}
class Chk(HTMLParser):
    def __init__(s): super().__init__(); s.st = []; s.err = []
    def handle_starttag(s, t, a):
        if t not in VOID: s.st.append(t)
    def handle_startendtag(s, t, a): pass
    def handle_endtag(s, t):
        if t in VOID: return
        if not s.st or s.st[-1] != t: s.err.append((t, s.st[-3:]))
        else: s.st.pop()
c = Chk(); c.feed(re.sub(r"<style>.*?</style>", "", page, flags=re.S)); c.close()
print(f"escrito {out.name}: {len(page)/1024:.0f} KB | SVG inválidos={bad} | etiquetas HTML sin cerrar={len(c.st)} | cierres incorrectos={len(c.err)}", c.err[:3])
