"""Mockup 3 v3: pantalla por equipo (todos los equipos de la liga 2025): nivel del rival en TEXTO, escudos en varios tamaños,
importancia (derrotas permitidas) y probabilidad de campeonar por jornada. Material de diseño desechable."""
import sys, io, base64, html, re, pickle
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from champ_state import team_states, BANDS, T_REF, THRESH

sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(r"C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz")
SCREEN = REPO / ".superpowers/brainstorm/792-1795652716/content"
SP = Path(__file__).parent
D = REPO / "gronestats/data/Liga 1 Peru/2025/dashboard/current"
CREST = REPO / "gronestats/images/teams"
SEASON, MIN_N, DEFAULT = 2025, 6, 2311
SHORT = ["Asegurado", "Baja", "Media", "Alta", "Crítica", "Fuera de alcance"]

ap = pd.read_parquet(D / "average_positions.parquet"); ma = pd.read_parquet(D / "matches.parquet")
ts = pd.read_parquet(D / "team_stats.parquet"); te = pd.read_parquet(D / "teams.parquet").set_index("team_id")
TSI = ts[ts.PERIOD.astype(str).str.upper() == "ALL"].drop_duplicates(["MATCH_ID", "KEY"]).set_index(["MATCH_ID", "KEY"])
PR = pickle.load(open(SP / "title_probs_120.pkl", "rb")); P_TEAMS, P_DF = PR["out"][(SEASON, "A")]; P_COMP = PR["comp"]
print("parámetros del modelo (K,H,A,rho,pdmax):", PR["params"], "| completitud:", {f"{k[0]}{k[1]}": v for k, v in P_COMP.items() if k[0] == SEASON})

def tsv(mid, key, side):
    try: v = TSI.loc[(mid, key)][("HOME" if side == "h" else "AWAY") + "VALUE"]
    except KeyError: return np.nan
    return float(v) if pd.notna(v) else np.nan

# ---------- equipos del torneo
reg = ma[ma.tournament.astype(str).str.contains("Apertura|Clausura") & ma.home_score.notna()]
IDS = sorted(set(reg.home_id.astype(int)) | set(reg.away_id.astype(int)), key=lambda t: str(te.loc[t, "short_name"]))
nm = lambda t: str(te.loc[t, "short_name"]); lvl = lambda t: str(te.loc[t, "competitiveness_level"]); alt = lambda t: bool(te.loc[t, "is_altitude_team"])
print(f"{len(IDS)} equipos con partidos de Apertura/Clausura {SEASON}; niveles:", pd.Series([lvl(t) for t in IDS]).value_counts().to_dict())

# ---------- escudos: cuadrados, SIN ampliar nunca (se reduce siempre desde el original), 1x/2x/3x por tamaño de uso
_c = {}
def crest_uri(tid, px):
    k = (tid, px)
    if k in _c: return _c[k]
    f = CREST / f"{tid}.png"
    if not f.exists(): _c[k] = None; return None
    im = Image.open(f).convert("RGBA"); w, h = im.size; s = max(w, h)
    if w != h:                                                   # normalizar a cuadrado con transparencia (no altera píxeles)
        sq = Image.new("RGBA", (s, s), (0, 0, 0, 0)); sq.paste(im, ((s - w) // 2, (s - h) // 2)); im = sq
    side = min(px, im.width)                                     # nunca ampliar
    out = im.resize((side, side), Image.LANCZOS); buf = io.BytesIO(); out.save(buf, "PNG", optimize=True)
    _c[k] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(); return _c[k]
CSS_CR, no_crest = [], []
for t in IDS:
    for base in (28, 44):
        u = [crest_uri(t, base * m) for m in (1, 2, 3)]
        if u[0] is None: no_crest.append(t); break
        CSS_CR.append(f".cr{base}-{t}{{width:{base}px;height:{base}px;background:center/contain no-repeat;background-image:url({u[0]});background-image:image-set(url({u[0]}) 1x,url({u[1]}) 2x,url({u[2]}) 3x)}}")
print("equipos SIN escudo:", no_crest, "| CSS de escudos: %.0f KB" % (sum(map(len, CSS_CR)) / 1024))
crest = lambda t, base=28: f'<span class="cr{base}-{t} crest" role="img" aria-label="Escudo de {html.escape(nm(t))}"></span>'

# ---------- tabla del Apertura 2025 (posición final, puntos)
a = reg[reg.tournament.astype(str).str.contains("Apertura") & ~reg.tournament.astype(str).str.contains("Final")]
rows = []
for r in a.itertuples():
    for tid, gf, ga in ((r.home_id, r.home_score, r.away_score), (r.away_id, r.away_score, r.home_score)):
        rows.append((int(tid), 3 if gf > ga else 1 if gf == ga else 0, gf - ga))
ST = pd.DataFrame(rows, columns=["t", "pts", "gd"]).groupby("t").sum().sort_values(["pts", "gd"], ascending=False); ST["pos"] = range(1, len(ST) + 1)

# ---------- formas de datos por equipo
def fam(lab): return {3: "#af52de", 4: "#0a84ff", 5: "#ff9f0a"}.get(int(lab.split("-")[0]), "#8e8e93")
LVL_ORDER = ("Candidato", "Competitivo", "Promedio", "Descenso")

def team_matches(tid):
    S = team_states(SEASON, tid, T_REF); SI = S.set_index("mid")
    tm = ma[((ma.home_id == tid) | (ma.away_id == tid)) & ma.match_id.isin(S.mid)].copy()
    tm["dt"] = pd.to_datetime(tm.fecha, format="%d/%m/%Y %H:%M", errors="coerce"); tm = tm.sort_values("dt")
    st = ap[(ap.team_id == tid) & (ap.is_starter == True)]; G = {int(m): g for m, g in st.groupby("match_id")}; M = []
    for r in tm.itertuples():
        mid = int(r.match_id)
        if mid not in G or len(G[mid]) != 11: continue
        home = r.home_id == tid; side, opp = ("h", "a") if home else ("a", "h"); rid = int(r.away_id if home else r.home_id)
        gf, ga = (r.home_score, r.away_score) if home else (r.away_score, r.home_score)
        c = G[mid].position.value_counts(); lab = f"{c.get('D',0)}-{c.get('M',0)}-{c.get('F',0)}"
        out = G[mid][G[mid].position != "G"].sort_values("average_x"); s = SI.loc[mid]
        ok = bool(s.complete) and s.band == s.band and s.band is not None
        M.append(dict(mid=mid, dt=r.dt, home=home, rid=rid, rival=nm(rid), level=lvl(rid), alt=alt(int(r.home_id)), lab=lab, gf=int(gf), ga=int(ga),
                      pts=3 if gf > ga else 1 if gf == ga else 0, defl=float(out.average_x.values[:4].mean() * 1.05), poss=tsv(mid, "ballPossession", side),
                      xgf=tsv(mid, "expectedGoals", side), xga=tsv(mid, "expectedGoals", opp), band=int(s.band) if ok else -1,
                      lives=(int(s.lives) if (ok and s.lives == s.lives and s.lives is not None) else None), tour=s.tour, p_before=int(s.p_before), rem=int(s.rem), needed=float(s.needed)))
    return S, pd.DataFrame(M)

def idx_chart(S):
    W, H, pl, pr, pt, pb = 320, 150, 30, 10, 10, 22
    X = lambda k, R: pl + (k / R) * (W - pl - pr); Y = lambda v: pt + (1.05 - v) * (H - pt - pb) / 1.05
    g = [f'<line x1="{pl}" y1="{Y(1):.1f}" x2="{W-pr}" y2="{Y(1):.1f}" stroke="var(--success)" stroke-dasharray="4 3"/><text x="{W-pr}" y="{Y(1)-3:.1f}" font-size="8" text-anchor="end" fill="var(--success)">umbral: {T_REF:.0f} pts</text>']
    for v in (0, .5): g.append(f'<text x="{pl-4}" y="{Y(v)+3:.1f}" font-size="8" fill="var(--text-secondary)" text-anchor="end">{v:.1f}</text><line x1="{pl}" y1="{Y(v):.1f}" x2="{W-pr}" y2="{Y(v):.1f}" stroke="var(--border)" stroke-width=".6"/>')
    R0 = int(S.R.max()); g.append(f'<line x1="{X(0,R0):.1f}" y1="{Y(0):.1f}" x2="{X(R0,R0):.1f}" y2="{Y(1):.1f}" stroke="var(--text-secondary)" stroke-dasharray="1.5 3"/>')
    note = []
    for tour, col in (("Apertura", "var(--accent)"), ("Clausura", "#ff9500")):
        s = S[S.tour == tour]
        if s.empty: continue
        if not bool(s.complete.iloc[0]): note.append(f"{tour}: datos incompletos"); continue
        pts = [(0, 0.0)] + [(int(k) + 1, float(v)) for k, v in zip(s.k, s.idx_after)]
        g.append(f'<polyline points="{" ".join(f"{X(k,R0):.1f},{Y(v):.1f}" for k, v in pts)}" fill="none" stroke="{col}" stroke-width="2.2"/>')
        k_, v_ = pts[-1]; g.append(f'<circle cx="{X(k_,R0):.1f}" cy="{Y(v_):.1f}" r="3" fill="{col}"/><text x="{X(k_,R0)-4:.1f}" y="{Y(v_)+11:.1f}" font-size="8" text-anchor="end" fill="{col}">{tour} · {int(s.p_after.iloc[-1])} pts</text>')
    return f'<svg viewBox="0 0 {W} {H}" width="{W}" xmlns="http://www.w3.org/2000/svg">{"".join(g)}</svg>', note

def prob_chart(tid, color):
    W, H, pl, pr, pt, pb = 320, 150, 32, 10, 10, 22
    col = P_TEAMS.index(tid); s = P_DF[col].values * 100; R = len(s) - 1
    X = lambda k: pl + k / R * (W - pl - pr); Y = lambda v: pt + (100 - v) * (H - pt - pb) / 100
    g = []
    for v in (0, 25, 50, 75, 100): g.append(f'<line x1="{pl}" y1="{Y(v):.1f}" x2="{W-pr}" y2="{Y(v):.1f}" stroke="var(--border)" stroke-width=".6"/><text x="{pl-4}" y="{Y(v)+3:.1f}" font-size="8" fill="var(--text-secondary)" text-anchor="end">{v}%</text>')
    g.append(f'<polyline points="{" ".join(f"{X(k):.1f},{Y(v):.1f}" for k, v in enumerate(s))}" fill="none" stroke="{color}" stroke-width="2.4" stroke-linejoin="round"/>')
    pk = int(s.argmax()); g.append(f'<circle cx="{X(pk):.1f}" cy="{Y(s[pk]):.1f}" r="3.2" fill="{color}"/><text x="{X(pk):.1f}" y="{Y(s[pk])-6:.1f}" font-size="8.5" text-anchor="middle" fill="var(--text-primary)">{s[pk]:.0f}% (J{pk})</text>')
    g.append(f'<text x="{pl}" y="{H-6}" font-size="8" fill="var(--text-secondary)">jornada 0</text><text x="{W-pr}" y="{H-6}" font-size="8" text-anchor="end" fill="var(--text-secondary)">{R}</text>')
    return f'<svg viewBox="0 0 {W} {H}" width="{W}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Probabilidad de campeonar por jornada">{"".join(g)}</svg>', s

COL = {t: (m.group(0) if (m := re.search(r"#[0-9a-fA-F]{6}", str(te.loc[t, "team_colors"]))) else "#0a84ff") for t in IDS}

# ---------- sección de un equipo
def section(tid):
    S, df = team_matches(tid); N = len(df); items = []
    for i, m in enumerate(df.itertuples(), 1):
        b = m.band; imp = "Sin datos completos" if b < 0 else SHORT[b] + (f" ({int(m.lives)})" if (m.lives is not None and b in (1, 2, 3, 4)) else "")
        det = (f'{m.dt:%d/%m} {"Local" if m.home else "Visita"} vs {m.rival} ({m.level}{", en altura" if m.alt else ""}) {m.gf}-{m.ga} · {m.lab} · {m.tour}: tenía {m.p_before} pts, '
               f'necesitaba {m.needed:.0f} en {m.rem} partidos' if b >= 0 else f'{m.dt:%d/%m} vs {m.rival} · torneo con partidos faltantes en el bundle')
        res = ("G" if m.pts == 3 else "E" if m.pts == 1 else "P") + f" {m.gf}-{m.ga}"; rc = "#34c759" if m.pts == 3 else "#8e8e93" if m.pts == 1 else "#ff3b30"
        bc = "repeating-linear-gradient(45deg,transparent 0 3px,var(--border) 3px 4px)" if b < 0 else BANDS[b][1]
        items.append(f'<div class="cx" title="{html.escape(det)}"><div class="cx-d">{m.dt:%d/%m}</div><div class="cx-c">{crest(m.rid, 28)}</div>'
                     f'<div class="cx-t lvl">{html.escape(m.level)}</div><div class="cx-t">{"Local" if m.home else "Visita"}</div><div class="cx-t">{"Altura" if m.alt else "Sin altura"}</div>'
                     f'<div class="cx-t" style="background:{rc};color:#fff;font-weight:700">{res}</div><div class="cx-t" style="background:{fam(m.lab)};color:#fff;font-weight:700">{m.lab}</div>'
                     f'<div class="cx-t imp" style="background:{bc}">{html.escape(imp)}</div></div>')
    strip = ('<div class="cx-wrap"><div class="cx-lbls"><span>Fecha</span><span style="height:34px;line-height:34px">Rival</span><span>Nivel del rival</span><span>Sede</span><span>Altura</span>'
             '<span>Resultado</span><span>Formación (D-M-F)</span><span>Importancia (derrotas)</span></div>' + f'<div class="cx-row">{"".join(items)}</div></div>')
    # tabla por contexto
    def grp(mask, label, note=""):
        s = df[mask]; n = len(s)
        if n == 0: return ""
        top = s.lab.value_counts(); low = n < MIN_N
        bars = "".join(f'<i style="width:{100*c/n:.0f}%;background:{fam(l)};opacity:{1-.13*k:.2f}" title="{l}: {c} de {n}"></i>' for k, (l, c) in enumerate(top.head(4).items()))
        f = lambda v, d=1: "—" if pd.isna(v) else f"{v:.{d}f}"          # xG puede faltar en algunos partidos
        return (f'<tr{" class=low" if low else ""}><td><b>{label}</b>{f"<br><span class=dim>{note}</span>" if note else ""}</td><td>{n}{" ⚠" if low else ""}</td>'
                f'<td><div class="stack">{bars}</div><span class="dim">{top.index[0]} en {int(top.iloc[0])} de {n} ({100*int(top.iloc[0])/n:.0f} %)</span></td>'
                f'<td>{f(s.defl.mean(),0)} m</td><td>{f(s.poss.mean(),0)} %</td><td>{f(s.xgf.mean(),2)} · {f(s.xga.mean(),2)}</td><td>{f(s.pts.mean(),2)}</td></tr>')
    T = ['<tr class="sec"><td colspan="7">Por importancia para el título (derrotas que aún podía permitirse)</td></tr>']
    for b, (l, c) in enumerate(BANDS): T.append(grp(df.band == b, l))
    T.append('<tr class="sec"><td colspan="7">Por nivel del rival</td></tr>')
    for l in LVL_ORDER: T.append(grp(df.level == l, l))
    T.append('<tr class="sec"><td colspan="7">Por altura de la sede</td></tr>'); T.append(grp(df.alt, "Juega en altura")); T.append(grp(~df.alt, "Juega sin altura"))
    T.append('<tr class="sec"><td colspan="7">Por localía</td></tr>'); T.append(grp(df.home, "Local")); T.append(grp(~df.home, "Visita"))
    table = ('<table class="ctx"><thead><tr><th>Contexto</th><th>PJ</th><th>Formación más usada</th><th>Línea def.</th><th>Posesión</th><th>xG fav · contra</th><th>Pts/PJ</th></tr></thead>'
             f'<tbody>{"".join(T)}</tbody></table>')
    # probabilidad y índice
    pc, pser = prob_chart(tid, COL[tid]); ic, inote = idx_chart(S)
    pos = ST.loc[tid] if tid in ST.index else None; hi = df[df.band.isin([3, 4])]
    sens = {T_: int(team_states(SEASON, tid, T_).query("complete").band.isin([3, 4]).sum()) for T_ in (min(THRESH), T_REF, max(THRESH))}
    head = (f'<div class="th">{crest(tid, 44)}<div><div class="tn">{html.escape(str(te.loc[tid, "full_name"]))}</div>'
            f'<div class="dim">Nivel de competitividad: <b>{lvl(tid)}</b> · {"Sede en altura" if alt(tid) else "Sede sin altura"}'
            + (f' · Apertura {SEASON}: <b>{int(pos.pos)}.º</b> con {int(pos.pts)} pts' if pos is not None else '') + '</div></div></div>')
    probs = (f'<div class="row2"><div><div class="dim" style="margin-bottom:.3rem">Probabilidad de campeonar · Apertura {SEASON}</div>{pc}'
             f'<div class="dim" style="max-width:320px">Inicio {pser[0]:.0f} % · máximo {pser.max():.0f} % (J{int(pser.argmax())}) · tras J15: {pser[min(15, len(pser)-1)]:.0f} %. '
             f'<b>Clausura {SEASON}:</b> no calculable, el bundle trae {P_COMP[(SEASON,"C")][0]} de {P_COMP[(SEASON,"C")][1]} partidos.</div></div>'
             f'<div><div class="dim" style="margin-bottom:.3rem">Índice del Campeón por jornada (puntos ÷ umbral)</div>{ic}'
             f'<div class="dim" style="max-width:320px">Punteada gris = ritmo ideal.{" " + "; ".join(inote) + "." if inote else ""}</div></div>'
             f'<div style="flex:1;min-width:240px"><div class="dim" style="margin-bottom:.3rem">Lectura rápida</div>'
             f'<span class="cc"><b>{len(hi)}</b> partidos de importancia alta o crítica: <b>{int(hi.alt.sum())}</b> en altura · <b>{int((hi.level=="Candidato").sum())}</b> contra Candidatos</span>'
             f'<span class="cc">Umbral {min(THRESH)} / {T_REF:.0f} / {max(THRESH)} pts → <b>{sens[min(THRESH)]}</b> / <b>{sens[T_REF]}</b> / <b>{sens[max(THRESH)]}</b> partidos alta o crítica</span></div></div>')
    return (f'<div class="team t-{tid}">{head}{probs}<div class="box" style="margin-top:1rem"><div class="dim" style="margin-bottom:.5rem">Evolución partido a partido ({N} partidos)</div>{strip}</div>'
            f'<div class="box"><div class="dim" style="margin-bottom:.5rem">Cómo cambia el juego según el contexto</div>{table}'
            f'<div class="dim" style="margin-top:.5rem">⚠ = menos de {MIN_N} partidos. Los contextos se solapan. La importancia depende de los resultados previos, así que «Pts/PJ» por banda está en parte condicionado por la racha. '
            f'Un torneo con partidos faltantes en el bundle se marca «Sin datos completos» y no entra en la tabla.</div></div></div>')

# ---------- vista de toda la liga: curvas de los 19 equipos con escudos
def league_chart():
    W, H, pl, pr, pt, pb = 700, 280, 36, 14, 14, 24
    R = len(P_DF) - 1; X = lambda k: pl + k / R * (W - pl - pr); Y = lambda v: pt + (100 - v) * (H - pt - pb) / 100
    peak = {t: float(P_DF[P_TEAMS.index(t)].max() * 100) for t in IDS if t in P_TEAMS}; top = sorted(peak, key=lambda t: -peak[t])[:6]
    g = []
    for v in (0, 25, 50, 75, 100): g.append(f'<line x1="{pl}" y1="{Y(v):.1f}" x2="{W-pr}" y2="{Y(v):.1f}" stroke="var(--border)" stroke-width=".6"/><text x="{pl-5}" y="{Y(v)+3:.1f}" font-size="9" fill="var(--text-secondary)" text-anchor="end">{v}%</text>')
    for t in IDS:
        if t in P_TEAMS and t not in top:
            s = P_DF[P_TEAMS.index(t)].values * 100; g.append(f'<polyline points="{" ".join(f"{X(k):.1f},{Y(v):.1f}" for k, v in enumerate(s))}" fill="none" stroke="var(--text-tertiary)" stroke-width="1" stroke-opacity=".55"/>')
    for t in top:
        s = P_DF[P_TEAMS.index(t)].values * 100; g.append(f'<polyline points="{" ".join(f"{X(k):.1f},{Y(v):.1f}" for k, v in enumerate(s))}" fill="none" stroke="{COL[t]}" stroke-width="2.4" stroke-linejoin="round"/>')
    for t in top:
        s = P_DF[P_TEAMS.index(t)].values * 100; k = int(s.argmax()); u = crest_uri(t, 66)
        g.append((f'<image href="{u}" x="{X(k)-11:.1f}" y="{Y(s[k])-11:.1f}" width="22" height="22"/>') if u else f'<circle cx="{X(k):.1f}" cy="{Y(s[k]):.1f}" r="5" fill="{COL[t]}"/>')
    g.append(f'<text x="{pl}" y="{H-6}" font-size="9" fill="var(--text-secondary)">jornada 0</text><text x="{W-pr}" y="{H-6}" font-size="9" text-anchor="end" fill="var(--text-secondary)">jornada {R}</text>')
    svg = f'<svg viewBox="0 0 {W} {H}" width="{W}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Probabilidad de campeonar por jornada, todos los equipos">{"".join(g)}</svg>'
    order = sorted(peak, key=lambda t: -peak[t]); rows = []
    for t in order:
        s = P_DF[P_TEAMS.index(t)].values * 100; pos = ST.loc[t] if t in ST.index else None
        rows.append(f'<tr><td>{crest(t, 28)}<b style="margin-left:.5rem">{html.escape(nm(t))}</b></td><td>{lvl(t)}</td>' + "".join(f'<td>{s[min(k, len(s)-1)]:.0f} %</td>' for k in (0, 6, 9, 12, 15))
                    + f'<td>{int(pos.pos)}.º · {int(pos.pts)} pts</td></tr>')
    tab = ('<table class="ctx"><thead><tr><th>Equipo</th><th>Nivel</th><th>Inicio</th><th>Tras J6</th><th>Tras J9</th><th>Tras J12</th><th>Tras J15</th><th>Final</th></tr></thead>'
           f'<tbody>{"".join(rows)}</tbody></table>')
    return svg, tab

lsvg, ltab = league_chart()
SECTIONS = [section(t) for t in IDS]
sel = "".join(f'<input type="radio" name="tm" id="sel-{t}" class="mk-hide"{" checked" if t == DEFAULT else ""}>' for t in IDS)
labs = "".join(f'<label for="sel-{t}" class="selb">{crest(t, 44)}<span><b>{html.escape(nm(t))}</b><br><small>{lvl(t)}</small></span></label>' for t in IDS)
dyn = "".join(f".wrap:has(#sel-{t}:checked) .t-{t}{{display:block}}.wrap:has(#sel-{t}:checked) label[for=sel-{t}]{{outline:2px solid var(--accent);background:var(--selected-bg)}}" for t in IDS)
legend = ('<div class="leg"><span><i style="background:#af52de"></i>3 defensas</span><span><i style="background:#0a84ff"></i>4 defensas</span><span><i style="background:#ff9f0a"></i>5 defensas</span>'
          + "".join(f'<span><i style="background:{c}"></i>{l}</span>' for l, c in BANDS) + '<span>El número entre paréntesis = derrotas que aún podía permitirse</span></div>')

CSS = '''<style>
.mk-hide{position:absolute;opacity:0;pointer-events:none}
.dim{color:var(--text-secondary);font-size:.78rem}.dim small{font-size:.7rem}
.box{background:var(--bg-secondary);border:1px solid var(--border);border-radius:12px;padding:1.1rem 1.25rem;margin-bottom:1.2rem}
.warn{border-left:3px solid var(--warning);background:var(--bg-primary);padding:.6rem .9rem;border-radius:0 8px 8px 0;font-size:.82rem;margin:.4rem 0 1rem}
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
page = f'''{CSS}
<h2>3 · Camino al título y contexto del partido · por equipo <span class="dim">(v3)</span></h2>
<p class="subtitle">Liga 1 {SEASON} · {len(IDS)} equipos. Elige un equipo: todo lo de abajo se adapta a él (el nivel de cada rival sale en texto, no en colores).</p>
<div class="warn"><b>Correcciones y límites.</b> (1) Encontré un error mío en la importancia: con 19 equipos hay 19 rondas pero cada equipo juega 18 partidos; ahora se usa «equipos − 1». Los números de las bandas cambian respecto a la versión anterior (en Alianza Lima 2025: 10 baja · 7 media · 2 alta · 5 crítica · 11 fuera de alcance). (2) El bundle de Clausura {SEASON} trae {P_COMP[(SEASON,"C")][0]} de {P_COMP[(SEASON,"C")][1]} partidos, así que ese torneo se marca «sin datos completos» y no se calcula; el Apertura sí está completo. (3) La probabilidad sale de un modelo Elo simulado (Monte Carlo) con ajuste de un solo parámetro en 8 torneos: sirve para ver tendencias, no es una cifra exacta.</div>
<div class="box"><div class="dim" style="margin-bottom:.4rem">Probabilidad de campeonar por jornada · Apertura {SEASON} · todos los equipos (escudo = punto de máxima probabilidad)</div>{lsvg}{ltab}</div>
<div class="wrap">{sel}<div class="dim">Equipo:</div><div class="sel">{labs}</div>{"".join(SECTIONS)}{legend}</div>'''

out = SCREEN / "pantalla-liga.html"; out.write_text(page, encoding="utf-8")
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
bad = 0
for m_ in re.finditer(r"<svg.*?</svg>", page, flags=re.S):
    try: ET.fromstring(m_.group(0))
    except ET.ParseError as ex: bad += 1; print("SVG mal formado:", ex)
print(f"escrito {out.name}: {len(page)/1024/1024:.2f} MB | sin cerrar={len(c.st)} | cierres incorrectos={len(c.err)} {c.err[:2]} | SVG inválidos={bad} | secciones={len(SECTIONS)}")
