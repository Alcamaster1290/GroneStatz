"""Prototipo: Elo walk-forward + Monte Carlo del torneo -> probabilidad de campeonar por jornada. Material de validación (scratchpad).
Orden temporal por (temporada, torneo, ronda): 2022-23 no traen fecha en el bundle. Limitación: un partido aplazado cuenta en su ronda."""
import sys, pickle, itertools
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(r"C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz")
BASE = REPO / "gronestats/data/Liga 1 Peru"
SIG = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0          # incertidumbre del rating (puntos Elo) en cada simulación
OUT = Path(rf"C:\Users\Alvaro\AppData\Local\Temp\claude\C--Users-Alvaro\7aa9f7eb-a5d4-4175-a966-e3e7260a7f9a\scratchpad\title_probs_{int(SIG)}.pkl")


def load():
    t1 = pd.read_excel(BASE / "1_Teams.xlsx").drop_duplicates("team_id")
    alt1 = {int(r.team_id): bool(r.altura_team) for r in t1.itertuples()}
    rows = []
    for s in range(2022, 2026):
        m = pd.read_parquet(BASE / str(s) / "dashboard/current/matches.parquet")
        tm = pd.read_parquet(BASE / str(s) / "dashboard/current/teams.parquet")
        alt = {int(r.team_id): (False if pd.isna(r.is_altitude_team) else bool(r.is_altitude_team)) for r in tm.itertuples()} if s >= 2024 else alt1
        m = m[m.tournament.astype(str).str.contains("Apertura|Clausura")].copy()
        m["season"] = s; m["tour"] = np.where(m.tournament.astype(str).str.contains("Apertura"), "A", "C")
        m["dt"] = pd.to_datetime(m.fecha, format="%d/%m/%Y %H:%M", errors="coerce")
        m["ah"] = m.home_id.astype(int).map(alt).fillna(False).astype(bool); m["aa"] = m.away_id.astype(int).map(alt).fillna(False).astype(bool)
        rows.append(m)
    M = pd.concat(rows)
    M["ord"] = M.season * 1000 + np.where(M.tour == "A", 0, 100) + M.round_number.astype(int)
    return M.sort_values(["ord", "dt"]).reset_index(drop=True)


def expected(rh, ra, h): return 1 / (1 + 10 ** (-(rh - ra + h) / 400))
def probs(e, pdmax):
    pdr = pdmax * 4 * e * (1 - e); return e - pdr / 2, pdr, 1 - e - pdr / 2
def gmult(gd): return 1.0 if gd <= 1 else 1.5 if gd == 2 else (11 + gd) / 8


class Elo:
    def __init__(s, K, H, A, rho, pdmax, init_new=1450): s.K, s.H, s.A, s.rho, s.pdmax, s.init, s.R, s.season = K, H, A, rho, pdmax, init_new, {}, None
    def new_season(s, season):
        if s.season is not None and season != s.season:
            for t in s.R: s.R[t] = s.R[t] * (1 - s.rho) + 1500 * s.rho
        s.season = season
    def p(s, h, a, ah, aa):
        rh, ra = s.R.setdefault(h, s.init), s.R.setdefault(a, s.init)
        return probs(expected(rh, ra, s.H + (s.A if (ah and not aa) else 0)), s.pdmax)
    def update(s, h, a, gh, ga, ah, aa):
        rh, ra = s.R.setdefault(h, s.init), s.R.setdefault(a, s.init)
        e = expected(rh, ra, s.H + (s.A if (ah and not aa) else 0)); sc = 1.0 if gh > ga else .5 if gh == ga else 0.0
        d = s.K * gmult(abs(gh - ga)) * (sc - e); s.R[h] = rh + d; s.R[a] = ra - d


def walk(M, K, H, A, rho, pdmax, eval_seasons):
    e = Elo(K, H, A, rho, pdmax); ll = []
    for r in M.itertuples():
        e.new_season(r.season)
        if pd.isna(r.home_score): continue
        h, a = int(r.home_id), int(r.away_id); ph, pd_, pa = e.p(h, a, r.ah, r.aa)
        if r.season in eval_seasons:
            o = ph if r.home_score > r.away_score else pd_ if r.home_score == r.away_score else pa; ll.append(-np.log(max(o, 1e-9)))
        e.update(h, a, r.home_score, r.away_score, r.ah, r.aa)
    return float(np.mean(ll)), e


M = load()
print("partidos:", len(M), "| con resultado:", int(M.home_score.notna().sum()), "| con fecha:", int(M.dt.notna().sum()))
comp = {}
for (s, t), g in M.groupby(["season", "tour"]):
    n_t = len(set(g.home_id) | set(g.away_id)); exp = n_t * (n_t - 1) // 2; comp[(s, t)] = (len(g), exp)
    print(f"  {s}{t}: equipos={n_t} partidos={len(g)}/{exp}{'  <-- INCOMPLETO' if len(g) < exp else ''}")

hist = M[(M.season <= 2024) & M.home_score.notna()]; fr = np.array([(hist.home_score > hist.away_score).mean(), (hist.home_score == hist.away_score).mean(), (hist.home_score < hist.away_score).mean()])
t25 = M[(M.season == 2025) & M.home_score.notna()]
base_ll = float(np.mean([-np.log(fr[0 if r.home_score > r.away_score else 1 if r.home_score == r.away_score else 2]) for r in t25.itertuples()]))
print(f"\nfrecuencias 2022-24: local {fr[0]:.3f} empate {fr[1]:.3f} visita {fr[2]:.3f} | log-loss de referencia en 2025 (sin ratings): {base_ll:.4f}")

grid = list(itertools.product((15, 20, 30, 40, 50), (70, 100, 130, 160), (0, 40, 80), (.10, .25), (.30, .32, .34)))
res = sorted(((walk(M, K, H, A, rho, pdm, {2023, 2024})[0], (K, H, A, rho, pdm)) for K, H, A, rho, pdm in grid))
best = res[0]; K, H, A, rho, pdm = best[1]
print(f"mejores parámetros (ajuste 2023-24; 2022 = calentamiento): K={K} H={H} altitud={A} rho={rho} pdmax={pdm} | log-loss: {best[0]:.4f}")
print("   (¿en el borde de la rejilla?)", "K" if K in (15, 50) else "", "H" if H in (70, 160) else "", "A" if A in (0, 80) else "")
oos = walk(M, K, H, A, rho, pdm, {2025})[0]; oos_noalt = walk(M, K, H, 0, rho, pdm, {2025})[0]
print(f"FUERA DE MUESTRA 2025: Elo={oos:.4f} | sin efecto altitud={oos_noalt:.4f} | referencia sin ratings={base_ll:.4f} | mejora vs referencia={(base_ll - oos) / base_ll * 100:+.2f} %")
ins_noalt = min(r for r in res if r[1][2] == 0)[0]
print(f"altitud: mejor ajuste 2023-24 con A=0: {ins_noalt:.4f} vs mejor global {best[0]:.4f}")


def margins(rng, n):
    u = rng.random(n); return np.where(u < .55, 1, np.where(u < .82, 2, 3))


def title_probs(M, season, tour, K, H, A, rho, pdm, nsim=4000, seed=7, sigma=0.0):
    rng = np.random.default_rng(seed); el = Elo(K, H, A, rho, pdm)
    T = M[(M.season == season) & (M.tour == tour)].sort_values(["round_number", "dt"])
    teams = sorted(set(T.home_id.astype(int)) | set(T.away_id.astype(int))); ix = {t: i for i, t in enumerate(teams)}; R = int(T.round_number.max())
    for r in M[M.ord < T.ord.min()].itertuples():
        el.new_season(r.season)
        if not pd.isna(r.home_score): el.update(int(r.home_id), int(r.away_id), r.home_score, r.away_score, r.ah, r.aa)
    el.new_season(season)
    pts = np.zeros(len(teams)); gd = np.zeros(len(teams)); res = {}; ptr = 0; Ts = list(T.itertuples())
    for k in range(0, R + 1):
        while ptr < len(Ts) and Ts[ptr].round_number <= k:
            r = Ts[ptr]; ptr += 1
            if pd.isna(r.home_score): continue
            h, a = ix[int(r.home_id)], ix[int(r.away_id)]
            if r.home_score > r.away_score: pts[h] += 3
            elif r.home_score == r.away_score: pts[h] += 1; pts[a] += 1
            else: pts[a] += 3
            gd[h] += r.home_score - r.away_score; gd[a] -= r.home_score - r.away_score
            el.update(int(r.home_id), int(r.away_id), r.home_score, r.away_score, r.ah, r.aa)
        P = np.tile(pts, (nsim, 1)); G = np.tile(gd, (nsim, 1))
        rb = np.array([el.R.setdefault(t, el.init) for t in teams]); Rs = rb + sigma * rng.standard_normal((nsim, len(teams)))
        for r in Ts[ptr:]:
            h, a = ix[int(r.home_id)], ix[int(r.away_id)]
            e = expected(Rs[:, h], Rs[:, a], el.H + (el.A if (r.ah and not r.aa) else 0)); pd_ = el.pdmax * 4 * e * (1 - e); ph = e - pd_ / 2
            u = rng.random(nsim); mg = margins(rng, nsim); hw = u < ph; dr = (u >= ph) & (u < ph + pd_); aw = ~(hw | dr)
            P[:, h] += 3 * hw + dr; P[:, a] += 3 * aw + dr; G[:, h] += mg * (hw * 1 - aw * 1); G[:, a] -= mg * (hw * 1 - aw * 1)
        champ = (P * 1e4 + G * 10 + rng.random(P.shape)).argmax(1)
        res[k] = np.bincount(champ, minlength=len(teams)) / nsim
    return teams, pd.DataFrame(res).T, pts.copy()


names = {}
for s in range(2022, 2026):
    for r in pd.read_parquet(BASE / str(s) / "dashboard/current/teams.parquet").itertuples(): names[int(r.team_id)] = str(r.short_name)
CH = {(2022, "A"): "Melgar", (2022, "C"): "Alianza Lima", (2023, "A"): "Alianza Lima", (2023, "C"): "Universitario", (2024, "A"): "Universitario",
      (2024, "C"): "Universitario", (2025, "A"): "Universitario", (2025, "C"): "Universitario"}
out = {}; fav_hits = {6: 0, 9: 0, 12: 0, 15: 0}; n_t = 0; logs = []
print("\n=== probabilidad asignada al campeón REAL en cada jornada (parámetros ajustados con 2023-24; 2025 fuera de muestra) ===")
for (s, t), cname in CH.items():
    n_have, n_exp = comp[(s, t)]
    teams, df, final_pts = title_probs(M, s, t, K, H, A, rho, pdm, nsim=3000, sigma=SIG); out[(s, t)] = (teams, df)
    cid = next((tid for tid in teams if names.get(tid, "") == cname), None)           # coincidencia exacta (el prefijo confundía a las 3 'Alianza')
    if cid is None: print(s, t, "campeón no identificado"); continue
    col = teams.index(cid); R = len(df) - 1; n_t += 1
    for k in fav_hits: fav_hits[k] += int(teams[int(df.loc[k].values.argmax())] == cid)
    logs.append(df[col].values)
    print(f"{s}{t} {cname:13s} ({n_have}/{n_exp}) " + " ".join(f"J{k}:{float(df.loc[k, col])*100:4.0f}%" for k in (0, 6, 9, 12, 15, R - 1) if k in df.index) + f" | final={int(final_pts[col])} pts")
print("\nel favorito del modelo ES el campeón real en:", {f"J{k}": f"{v}/{n_t}" for k, v in fav_hits.items()})
LL = np.array([[max(l[k], 1 / 3000) for k in (6, 9, 12, 15)] for l in logs])
print(f"sigma={SIG:.0f}: log-score medio del campeón real en J6/J9/J12/J15 = {np.log(LL).mean(0).round(2).tolist()} | media={np.log(LL).mean():.3f} | p mínima asignada al campeón={LL.min():.4f} | #con p<1% = {int((LL < .01).sum())} de {LL.size}")
pickle.dump(dict(out=out, names=names, params=(K, H, A, rho, pdm), comp=comp), open(OUT, "wb"))
print("guardado:", OUT.name)
