"""Camino al titulo de cada torneo corto (Apertura y Clausura): importancia de cada partido y probabilidad de campeonar.

Importancia ("derrotas permitidas"): con ``needed`` puntos por conseguir y ``remaining`` partidos programados, la
holgura es ``3 * remaining - needed`` y cada derrota cuesta 3, asi que ``lives = floor(holgura / 3)``. Los partidos que le
quedan a un equipo son los de SU calendario, no "equipos - 1" ni rondas: con 19 equipos hay 19 rondas pero cada uno juega 18,
y Binacional (que dejo el Clausura 2025) tuvo 5.

Probabilidad: Elo partido a partido (en orden de fecha) y simulacion Monte Carlo del resto del torneo desde el estado en que
termino cada partido, con incertidumbre de rating ``sigma`` para no ser sobreconfiado. Un resultado administrativo (3-0 sin
partido) suma puntos pero no mueve ratings.

Uso:
    py -3.11 -m gronestats.analysis.title_race --out docs/recursos-dashboard/datos-de-apoyo/title-race
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from gronestats.analysis.match_status import is_annulled, is_official_award
from gronestats.analysis.standings import ADJUSTMENTS_FILE, load_adjustments, season_tables, tournament_table

REFERENCE_THRESHOLD = 40.0  # media de los puntos del campeon en 10 torneos (imagen "Puntos para ganar un torneo" y el Clausura 2026)
FLOOR_THRESHOLD = 37.0  # el campeon mas bajo observado: "Fuera de alcance" solo si ni siquiera llega a esto
BAND_NAMES = ["Asegurado", "Baja", "Media", "Alta", "Crítica", "Fuera de alcance"]
CHAMPION_POINTS_IMAGE = {  # puntos del campeon segun la imagen de Alvaro (2026-11-25); el Clausura 2026 se mide con los datos
    (2022, "Apertura"): 41, (2022, "Clausura"): 42, (2023, "Apertura"): 42, (2023, "Clausura"): 39,
    (2024, "Apertura"): 40, (2024, "Clausura"): 37, (2025, "Apertura"): 39, (2025, "Clausura"): 40, (2026, "Apertura"): 40,
}
MARGIN_PROBABILITIES = (0.55, 0.27, 0.18)  # el ganador gana por 1, 2 o 3 goles (solo desempata la diferencia de gol)


def tournament_of(name: object) -> str | None:
    """'Apertura' o 'Clausura'; la final, los playoffs y la promocion no son torneos cortos."""
    text = str(name)
    if any(word in text for word in ("Final", "Playoff", "Relegation")):
        return None
    return "Apertura" if "Apertura" in text else "Clausura" if "Clausura" in text else None


def parse_match_dates(series: pd.Series) -> pd.Series:
    """Fecha del bundle ('dd/mm/aaaa hh:mm', hora de Lima)."""
    return pd.to_datetime(series, format="%d/%m/%Y %H:%M", errors="coerce")


def band_of(needed: float, remaining: int) -> tuple[int | None, int | None]:
    """(indice en BAND_NAMES, derrotas permitidas). Sin partidos por jugar no hay importancia que medir."""
    if remaining <= 0:
        return None, None
    if needed <= 0:
        return 0, None
    lives = int(np.floor((3 * remaining - needed) / 3))
    if lives < 0:
        return 5, lives
    return (1 if lives >= 3 else 2 if lives == 2 else 3 if lives == 1 else 4), lives


def importance_band(points: float, remaining: int, threshold: float = REFERENCE_THRESHOLD, floor: float | None = FLOOR_THRESHOLD) -> tuple[int | None, int | None, float]:
    """(banda, derrotas permitidas, umbral usado). Con ``threshold`` fuera de alcance, se reintenta con ``floor``: un equipo
    que todavia puede llegar al campeon mas bajo observado no esta fuera (Sport Huancayo ganó el Clausura 2026 con 37)."""
    band, lives = band_of(threshold - points, remaining)
    if band == 5 and floor is not None and floor < threshold:
        floor_band, floor_lives = band_of(floor - points, remaining)
        if floor_band != 5:
            return floor_band, floor_lives, floor
    return band, lives, threshold


def match_importance(matches: pd.DataFrame, threshold: float = REFERENCE_THRESHOLD, floor_threshold: float | None = FLOOR_THRESHOLD) -> pd.DataFrame:
    """Una fila por equipo y partido jugado: estado del equipo justo antes del partido. ``matches_remaining`` incluye ese partido."""
    rows = []
    played = matches[matches["home_score"].notna() & matches["away_score"].notna()]
    for (season, tour), group in matches.groupby(["season", "tour"]):
        calendar = pd.concat(
            [group.assign(team_id=group["home_id"], gf=group["home_score"], ga=group["away_score"]), group.assign(team_id=group["away_id"], gf=group["away_score"], ga=group["home_score"])]
        )
        totals = calendar.groupby("team_id").size()  # partidos programados de cada equipo en el torneo
        for team_id, team in calendar[calendar["match_id"].isin(played["match_id"])].sort_values(["date", "match_id"]).groupby("team_id"):
            points = 0
            for position, match in enumerate(team.itertuples()):
                remaining = int(totals[team_id]) - position
                band, lives, used = importance_band(points, remaining, threshold, floor_threshold)
                needed = used - points
                rows.append(
                    {
                        "season": season, "tour": tour, "match_id": match.match_id, "round_number": match.round_number, "date": match.date, "team_id": team_id,
                        "matches_before": position, "points_before": points, "matches_remaining": remaining, "threshold_used": used, "points_needed": needed, "lives": lives,
                        "band": band, "band_name": BAND_NAMES[band] if band is not None else None,
                    }
                )
                points += 3 if match.gf > match.ga else 1 if match.gf == match.ga else 0
    frame = pd.DataFrame(rows)
    frame["band"] = frame["band"].astype("Int64")
    frame["lives"] = frame["lives"].astype("Int64")
    return frame


def champion_points_by_tournament(matches: pd.DataFrame, adjustments: pd.DataFrame | None = None) -> dict[tuple[int, str], tuple[int, int]]:
    """(season, torneo) -> (equipo campeon, sus puntos): la tabla oficial (puntos, diferencia de gol y goles a favor, con sus ajustes)."""
    champions = {}
    for (season, tour), group in matches.groupby(["season", "tour"]):
        table = tournament_table(group, adjustments, season=int(season), tournament=tour)
        champions[(int(season), tour)] = (int(table.iloc[0]["team_id"]), int(table.iloc[0]["pts"]))
    return champions


@dataclass(frozen=True)
class EloParams:
    k: float = 20
    home: float = 100
    altitude: float = 0  # puntos Elo por cada 1000 m que el estadio supera a la sede habitual del visitante
    regression: float = 0.25  # fraccion que cada rating vuelve a 1500 al empezar una temporada
    draw_max: float = 0.32  # probabilidad maxima de empate (equipos parejos)
    initial: float = 1450  # rating de un equipo que aun no se vio


def expected_score(rating_home: float | np.ndarray, rating_away: float | np.ndarray, advantage: float | np.ndarray) -> float | np.ndarray:
    return 1 / (1 + 10 ** (-(rating_home - rating_away + advantage) / 400))


def outcome_probabilities(expected: float | np.ndarray, draw_max: float) -> tuple:
    draw = draw_max * 4 * expected * (1 - expected)
    return expected - draw / 2, draw, 1 - expected - draw / 2


def goal_multiplier(goal_difference: int) -> float:
    return 1.0 if goal_difference <= 1 else 1.5 if goal_difference == 2 else (11 + goal_difference) / 8


def _advantage(params: EloParams, altitude_edge: float) -> float:
    return params.home + params.altitude * max(0.0, altitude_edge) / 1000


class Elo:
    def __init__(self, params: EloParams) -> None:
        self.params, self.ratings, self.season = params, {}, None

    def new_season(self, season: int) -> None:
        if self.season is not None and season != self.season:
            for team in self.ratings:
                self.ratings[team] = self.ratings[team] * (1 - self.params.regression) + 1500 * self.params.regression
        self.season = season

    def rating(self, team: int) -> float:
        return self.ratings.setdefault(team, self.params.initial)

    def outcome(self, home: int, away: int, altitude_edge: float = 0.0) -> tuple[float, float, float]:
        expected = expected_score(self.rating(home), self.rating(away), _advantage(self.params, altitude_edge))
        return outcome_probabilities(expected, self.params.draw_max)

    def update(self, home: int, away: int, home_score: float, away_score: float, altitude_edge: float = 0.0) -> None:
        rating_home, rating_away = self.rating(home), self.rating(away)
        expected = expected_score(rating_home, rating_away, _advantage(self.params, altitude_edge))
        actual = 1.0 if home_score > away_score else 0.5 if home_score == away_score else 0.0
        delta = self.params.k * goal_multiplier(int(abs(home_score - away_score))) * (actual - expected)
        self.ratings[home], self.ratings[away] = rating_home + delta, rating_away - delta


def _edge(row) -> float:
    value = getattr(row, "altitude_edge", 0.0)
    return 0.0 if pd.isna(value) else float(value)


def chronological(matches: pd.DataFrame) -> pd.DataFrame:
    return matches.sort_values(["date", "match_id"], kind="mergesort").reset_index(drop=True)


def walk_log_loss(matches: pd.DataFrame, params: EloParams, eval_seasons: Iterable[int]) -> float:
    """Pérdida logarítmica (resultado 1X2) del Elo partido a partido en las temporadas evaluadas."""
    elo, losses, evaluate = Elo(params), [], set(eval_seasons)
    for row in chronological(matches[matches["home_score"].notna() & ~matches["awarded"]]).itertuples():
        elo.new_season(row.season)
        home, away, edge = int(row.home_id), int(row.away_id), _edge(row)
        if row.season in evaluate:
            win, draw, lose = elo.outcome(home, away, edge)
            chosen = win if row.home_score > row.away_score else draw if row.home_score == row.away_score else lose
            losses.append(-np.log(max(chosen, 1e-9)))
        elo.update(home, away, row.home_score, row.away_score, edge)
    return float(np.mean(losses))


def default_grid(altitudes: Iterable[float] = (0, 30, 45, 60, 80, 100)) -> list[tuple]:
    """(k, ventaja de local, altitud por 1000 m, regresion a la media, empate maximo)."""
    return list(itertools.product((15, 20, 30, 40, 50), (50, 70, 100, 130, 160), altitudes, (0.0, 0.05, 0.10, 0.25), (0.30, 0.32, 0.34)))


def fit_params(matches: pd.DataFrame, fit_seasons: Iterable[int], grid: Iterable[tuple] | None = None) -> tuple[EloParams, float, list[tuple[float, EloParams]]]:
    """Busca los parametros que minimizan la perdida en ``fit_seasons`` (las anteriores calientan los ratings)."""
    grid = grid or default_grid()
    scored = sorted(
        ((walk_log_loss(matches, p, fit_seasons), p) for p in (EloParams(k, home, altitude, regression, draw_max) for k, home, altitude, regression, draw_max in grid)),
        key=lambda item: item[0],
    )
    return scored[0][1], scored[0][0], scored


def simulate_title_probabilities(matches: pd.DataFrame, params: EloParams, *, n_sim: int = 3000, sigma: float = 120.0, seed: int = 7, only: Iterable[tuple[int, str]] | None = None) -> pd.DataFrame:
    """Probabilidad de campeonar de cada equipo al terminar cada uno de sus partidos (``k`` = partidos jugados).

    Por torneo: una fila ``k = 0`` por equipo antes del primer partido y, tras cada partido jugado, una fila para
    cada uno de sus dos equipos con el estado del torneo en ese momento (puntos, rating y probabilidad)."""
    rng = np.random.default_rng(seed)
    ordered = chronological(matches)
    keys = sorted({(int(r.season), r.tour) for r in ordered.itertuples()}) if only is None else sorted(only)
    frames = [_simulate_tournament(ordered, season, tour, params, n_sim, sigma, rng) for season, tour in keys]
    return pd.concat(frames, ignore_index=True)


def _simulate_tournament(ordered: pd.DataFrame, season: int, tour: str, params: EloParams, n_sim: int, sigma: float, rng: np.random.Generator) -> pd.DataFrame:
    mine = ordered[(ordered["season"] == season) & (ordered["tour"] == tour)].reset_index(drop=True)
    teams = sorted(set(mine["home_id"].astype(int)) | set(mine["away_id"].astype(int)))
    index = {team: i for i, team in enumerate(teams)}
    elo, points, goal_diff, games = Elo(params), np.zeros(len(teams)), np.zeros(len(teams)), np.zeros(len(teams), dtype=int)
    first_key = (mine.iloc[0]["date"], mine.iloc[0]["match_id"])
    rows: list[dict] = []
    played_flags = (mine["home_score"].notna() & mine["away_score"].notna()).to_numpy()

    def snapshot(match_position: int | None, owners: list[int]) -> None:
        remaining = [mine.iloc[i] for i in range(len(mine)) if not (played_flags[i] and (match_position is not None and i <= match_position))]
        probabilities = _title_probabilities(remaining, index, elo, points, goal_diff, params, n_sim, sigma, rng)
        match_id = None if match_position is None else int(mine.iloc[match_position]["match_id"])
        for team in owners:
            rows.append(
                {
                    "season": season, "tour": tour, "match_id": match_id, "team_id": team, "k": int(games[index[team]]),
                    "p_title": float(probabilities[index[team]]), "points": int(points[index[team]]), "rating": float(elo.rating(team)),
                }
            )

    # Ratings: todo lo anterior al primer partido del torneo, en orden de fecha.
    pending_global = ordered[(ordered["date"] < first_key[0]) | ((ordered["date"] == first_key[0]) & (ordered["match_id"] < first_key[1]))]
    pending_global = pending_global[pending_global["home_score"].notna() & ~pending_global["awarded"]]
    for row in pending_global.itertuples():
        elo.new_season(row.season)
        elo.update(int(row.home_id), int(row.away_id), row.home_score, row.away_score, _edge(row))
    elo.new_season(season)
    for team in teams:
        elo.rating(team)
    snapshot(None, teams)

    for position, row in enumerate(mine.itertuples()):
        if not played_flags[position]:
            continue
        home, away = int(row.home_id), int(row.away_id)
        if not row.awarded:
            elo.update(home, away, row.home_score, row.away_score, _edge(row))
        h, a = index[home], index[away]
        points[h] += 3 if row.home_score > row.away_score else 1 if row.home_score == row.away_score else 0
        points[a] += 3 if row.away_score > row.home_score else 1 if row.home_score == row.away_score else 0
        goal_diff[h] += row.home_score - row.away_score
        goal_diff[a] -= row.home_score - row.away_score
        games[h] += 1
        games[a] += 1
        snapshot(position, [home, away])
    return pd.DataFrame(rows)


def _title_probabilities(remaining: list, index: dict[int, int], elo: Elo, points: np.ndarray, goal_diff: np.ndarray, params: EloParams, n_sim: int, sigma: float, rng: np.random.Generator) -> np.ndarray:
    n_teams = len(index)
    simulated_points = np.tile(points, (n_sim, 1))
    simulated_diff = np.tile(goal_diff, (n_sim, 1))
    base = np.array([elo.rating(team) for team in index])
    ratings = base + sigma * rng.standard_normal((n_sim, n_teams)) if sigma else np.tile(base, (n_sim, 1))
    for match in remaining:
        h, a = index[int(match["home_id"])], index[int(match["away_id"])]
        expected = expected_score(ratings[:, h], ratings[:, a], _advantage(params, 0.0 if pd.isna(match.get("altitude_edge", 0.0)) else float(match.get("altitude_edge", 0.0))))
        draw = params.draw_max * 4 * expected * (1 - expected)
        p_home = expected - draw / 2
        roll = rng.random(n_sim)
        home_win, away_win = roll < p_home, roll >= p_home + draw
        margin = rng.choice([1, 2, 3], size=n_sim, p=MARGIN_PROBABILITIES)
        simulated_points[:, h] += 3 * home_win + (~home_win & ~away_win)
        simulated_points[:, a] += 3 * away_win + (~home_win & ~away_win)
        swing = margin * (home_win.astype(int) - away_win.astype(int))
        simulated_diff[:, h] += swing
        simulated_diff[:, a] -= swing
    champion = (simulated_points * 1e4 + simulated_diff * 10 + rng.random(simulated_points.shape)).argmax(axis=1)
    return np.bincount(champion, minlength=n_teams) / n_sim


def load_matches(base_dir: Path, seasons: Iterable[int], altitude_table: Path | None = None) -> pd.DataFrame:
    """Partidos de los torneos cortos desde el bundle publicado, con fecha, estado administrativo (``status``) y ventaja de altitud."""
    frames = []
    for season in seasons:
        matches = pd.read_parquet(base_dir / str(season) / "dashboard" / "current" / "matches.parquet")
        matches = matches.assign(season=season, tour=matches["tournament"].map(tournament_of)).dropna(subset=["tour"])
        matches["date"] = parse_match_dates(matches["fecha"])
        if "status" in matches.columns:
            matches = matches[~is_annulled(matches["status"])].copy()  # anulado: no cuenta en puntos ni en el calendario de nadie
            matches["awarded"] = is_official_award(matches["status"])
        else:
            matches["awarded"] = False
        frames.append(matches)
    result = pd.concat(frames, ignore_index=True)
    result["altitude_edge"] = altitude_edge(result, altitude_table) if altitude_table is not None else 0.0
    return result


def team_names(base_dir: Path, seasons: Iterable[int]) -> dict[int, str]:
    names: dict[int, str] = {}
    for season in sorted(seasons):
        teams = pd.read_parquet(base_dir / str(season) / "dashboard" / "current" / "teams.parquet")
        names.update({int(row.team_id): str(row.short_name) for row in teams.itertuples()})
    return names


def altitude_edge(matches: pd.DataFrame, altitude_table: Path) -> pd.Series:
    """Metros que el estadio supera a la sede habitual del visitante (la mediana de la altitud de sus partidos de local)."""
    table = pd.read_csv(altitude_table, encoding="utf-8-sig")
    height = {(row.estadio, row.ciudad_en_el_maestro): row.altitud_msnm for row in table.itertuples()}
    venue = pd.Series([height.get((e, c)) for e, c in zip(matches["estadio"], matches["ciudad"])], index=matches.index, dtype=float)
    base = venue.groupby(matches["home_id"]).median()
    return (venue - matches["away_id"].map(base)).clip(lower=0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Importancia por partido y probabilidad de campeonar de los torneos cortos de la Liga 1.")
    parser.add_argument("--league", default="Liga 1 Peru")
    parser.add_argument("--seasons", default="2022,2023,2024,2025,2026")
    parser.add_argument("--fit-seasons", default="2023,2024,2025", help="Temporadas con las que se ajustan los parametros del Elo (2022 calienta).")
    parser.add_argument("--holdout-season", type=int, default=2026, help="Temporada que se evalua fuera de muestra.")
    parser.add_argument("--n-sim", type=int, default=3000)
    parser.add_argument("--sigma", type=float, default=120.0)
    parser.add_argument("--altitude-table", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(__file__).resolve().parents[1] / "data" / args.league
    seasons = [int(token) for token in args.seasons.split(",")]
    matches = load_matches(base_dir, seasons, args.altitude_table)
    args.out.mkdir(parents=True, exist_ok=True)

    names = team_names(base_dir, seasons)
    adjustments = load_adjustments(base_dir / ADJUSTMENTS_FILE)
    champions = champion_points_by_tournament(matches, adjustments)
    official_tables = pd.concat(
        [table.assign(season=season, torneo=name, team=lambda f: f["team_id"].map(names)) for season in seasons for name, table in season_tables(matches[matches["season"] == season], season, adjustments).items()],
        ignore_index=True,
    )
    official_tables.to_csv(args.out / "tablas_oficiales.csv", index=False, encoding="utf-8-sig")
    threshold_rows = []
    for (season, tour), (team, points) in sorted(champions.items()):
        image = CHAMPION_POINTS_IMAGE.get((season, tour))
        threshold_rows.append({"temporada": season, "torneo": tour, "campeon": names.get(team, team), "equipo_id": team, "puntos_datos": points, "puntos_imagen": image, "coincide": None if image is None else image == points})
    thresholds = pd.DataFrame(threshold_rows)
    thresholds.to_csv(args.out / "umbral_campeon_medido.csv", index=False, encoding="utf-8-sig")
    print("=== puntos del campeon: datos contra la imagen ===")
    print(thresholds.to_string(index=False))

    importance = match_importance(matches).assign(team_name=lambda frame: frame["team_id"].map(names))
    importance.to_parquet(args.out / "importancia_equipo_partido.parquet", index=False)
    importance.to_csv(args.out / "importancia_equipo_partido.csv", index=False, encoding="utf-8-sig")
    print("\n=== bandas de importancia (partidos de equipo, umbral %.0f, piso %.0f para «Fuera de alcance») ===" % (REFERENCE_THRESHOLD, FLOOR_THRESHOLD))
    print(importance.groupby("band_name", dropna=False).size().to_string())
    print("   rescatados del 'Fuera de alcance' por el piso:", int((importance["threshold_used"] != REFERENCE_THRESHOLD).sum()))
    sensitivity = {
        f"umbral {threshold}": match_importance(matches, threshold=threshold, floor_threshold=None).groupby("band_name", dropna=False).size() for threshold in (37, 40, 42)
    }
    print("\n=== sensibilidad al umbral, sin piso (partidos de equipo por banda) ===")
    print(pd.DataFrame(sensitivity).reindex(BAND_NAMES).to_string())

    fit_seasons = [int(token) for token in args.fit_seasons.split(",")]
    best, in_sample, _ = fit_params(matches, fit_seasons)
    print(f"\nparametros (ajuste {fit_seasons}): {asdict(best)} | perdida {in_sample:.4f}")
    edge = {name: (min(values), max(values)) for name, values in zip(("k", "home", "altitude", "regression", "draw_max"), zip(*default_grid()))}
    print("   en el borde de la rejilla:", [name for name, (low, high) in edge.items() if asdict(best)[name] in (low, high) and low != high] or "ninguno")
    print("\n=== fuera de muestra: Elo con altitud contra Elo sin altitud (reajustado) contra frecuencias sin ratings ===")
    checks = {}
    for holdout in sorted({2025, args.holdout_season}):
        fit = [season for season in fit_seasons if season < holdout] if holdout != args.holdout_season else fit_seasons
        if not fit or holdout not in set(seasons):
            continue
        with_altitude = best if fit == fit_seasons else fit_params(matches, fit)[0]
        flat, _, _ = fit_params(matches, fit, grid=default_grid(altitudes=(0,)))
        train = matches[(matches["season"] < holdout) & matches["home_score"].notna() & ~matches["awarded"]]
        fr = np.array([(train["home_score"] > train["away_score"]).mean(), (train["home_score"] == train["away_score"]).mean(), (train["home_score"] < train["away_score"]).mean()])
        held = matches[(matches["season"] == holdout) & matches["home_score"].notna()]
        reference = float(np.mean([-np.log(fr[0 if h > a else 1 if h == a else 2]) for h, a in zip(held["home_score"], held["away_score"])]))
        loss_with, loss_flat = walk_log_loss(matches, with_altitude, {holdout}), walk_log_loss(matches, flat, {holdout})
        checks[holdout] = {"ajuste": fit, "con_altitud": asdict(with_altitude), "sin_altitud": asdict(flat), "perdida_con_altitud": loss_with, "perdida_sin_altitud": loss_flat, "perdida_frecuencias": reference}
        print(f"{holdout} (ajuste {fit}): con altitud {loss_with:.4f} (A={with_altitude.altitude:g}) | sin altitud {loss_flat:.4f} | frecuencias {reference:.4f} | altitud mejora {(loss_flat - loss_with) / loss_flat * 100:+.2f} % | Elo mejora {(reference - loss_with) / reference * 100:+.2f} % sobre frecuencias")

    probabilities = simulate_title_probabilities(matches, best, n_sim=args.n_sim, sigma=args.sigma).assign(team_name=lambda frame: frame["team_id"].map(names))
    probabilities.to_parquet(args.out / "probabilidad_titulo.parquet", index=False)
    probabilities.to_csv(args.out / "probabilidad_titulo.csv", index=False, encoding="utf-8-sig")
    (args.out / "parametros_elo.json").write_text(json.dumps({"params": asdict(best), "sigma": args.sigma, "n_sim": args.n_sim, "fit_seasons": fit_seasons, "perdida_ajuste": in_sample, "fuera_de_muestra": checks}, indent=2, default=str), encoding="utf-8")

    print("\n=== probabilidad asignada al campeon real, tras su partido k ===")
    hits = {6: 0, 9: 0, 12: 0, 15: 0}
    evaluated = 0
    for (season, tour), (team, points) in sorted(champions.items()):
        table = probabilities[(probabilities["season"] == season) & (probabilities["tour"] == tour)]
        mine = table[table["team_id"] == team].set_index("k")["p_title"]
        evaluated += 1
        for k in hits:
            at_k = table[table["k"] == k]
            leader = at_k.loc[at_k["p_title"].idxmax(), "team_id"] if len(at_k) else None
            hits[k] += int(leader == team)
        print(f"{season} {tour:8s} campeon {names.get(team, team)} ({points} pts): " + " ".join(f"J{k}:{mine.get(k, float('nan')) * 100:4.0f}%" for k in (0, 6, 9, 12, 15)))
    print(f"el favorito del modelo es el campeon real tras el partido k en: {dict((f'J{k}', f'{v}/{evaluated}') for k, v in hits.items())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
