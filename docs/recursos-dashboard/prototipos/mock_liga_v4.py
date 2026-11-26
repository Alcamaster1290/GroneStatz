"""Maqueta «pantalla-liga» v4 (2026-11-26): camino al título y contexto del partido, por equipo, Liga 1 2026 (Apertura y Clausura).

Lee solo datos ya calculados: el bundle publicado de 2026, `datos-de-apoyo/title-race/` (importancia y probabilidad), el xG propio
(`datos-de-apoyo/xg-prototipo/`) y la tabla de altitud medida. Escribe `mockups/pantalla-liga.html` (autocontenido, tema claro/oscuro).
Material de diseño: no es código de producción. Sustituye a `mock_liga.py` (v3, Apertura 2025 con el primer cálculo)."""
import base64
import html
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from gronestats.analysis.standings import ADJUSTMENTS_FILE, load_adjustments, season_tables  # noqa: E402
from gronestats.analysis.title_race import BAND_NAMES, FLOOR_THRESHOLD, REFERENCE_THRESHOLD, load_matches, match_importance  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
BASE = REPO / "gronestats/data/Liga 1 Peru"
SUPPORT = REPO / "docs/recursos-dashboard/datos-de-apoyo"
OUT = REPO / "docs/recursos-dashboard/mockups/pantalla-liga.html"
CREST = REPO / "gronestats/images/teams"
SEASON, MIN_N, TOURS = 2026, 6, ("Apertura", "Clausura")
TOUR_COLOR = {"Apertura": "var(--accent)", "Clausura": "#ff9500"}
BAND_COLORS = ["#0a84ff", "#34c759", "#ffcc00", "#ff9500", "#ff3b30", "#8e8e93"]
BAND_LABEL = ["Asegurado (umbral alcanzado)", "Baja (puede perder 3 o más)", "Media (puede perder 2)", "Alta (puede perder 1)", "Crítica (no puede perder)", "Fuera de alcance (ni a 37 pts)"]
LVL_ORDER = ("Candidato", "Competitivo", "Promedio", "Descenso")
ALT_BINS = [("Sede ≥ 1.500 m más arriba que la suya", lambda d: d >= 1500), ("Sede 500–1.500 m más arriba", lambda d: (d >= 500) & (d < 1500)),
            ("Sede a su altura (± 500 m)", lambda d: d.abs() < 500), ("Sede ≥ 500 m más abajo", lambda d: d <= -500)]

# ---------------------------------------------------------------- datos
D = BASE / str(SEASON) / "dashboard/current"
matches = load_matches(BASE, [SEASON])
matches["tour"] = matches["tour"].astype(str)
teams = pd.read_parquet(D / "teams.parquet").set_index("team_id")
ap = pd.read_parquet(D / "average_positions.parquet")
ts = pd.read_parquet(D / "team_stats.parquet")
POSS = ts[(ts.PERIOD.astype(str).str.upper() == "ALL") & (ts.KEY == "ballPossession")].drop_duplicates("MATCH_ID").set_index("MATCH_ID")
imp = pd.read_parquet(SUPPORT / "title-race/importancia_equipo_partido.parquet")
imp = imp[imp.season == SEASON].set_index(["match_id", "team_id"])
prob = pd.read_parquet(SUPPORT / "title-race/probabilidad_titulo.parquet")
prob = prob[prob.season == SEASON]
params = json.loads((SUPPORT / "title-race/parametros_elo.json").read_text(encoding="utf-8"))
FORM = pd.read_parquet(SUPPORT / "formaciones/formaciones_equipo_partido.parquet")
FORM = FORM[FORM.season == SEASON].set_index(["match_id", "team_id"])
xg = pd.read_parquet(SUPPORT / "xg-prototipo/xg_tiros.parquet")
xg = xg[xg.season == SEASON].groupby(["match_id", "is_home"]).xg.sum()
alt_table = pd.read_csv(SUPPORT / "altitud_estadios_medida.csv", encoding="utf-8-sig")
HEIGHT = {(r.estadio, r.ciudad_en_el_maestro): float(r.altitud_msnm) for r in alt_table.itertuples()}
matches["venue_alt"] = [HEIGHT.get((e, c), np.nan) for e, c in zip(matches.estadio, matches.ciudad)]
BASE_ALT = matches.groupby("home_id").venue_alt.median()            # sede habitual: la mediana de la altitud de sus partidos de local
IDS = sorted(set(matches.home_id.astype(int)) | set(matches.away_id.astype(int)), key=lambda t: str(teams.loc[t, "short_name"]))
nm = lambda t: str(teams.loc[t, "short_name"])
lvl = lambda t: str(teams.loc[t, "competitiveness_level"])
champs = pd.read_csv(SUPPORT / "title-race/umbral_campeon_medido.csv", encoding="utf-8-sig")
CHAMP = {r.torneo: int(r.equipo_id) for r in champs[champs.temporada == SEASON].itertuples()}
print(f"{len(IDS)} equipos · partidos {len(matches)} · campeones {{{', '.join(f'{k}: {nm(v)}' for k, v in CHAMP.items())}}}")

# ---------------------------------------------------------------- escudos (cuadrados, nunca ampliados; 1x/2x/3x)
_c = {}


def crest_uri(tid, px):
    if (tid, px) in _c:
        return _c[(tid, px)]
    f = CREST / f"{tid}.png"
    if not f.exists():
        _c[(tid, px)] = None
        return None
    im = Image.open(f).convert("RGBA")
    w, h = im.size
    s = max(w, h)
    if w != h:
        sq = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        sq.paste(im, ((s - w) // 2, (s - h) // 2))
        im = sq
    side = min(px, im.width)
    buf = io.BytesIO()
    im.resize((side, side), Image.LANCZOS).save(buf, "PNG", optimize=True)
    _c[(tid, px)] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return _c[(tid, px)]


CSS_CR, NO_CREST = [], []
for t in IDS:
    for size in (28, 44):
        u = [crest_uri(t, size * k) for k in (1, 2, 3)]
        if u[0] is None:
            NO_CREST.append(t)
            break
        CSS_CR.append(f".cr{size}-{t}{{width:{size}px;height:{size}px;background:center/contain no-repeat;background-image:url({u[0]});background-image:image-set(url({u[0]}) 1x,url({u[1]}) 2x,url({u[2]}) 3x)}}")
print("equipos sin escudo:", NO_CREST)
crest = lambda t, size=28: f'<span class="cr{size}-{t} crest" role="img" aria-label="Escudo de {html.escape(nm(t))}"></span>'


def team_color(t):
    m = re.search(r"#[0-9a-fA-F]{6}", str(teams.loc[t, "team_colors"]))
    return m.group(0) if m else "#0a84ff"


def line_style(t):
    """Atributos de trazo: el color del equipo, mezclado con el color del texto para que un marino o un negro se vean en tema oscuro."""
    c = team_color(t)
    return f'stroke="{c}" style="stroke:color-mix(in srgb,{c} 62%,var(--text-primary))"'


# ---------------------------------------------------------------- tablas de posiciones
ADJUSTMENTS = load_adjustments(BASE / ADJUSTMENTS_FILE)  # sanciones de puntos y partidos que la tabla oficial cuenta sin goles
TABLES = season_tables(matches[matches.season == SEASON], SEASON, ADJUSTMENTS)
ST = {tour: TABLES[tour].set_index("team_id") for tour in TOURS}  # pos, pts, ... (tabla oficial)
SHORT = ["Asegurado", "Baja", "Media", "Alta", "Crítica", "Fuera"]


def fam(lab):
    return {3: "#af52de", 4: "#0a84ff", 5: "#ff9f0a"}.get(int(lab.split("-")[0]), "#8e8e93")


# ---------------------------------------------------------------- filas por equipo y partido
def team_rows(tid):
    g = matches[((matches.home_id == tid) | (matches.away_id == tid)) & matches.home_score.notna()].sort_values(["date", "match_id"])
    starters = ap[(ap.team_id == tid) & (ap.is_starter == True)]  # noqa: E712
    groups = {int(m): x for m, x in starters.groupby("match_id")}
    base_alt = BASE_ALT.get(tid, np.nan)
    rows = []
    for r in g.itertuples():
        mid, home = int(r.match_id), r.home_id == tid
        rid = int(r.away_id if home else r.home_id)
        gf, ga = (r.home_score, r.away_score) if home else (r.away_score, r.home_score)
        defl = np.nan
        if mid in groups and len(groups[mid]) == 11:
            out = groups[mid][groups[mid].position != "G"].sort_values("average_x")
            defl = float(out.average_x.values[:4].mean() * 1.05)
        # Formación declarada por SofaScore, cruzada con la posición de los 11 titulares (gronestats.analysis.formations)
        lab, ok_form, ok_def, why = None, None, None, ""
        if (mid, tid) in FORM.index:
            f = FORM.loc[(mid, tid)]
            lab = f.formation if isinstance(f.formation, str) else None
            ok_form, ok_def, why = bool(f.consistent), bool(f.defenders_ok), str(f.reason or "")
        poss = np.nan
        if mid in POSS.index:
            v = POSS.loc[mid]["HOMEVALUE" if home else "AWAYVALUE"]
            poss = float(v) if pd.notna(v) else np.nan
        i = imp.loc[(mid, tid)]
        rows.append(dict(mid=mid, tour=r.tour, dt=r.date, home=home, rid=rid, rival=nm(rid), level=lvl(rid), venue_alt=r.venue_alt, dalt=r.venue_alt - base_alt,
                         lab=lab, form_ok=ok_form, form_def=ok_def, form_why=why, defl=defl, poss=poss, gf=int(gf), ga=int(ga), pts=3 if gf > ga else 1 if gf == ga else 0,
                         xgf=float(xg.get((mid, home), np.nan)), xga=float(xg.get((mid, not home), np.nan)),
                         band=int(i.band), lives=None if pd.isna(i.lives) else int(i.lives), used=float(i.threshold_used), p_before=int(i.points_before),
                         rem=int(i.matches_remaining), needed=float(i.points_needed)))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- gráficos
def prob_series(tid, tour):
    s = prob[(prob.tour == tour) & (prob.team_id == tid)].sort_values("k")
    return s.k.to_numpy(), s.p_title.to_numpy() * 100


def prob_chart(tid):
    W, H, pl, pr, pt, pb = 330, 160, 32, 10, 10, 24
    X = lambda k: pl + k / 17 * (W - pl - pr)
    Y = lambda v: pt + (100 - v) * (H - pt - pb) / 100
    g = [f'<line x1="{pl}" y1="{Y(v):.1f}" x2="{W-pr}" y2="{Y(v):.1f}" stroke="var(--border)" stroke-width=".6"/><text x="{pl-4}" y="{Y(v)+3:.1f}" font-size="8" fill="var(--text-secondary)" text-anchor="end">{v}%</text>' for v in (0, 25, 50, 75, 100)]
    notes = []
    for tour in TOURS:
        k, s = prob_series(tid, tour)
        col = TOUR_COLOR[tour]
        g.append(f'<polyline points="{" ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(k, s))}" fill="none" stroke="{col}" stroke-width="2.3" stroke-linejoin="round"/>')
        pk = int(s.argmax())
        edge = s[pk] > 88 or k[pk] >= 16
        label = f'<text x="{X(k[pk]) - 6:.1f}" y="{Y(s[pk]) + 3:.1f}" font-size="8.5" text-anchor="end" fill="var(--text-primary)">{s[pk]:.0f}%</text>' if edge else f'<text x="{X(k[pk]):.1f}" y="{Y(s[pk])-6:.1f}" font-size="8.5" text-anchor="middle" fill="var(--text-primary)">{s[pk]:.0f}%</text>'
        g.append(f'<circle cx="{X(k[pk]):.1f}" cy="{Y(s[pk]):.1f}" r="3" fill="{col}"/>{label}')
        notes.append(f'<span style="color:{col}">●</span> {tour}: inicio {s[0]:.0f} % · máximo {s.max():.0f} % (tras {int(k[pk])} partidos) · final {s[-1]:.0f} %')
    g.append(f'<text x="{pl}" y="{H-7}" font-size="8" fill="var(--text-secondary)">0 partidos</text><text x="{W-pr}" y="{H-7}" font-size="8" text-anchor="end" fill="var(--text-secondary)">17 partidos jugados</text>')
    svg = f'<svg viewBox="0 0 {W} {H}" width="{W}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Probabilidad de campeonar según los partidos jugados">{"".join(g)}</svg>'
    return svg, notes


def idx_chart(df):
    W, H, pl, pr, pt, pb = 330, 160, 30, 10, 10, 24
    X = lambda k: pl + k / 17 * (W - pl - pr)
    Y = lambda v: pt + (1.05 - v) * (H - pt - pb) / 1.05
    g = [f'<line x1="{pl}" y1="{Y(1):.1f}" x2="{W-pr}" y2="{Y(1):.1f}" stroke="var(--success)" stroke-dasharray="4 3"/><text x="{W-pr}" y="{Y(1)-3:.1f}" font-size="8" text-anchor="end" fill="var(--success)">umbral: {REFERENCE_THRESHOLD:.0f} pts</text>']
    for v in (0, .5):
        g.append(f'<text x="{pl-4}" y="{Y(v)+3:.1f}" font-size="8" fill="var(--text-secondary)" text-anchor="end">{v:.1f}</text><line x1="{pl}" y1="{Y(v):.1f}" x2="{W-pr}" y2="{Y(v):.1f}" stroke="var(--border)" stroke-width=".6"/>')
    g.append(f'<line x1="{X(0):.1f}" y1="{Y(0):.1f}" x2="{X(17):.1f}" y2="{Y(1):.1f}" stroke="var(--text-secondary)" stroke-dasharray="1.5 3"/>')
    for tour in TOURS:
        s = df[df.tour == tour]
        pts = [(0, 0.0)] + [(k + 1, min(1.0, (p + q) / REFERENCE_THRESHOLD)) for k, (p, q) in enumerate(zip(s.p_before, s.pts))]
        col = TOUR_COLOR[tour]
        g.append(f'<polyline points="{" ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in pts)}" fill="none" stroke="{col}" stroke-width="2.2"/>')
        a, b = pts[-1]
        final = int(s.p_before.iloc[-1] + s.pts.iloc[-1])
        g.append(f'<circle cx="{X(a):.1f}" cy="{Y(b):.1f}" r="3" fill="{col}"/><text x="{X(a)-4:.1f}" y="{Y(b)+11:.1f}" font-size="8" text-anchor="end" fill="{col}">{tour} · {final} pts</text>')
    return f'<svg viewBox="0 0 {W} {H}" width="{W}" xmlns="http://www.w3.org/2000/svg">{"".join(g)}</svg>'


# ---------------------------------------------------------------- sección de un equipo
SENS = {T_: match_importance(matches[matches.season == SEASON], threshold=T_, floor_threshold=None) for T_ in (37, 40, 42)}  # sin piso: aísla el efecto del umbral


def fmt_m(v):
    return "—" if pd.isna(v) else f"{v:,.0f}".replace(",", ".") + " m"


def section(tid):
    df = team_rows(tid)
    items = {tour: [] for tour in TOURS}
    for m in df.itertuples():
        b = m.band
        imp_txt = SHORT[b] + (f" ({m.lives})" if (m.lives is not None and b in (1, 2, 3, 4)) else "") + ("*" if m.used != REFERENCE_THRESHOLD else "")
        det = (f'{m.dt:%d/%m/%Y} · {m.tour} · {"Local" if m.home else "Visita"} vs {m.rival} ({m.level}) {m.gf}-{m.ga} · sede {fmt_m(m.venue_alt)} · formación declarada {m.lab or "no disponible"}{(" (" + m.form_why + ")") if m.form_ok is False and m.form_why else ""} · '
               f'tenía {m.p_before} pts y le quedaban {m.rem} partidos (incluido este); para {m.used:.0f} pts necesitaba {m.needed:.0f}'
               + (f' · «Fuera de alcance» con 40, pero aún llegaba a {FLOOR_THRESHOLD:.0f}' if m.used != REFERENCE_THRESHOLD else ""))
        res = ("G" if m.pts == 3 else "E" if m.pts == 1 else "P") + f" {m.gf}-{m.ga}"
        rc = "#34c759" if m.pts == 3 else "#8e8e93" if m.pts == 1 else "#ff3b30"
        up = pd.notna(m.dalt) and m.dalt >= 1500
        alt_style = "background:#af52de;color:#fff;font-weight:700" if up else ""
        lab = m.lab or "—"
        flag = " ⚠" if (m.lab and m.form_def is False) else ""  # solo si no coincide el número de defensas
        items[m.tour].append(
            f'<div class="cx" title="{html.escape(det)}"><div class="cx-d">{m.dt:%d/%m}</div><div class="cx-c">{crest(m.rid, 28)}</div>'
            f'<div class="cx-t lvl">{html.escape(m.level)}</div><div class="cx-t">{"Local" if m.home else "Visita"}</div><div class="cx-t" style="{alt_style}">{fmt_m(m.venue_alt)}</div>'
            f'<div class="cx-t" style="background:{rc};color:#fff;font-weight:700">{res}</div><div class="cx-t" style="background:{fam(lab) if m.lab else "var(--bg-tertiary)"};color:#fff;font-weight:700">{lab}{flag}</div>'
            f'<div class="cx-t imp" style="background:{BAND_COLORS[b]}">{html.escape(imp_txt)}</div></div>')
    labels = ('<div class="cx-lbls"><span>Fecha</span><span style="height:34px;line-height:34px">Rival</span><span>Nivel del rival</span><span>Sede</span><span>Altitud de la sede</span>'
              '<span>Resultado</span><span>Formación declarada</span><span>Importancia (derrotas)</span></div>')
    strips = "".join(f'<div class="dim" style="margin:.7rem 0 .3rem;color:{TOUR_COLOR[t]}"><b>{t} {SEASON}</b> · {len(items[t])} partidos</div><div class="cx-wrap">{labels}<div class="cx-row">{"".join(items[t])}</div></div>' for t in TOURS)

    def grp(mask, label, note=""):
        s = df[mask]
        n = len(s)
        if n == 0:
            return ""
        f = lambda v, d=1: "—" if pd.isna(v) else f"{v:.{d}f}"
        low = n < MIN_N
        forms = s.lab.dropna().value_counts()
        if len(forms):
            bars = "".join(f'<i style="width:{100*c/len(s.lab.dropna()):.0f}%;background:{fam(l)};opacity:{1-.13*k:.2f}" title="{l}: {c} de {len(s.lab.dropna())}"></i>' for k, (l, c) in enumerate(forms.head(4).items()))
            top = f'<div class="stack">{bars}</div><span class="dim">{forms.index[0]} en {int(forms.iloc[0])} de {len(s.lab.dropna())}</span>'
        else:
            top = '<span class="dim">sin formación</span>'
        return (f'<tr{" class=low" if low else ""}><td><b>{label}</b>{f"<br><span class=dim>{note}</span>" if note else ""}</td><td>{n}{" ⚠" if low else ""}</td><td>{top}</td>'
                f'<td>{f(s.defl.mean(), 0)} m</td><td>{f(s.poss.mean(), 0)} %</td><td>{f(s.xgf.mean(), 2)} · {f(s.xga.mean(), 2)}</td><td>{f(s.pts.mean(), 2)}</td></tr>')

    T = ['<tr class="sec"><td colspan="7">Por importancia para el título (derrotas que aún podía permitirse)</td></tr>']
    T += [grp(df.band == b, BAND_LABEL[b].split(" (")[0]) for b in range(6)]
    T.append('<tr class="sec"><td colspan="7">Por nivel del rival</td></tr>')
    T += [grp(df.level == l, l) for l in LVL_ORDER]
    T.append('<tr class="sec"><td colspan="7">Por altitud de la sede respecto a la suya (' + fmt_m(BASE_ALT.get(tid, np.nan)) + ')</td></tr>')
    T += [grp(fn(df.dalt.fillna(0)) & df.dalt.notna(), label) for label, fn in ALT_BINS]
    T.append('<tr class="sec"><td colspan="7">Por localía</td></tr>')
    T += [grp(df.home, "Local"), grp(~df.home, "Visita")]
    table = ('<table class="ctx"><thead><tr><th>Contexto</th><th>PJ</th><th>Formación más usada</th><th>Línea def.</th><th>Posesión</th><th>xG fav · contra*</th><th>Pts/PJ</th></tr></thead>'
             f'<tbody>{"".join(T)}</tbody></table>')
    pc, notes = prob_chart(tid)
    ic = idx_chart(df)
    hi = df[df.band.isin([3, 4])]
    sens = {}
    for T_ in (37, 40, 42):
        mine = SENS[T_]
        sens[T_] = int(mine[mine.team_id == tid].band.isin([3, 4]).sum())
    pos = {tour: ST[tour].loc[tid] for tour in TOURS}
    head = (f'<div class="th">{crest(tid, 44)}<div><div class="tn">{html.escape(str(teams.loc[tid, "full_name"]))}</div>'
            f'<div class="dim">Nivel de competitividad: <b>{lvl(tid)}</b> · sede habitual a <b>{fmt_m(BASE_ALT.get(tid, np.nan))}</b> · '
            + " · ".join(f'{t}: <b>{int(pos[t].pos)}.º</b> con {int(pos[t].pts)} pts{" (campeón)" if CHAMP.get(t) == tid else ""}' for t in TOURS) + '</div></div></div>')
    probs = (f'<div class="row2"><div><div class="dim" style="margin-bottom:.3rem">Probabilidad de campeonar · tras cada partido jugado</div>{pc}'
             f'<div class="dim" style="max-width:330px">{"<br>".join(notes)}</div></div>'
             f'<div><div class="dim" style="margin-bottom:.3rem">Índice del Campeón (puntos ÷ {REFERENCE_THRESHOLD:.0f})</div>{ic}'
             f'<div class="dim" style="max-width:330px">Punteada gris = ritmo ideal para llegar a 40 al partido 17.</div></div>'
             f'<div style="flex:1;min-width:240px"><div class="dim" style="margin-bottom:.3rem">Lectura rápida</div>'
             f'<span class="cc"><b>{len(hi)}</b> partidos de importancia alta o crítica: <b>{int((hi.dalt >= 1500).sum())}</b> en sedes ≥ 1.500 m más arriba · <b>{int((hi.level == "Candidato").sum())}</b> contra Candidatos</span>'
             f'<span class="cc">Umbral 37 / 40 / 42 pts → <b>{sens[37]}</b> / <b>{sens[40]}</b> / <b>{sens[42]}</b> partidos alta o crítica (sin piso)</span>'
             f'<span class="cc">Formación declarada: el número de defensas de los 11 titulares coincide en <b>{int((df.form_def == True).sum())}</b> de <b>{int(df.form_def.notna().sum())}</b> partidos (⚠ en la tira = no coincide); la distribución completa, en <b>{int((df.form_ok == True).sum())}</b></span></div></div>')  # noqa: E712
    return (f'<div class="team t-{tid}">{head}{probs}<div class="box" style="margin-top:1rem"><div class="dim">Evolución partido a partido ({len(df)} partidos). Pasa el mouse por un partido para ver el detalle.</div>{strips}</div>'
            f'<div class="box"><div class="dim" style="margin-bottom:.5rem">Cómo cambia el juego según el contexto (los dos torneos juntos)</div>{table}'
            f'<div class="dim" style="margin-top:.5rem">⚠ = menos de {MIN_N} partidos. Los contextos se solapan. La importancia depende de los resultados previos, así que «Pts/PJ» por banda está en parte condicionado por la racha. '
            f'* xG GroneStats (modelo propio), no el del proveedor.</div></div></div>')


# ---------------------------------------------------------------- vista de toda la liga
def league_block(tour):
    W, H, pl, pr, pt, pb = 860, 300, 36, 14, 16, 26
    X = lambda k: pl + k / 17 * (W - pl - pr)
    Y = lambda v: pt + (100 - v) * (H - pt - pb) / 100
    series = {t: prob_series(t, tour) for t in IDS}
    peak = {t: float(series[t][1].max()) for t in IDS}
    top = sorted(peak, key=lambda t: -peak[t])[:6]
    if CHAMP.get(tour) not in top:
        top = top[:5] + [CHAMP[tour]]
    g = [f'<line x1="{pl}" y1="{Y(v):.1f}" x2="{W-pr}" y2="{Y(v):.1f}" stroke="var(--border)" stroke-width=".6"/><text x="{pl-5}" y="{Y(v)+3:.1f}" font-size="9" fill="var(--text-secondary)" text-anchor="end">{v}%</text>' for v in (0, 25, 50, 75, 100)]
    for t in IDS:
        if t not in top:
            k, s = series[t]
            g.append(f'<polyline points="{" ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(k, s))}" fill="none" stroke="var(--text-tertiary)" stroke-width="1" stroke-opacity=".55"/>')
    for t in top:
        k, s = series[t]
        g.append(f'<polyline points="{" ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(k, s))}" fill="none" {line_style(t)} stroke-width="2.4" stroke-linejoin="round"/>')
    for t in top:
        k, s = series[t]
        i = int(s.argmax())
        u = crest_uri(t, 66)
        g.append(f'<image href="{u}" x="{X(k[i])-11:.1f}" y="{Y(s[i])-11:.1f}" width="22" height="22"/>' if u else f'<circle cx="{X(k[i]):.1f}" cy="{Y(s[i]):.1f}" r="5" fill="{team_color(t)}"/>')
    g.append(f'<text x="{pl}" y="{H-7}" font-size="9" fill="var(--text-secondary)">0 partidos</text><text x="{W-pr}" y="{H-7}" font-size="9" text-anchor="end" fill="var(--text-secondary)">17 partidos jugados</text>')
    svg = f'<svg viewBox="0 0 {W} {H}" style="width:100%;max-width:{W}px;height:auto" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Probabilidad de campeonar, {tour}, todos los equipos">{"".join(g)}</svg>'
    rows = []
    for t in sorted(IDS, key=lambda t: ST[tour].loc[t].pos):
        k, s = series[t]
        at = lambda n: f"{s[min(n, len(s) - 1)]:.0f} %"
        champion = CHAMP.get(tour) == t
        rows.append(f'<tr{" style=font-weight:700" if champion else ""}><td>{crest(t, 28)}<b style="margin-left:.5rem">{html.escape(nm(t))}</b>{" 🏆" if champion else ""}</td><td>{lvl(t)}</td><td>{at(0)}</td>'
                    + "".join(f"<td>{at(n)}</td>" for n in (6, 9, 12, 15)) + f'<td>{int(ST[tour].loc[t].pos)}.º · {int(ST[tour].loc[t].pts)} pts</td></tr>')
    tab = ('<table class="ctx"><thead><tr><th>Equipo</th><th>Nivel</th><th>Inicio</th><th>Tras 6</th><th>Tras 9</th><th>Tras 12</th><th>Tras 15</th><th>Final</th></tr></thead>'
           f'<tbody>{"".join(rows)}</tbody></table>')
    cname = nm(CHAMP[tour])
    cpts = int(ST[tour].loc[CHAMP[tour]].pts)
    return (f'<div class="box"><div class="dim" style="margin-bottom:.4rem;color:{TOUR_COLOR[tour]}"><b>{tour} {SEASON}</b> · campeón: <b>{html.escape(cname)}</b> con {cpts} pts. '
            f'Probabilidad de campeonar tras N partidos jugados (escudo = punto de máxima probabilidad; en color los 6 con más probabilidad y el campeón)</div>{svg}{tab}</div>')


# ---------------------------------------------------------------- página
SECTIONS = [section(t) for t in IDS]
sel = "".join(f'<input type="radio" name="tm" id="sel-{t}" class="mk-hide"{" checked" if t == CHAMP["Clausura"] else ""}>' for t in IDS)
labs = "".join(f'<label for="sel-{t}" class="selb">{crest(t, 44)}<span><b>{html.escape(nm(t))}</b><br><small>{lvl(t)}</small></span></label>' for t in IDS)
dyn = "".join(f".wrap:has(#sel-{t}:checked) .t-{t}{{display:block}}.wrap:has(#sel-{t}:checked) label[for=sel-{t}]{{outline:2px solid var(--accent);background:var(--selected-bg)}}" for t in IDS)
legend = ('<div class="leg"><span><i style="background:#af52de"></i>3 defensas</span><span><i style="background:#0a84ff"></i>4 defensas</span><span><i style="background:#ff9f0a"></i>5 defensas</span>'
          + "".join(f'<span><i style="background:{c}"></i>{l}</span>' for l, c in zip(BAND_LABEL, BAND_COLORS))
          + '<span>El número entre paréntesis = derrotas que aún podía permitirse · * = el umbral usado fue 37 y no 40</span></div>')

P = params["params"]
CSS = '''<style>
:root{--bg-primary:#ffffff;--bg-secondary:#f5f5f7;--bg-tertiary:#e8e8ed;--border:#d2d2d7;--text-primary:#1d1d1f;--text-secondary:#6e6e73;--text-tertiary:#a1a1a6;--accent:#0a84ff;--success:#248a3d;--warning:#ff9500;--selected-bg:#e3f0ff;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg-primary:#161618;--bg-secondary:#1f1f22;--bg-tertiary:#2c2c30;--border:#3a3a3f;--text-primary:#f5f5f7;--text-secondary:#a1a1a6;--text-tertiary:#6e6e73;--accent:#64a8ff;--success:#30d158;--selected-bg:#1d3556;color-scheme:dark}}
:root[data-theme="dark"]{--bg-primary:#161618;--bg-secondary:#1f1f22;--bg-tertiary:#2c2c30;--border:#3a3a3f;--text-primary:#f5f5f7;--text-secondary:#a1a1a6;--text-tertiary:#6e6e73;--accent:#64a8ff;--success:#30d158;--selected-bg:#1d3556;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg-primary);color:var(--text-primary);font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.page{max-width:1120px;margin:0 auto;padding:20px 16px 40px}h2{margin:.2rem 0 .3rem}.subtitle{color:var(--text-secondary);margin:.2rem 0 1rem}
.mk-hide{position:absolute;opacity:0;pointer-events:none}
.dim{color:var(--text-secondary);font-size:.78rem}.dim small{font-size:.7rem}
.box{background:var(--bg-secondary);border:1px solid var(--border);border-radius:12px;padding:1.1rem 1.25rem;margin-bottom:1.2rem;overflow-x:auto}
.warn{border-left:3px solid var(--warning);background:var(--bg-secondary);padding:.6rem .9rem;border-radius:0 8px 8px 0;font-size:.82rem;margin:.4rem 0 1rem}
.warn p{margin:.25rem 0}
.crest{display:inline-block;vertical-align:middle;flex:none}
.sel{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:.45rem;margin:.6rem 0 1.2rem}
.selb{display:flex;align-items:center;gap:.55rem;padding:.35rem .55rem;border:1px solid var(--border);border-radius:10px;background:var(--bg-secondary);cursor:pointer;font-size:.8rem;line-height:1.15}
.selb small{color:var(--text-secondary)}
.wrap .team{display:none}
.th{display:flex;align-items:center;gap:.8rem;margin-bottom:.9rem}.tn{font-size:1.15rem;font-weight:700}
.row2{display:flex;gap:1.4rem;flex-wrap:wrap;align-items:flex-start}
.cx-wrap{display:flex;gap:.6rem;overflow-x:auto;padding-bottom:.4rem}
.cx-lbls{display:flex;flex-direction:column;gap:3px;font-size:.62rem;color:var(--text-secondary);text-align:right;min-width:132px;flex:none}
.cx-lbls span{height:20px;line-height:20px;white-space:nowrap}
.cx-row{display:flex;gap:3px}.cx{display:flex;flex-direction:column;gap:3px;width:78px;flex:none}
.cx-d{height:20px;line-height:20px;font-size:.62rem;color:var(--text-secondary);text-align:center}
.cx-c{height:34px;display:flex;align-items:center;justify-content:center}
.cx-t{height:20px;line-height:20px;border-radius:4px;text-align:center;font-size:.6rem;overflow:hidden;white-space:nowrap;background:var(--bg-primary);color:var(--text-primary)}
.cx-t.lvl{font-weight:700;border:1px solid var(--border)}.cx-t.imp{color:#1d1d1f;font-weight:700}
.ctx{width:100%;border-collapse:collapse;font-size:.84rem}.ctx th{font-size:.66rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-secondary);text-align:left;padding:.35rem .5rem;border-bottom:1px solid var(--border)}
.ctx td{padding:.42rem .5rem;border-bottom:1px solid var(--border);vertical-align:middle}.ctx tr.sec td{background:var(--bg-primary);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-secondary);font-weight:600}
.ctx tr.low td{opacity:.55}
.stack{display:flex;height:9px;border-radius:3px;overflow:hidden;width:150px;background:var(--bg-tertiary);margin-bottom:2px}.stack i{display:block;height:100%}
.cc{display:block;border:1px solid var(--border);border-radius:10px;padding:.35rem .65rem;margin:0 0 .4rem 0;font-size:.78rem}
.leg{display:flex;gap:1rem;flex-wrap:wrap;font-size:.74rem;color:var(--text-secondary);margin-top:.6rem}.leg i{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:.3rem}
'''
CSS += "".join(CSS_CR) + dyn + "</style>"
warn = (f'<div class="warn"><p><b>Qué cambió (26/11/2026).</b> Recalculado con 2026 completo (306 partidos, 17 jornadas por torneo). '
        f'(1) «Partidos que le quedan» sale del calendario de cada equipo, no de «equipos − 1». '
        f'(2) La probabilidad se calcula tras cada partido del equipo (eje: partidos jugados), con Elo y 3.000 simulaciones; parámetros: K {P["k"]:g}, ventaja de local {P["home"]:g}, altitud {P["altitude"]:g} puntos Elo por cada 1.000 m. '
        f'(3) «Fuera de alcance» solo si ni siquiera llegaba a {FLOOR_THRESHOLD:.0f} pts (el campeón más bajo observado); el asterisco marca los partidos que con 40 habrían salido «Fuera de alcance». '
        f'(4) La altura va en metros y se compara con la sede habitual del equipo, no es un sí/no. (5) xG propio (modelo GroneStats).</p>'
        f'<p><b>Límites.</b> El umbral de 40 es la media de los campeones de 10 torneos (rango 37–42): el Clausura 2026 lo ganó Sport Huancayo con 37. La probabilidad no ve lesiones ni plantillas. '
        f'La formación es la que declara SofaScore para cada partido; se cruza con la posición (G, D, M, F) de los 11 titulares y ⚠ marca los partidos donde el número de defensas de los titulares no coincide con el de la formación declarada (la declarada manda). Con pocos partidos por contexto (⚠ en la tabla) las medias son ruido.</p></div>')
page = f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GroneStats · Camino al título · Liga 1 {SEASON}</title>{CSS}</head>
<body><div class="page"><h2>Camino al título y contexto del partido · por equipo <span class="dim">(v4)</span></h2>
<p class="subtitle">Liga 1 {SEASON} · {len(IDS)} equipos · Apertura y Clausura. Elige un equipo: todo lo de abajo se adapta a él (el nivel de cada rival sale en texto, no en colores).</p>
{warn}{"".join(league_block(t) for t in TOURS)}
<div class="wrap">{sel}<div class="dim">Equipo:</div><div class="sel">{labs}</div>{"".join(SECTIONS)}{legend}</div></div></body></html>'''
OUT.write_text(page, encoding="utf-8")

VOID = {"img", "input", "br", "hr", "meta", "link"}


class Chk(HTMLParser):
    def __init__(s):
        super().__init__()
        s.st, s.err = [], []

    def handle_starttag(s, t, a):
        if t not in VOID:
            s.st.append(t)

    def handle_startendtag(s, t, a):
        pass

    def handle_endtag(s, t):
        if t in VOID:
            return
        if not s.st or s.st[-1] != t:
            s.err.append((t, s.st[-3:]))
        else:
            s.st.pop()


c = Chk()
c.feed(re.sub(r"<style>.*?</style>", "", page, flags=re.S))
c.close()
bad = 0
for m_ in re.finditer(r"<svg.*?</svg>", page, flags=re.S):
    try:
        ET.fromstring(m_.group(0))
    except ET.ParseError as ex:
        bad += 1
        print("SVG mal formado:", ex)
print(f"escrito {OUT.name}: {len(page)/1024/1024:.2f} MB | sin cerrar={len(c.st)} | cierres incorrectos={len(c.err)} {c.err[:2]} | SVG inválidos={bad} | secciones={len(SECTIONS)}")
