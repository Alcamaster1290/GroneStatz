"""xG propio por tiro: regresion logistica con L2, solo numpy y scipy.

Variables: distancia y angulo al arco, parte del cuerpo y situacion de juego. Excluye a proposito lo posterior al
disparo (``goal_mouth_*``, ``block_coordinates``): eso seria xGOT y filtraria el resultado. Metodologia inspirada,
sin copiar codigo, en soccer_xg (Apache-2.0), expected-goals-thesis (MIT) y xGils (MIT).

Uso:
    py -3.11 -m gronestats.analysis.xg_model --out docs/recursos-dashboard/datos-de-apoyo/xg-prototipo
Lee ``<season>/dashboard/current/shot_events.parquet`` de cada temporada y valida dejando una temporada fuera:
cada tiro recibe el xG de un modelo que no vio su temporada.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import rankdata

from gronestats.analysis.match_status import is_administrative, is_annulled, is_official_award

# Base: "assisted". "fast-break" queda fuera a proposito: SofaScore amplio la etiqueta en 2025 (de 2-3 % de los tiros a 7-9 %)
# y su tasa de gol cayo de 20-29 % a 13 % con las mismas distancias; con ella el xG de 2025-2026 salia 7 % sobre los goles.
SITUATIONS = ["regular", "corner", "set-piece", "free-kick", "throw-in-set-piece"]
GOAL_HALF_M = (55.8 - 44.2) / 2 * 0.68  # poste a poste en la cancha Opta (y de 44,2 a 55,8, ancho 68 m)
PITCH_LENGTH_M, PITCH_WIDTH_M = 105.0, 68.0
SOURCE_MODEL, SOURCE_PENALTY, SOURCE_OWN = "modelo", "penal (constante)", "autogol (0)"
SOURCE_NO_COORDINATES, SOURCE_SHOOTOUT = "sin coordenadas (media por situación)", "tanda (excluida)"


def shot_geometry(x: pd.Series, y: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Distancia (m) y angulo (rad) al arco. ``x`` es la distancia a la linea de fondo del arco atacado: misma
    convencion para local y visita (verificado contra ``gronestats/dashboard``)."""
    dx = np.asarray(x, dtype=float) * PITCH_LENGTH_M / 100
    dy = (np.asarray(y, dtype=float) - 50) * PITCH_WIDTH_M / 100
    distance = np.hypot(dx, dy)
    angle = np.arctan2(2 * GOAL_HALF_M * dx, dx**2 + dy**2 - GOAL_HALF_M**2)
    return distance, np.where(angle < 0, angle + np.pi, angle)


def _is(column: pd.Series, value: str) -> pd.Series:
    return (column == value).fillna(False).astype(bool)  # las columnas de texto traen <NA>


def prepare_shots(shots: pd.DataFrame) -> pd.DataFrame:
    work = shots.copy()
    work["is_goal"] = _is(work["shot_type"], "goal").astype(int)
    work["is_pen"] = _is(work["situation"], "penalty")
    work["is_own"] = _is(work["goal_type"], "own")
    work["is_shootout"] = _is(work["situation"], "shootout")
    work["has_xy"] = work["x"].notna() & work["y"].notna()
    return work


def build_features(shots: pd.DataFrame, stats: tuple[pd.Series, pd.Series] | None = None) -> tuple[pd.DataFrame, tuple[pd.Series, pd.Series]]:
    distance, angle = shot_geometry(shots["x"], shots["y"])
    head = _is(shots["body_part"], "head").astype(float).to_numpy()
    other = _is(shots["body_part"], "other").astype(float).to_numpy()
    log_distance = np.log(np.maximum(distance, 0.5))
    columns = {"dist": distance, "log_dist": log_distance, "dist2": distance**2, "angle": angle, "head": head, "head_x_logd": head * log_distance, "otro_cuerpo": other}
    for situation in SITUATIONS:
        columns[f"sit_{situation}"] = _is(shots["situation"], situation).astype(float).to_numpy()
    columns["fk_x_logd"] = columns["sit_free-kick"] * log_distance
    features = pd.DataFrame(columns, index=shots.index)
    if stats is None:
        stats = (features.mean(), features.std().replace(0, 1))
    return (features - stats[0]) / stats[1], stats


def fit_logistic(features: pd.DataFrame, target: np.ndarray, l2: float = 1.0) -> np.ndarray:
    design = np.c_[np.ones(len(features)), features.to_numpy()]

    def objective(beta: np.ndarray) -> tuple[float, np.ndarray]:
        z = design @ beta
        p = 1 / (1 + np.exp(-z))
        loss = np.sum(np.logaddexp(0, z) - target * z) + 0.5 * l2 * np.sum(beta[1:] ** 2)
        return loss, design.T @ (p - target) + l2 * np.r_[0, beta[1:]]

    return minimize(objective, np.zeros(design.shape[1]), jac=True, method="L-BFGS-B").x


def predict_logistic(features: pd.DataFrame, beta: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-(np.c_[np.ones(len(features)), features.to_numpy()] @ beta)))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc(y: np.ndarray, p: np.ndarray) -> float:
    ranks = rankdata(p)
    positives = y.sum()
    negatives = len(y) - positives
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


@dataclass
class XgModel:
    """Modelo entrenado: coeficientes, estandarizacion, tasa de penales y tasa de gol por situacion."""

    beta: np.ndarray
    stats: tuple[pd.Series, pd.Series]
    penalty_rate: float
    situation_rate: pd.Series
    base_rate: float

    def predict(self, shots: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """(xG, origen) de cada tiro, con el mismo indice que ``shots``."""
        work = prepare_shots(shots)
        xg = pd.Series(np.nan, index=work.index, dtype=float)
        source = pd.Series("", index=work.index, dtype=object)
        modeled = work["has_xy"] & ~work["is_pen"] & ~work["is_own"] & ~work["is_shootout"]
        if modeled.any():
            features, _ = build_features(work[modeled], self.stats)
            xg[modeled] = predict_logistic(features, self.beta)
            source[modeled] = SOURCE_MODEL
        xg[work["is_pen"]], source[work["is_pen"]] = self.penalty_rate, SOURCE_PENALTY
        xg[work["is_own"]], source[work["is_own"]] = 0.0, SOURCE_OWN
        xg[work["is_shootout"]], source[work["is_shootout"]] = 0.0, SOURCE_SHOOTOUT
        no_xy = ~work["has_xy"] & ~work["is_pen"] & ~work["is_own"] & ~work["is_shootout"]
        xg[no_xy] = work.loc[no_xy, "situation"].map(self.situation_rate).fillna(self.base_rate)
        source[no_xy] = SOURCE_NO_COORDINATES
        return xg, source


def fit_model(shots: pd.DataFrame, l2: float = 1.0) -> XgModel:
    work = prepare_shots(shots)
    trainable = work[~work["is_pen"] & ~work["is_own"] & ~work["is_shootout"] & work["has_xy"]]
    features, stats = build_features(trainable)
    return XgModel(
        beta=fit_logistic(features, trainable["is_goal"].to_numpy(), l2),
        stats=stats,
        penalty_rate=float(work.loc[work["is_pen"], "is_goal"].mean()),
        situation_rate=trainable.groupby("situation")["is_goal"].mean(),
        base_rate=float(trainable["is_goal"].mean()),
    )


def leave_one_season_out(shots: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """xG de cada tiro con un modelo entrenado en las demas temporadas, mas las metricas fuera de muestra."""
    seasons = sorted(shots["season"].unique())
    if len(seasons) < 2:
        raise ValueError("hacen falta al menos dos temporadas para dejar una fuera")
    xg = pd.Series(np.nan, index=shots.index, dtype=float)
    source = pd.Series("", index=shots.index, dtype=object)
    rows = []
    for season in seasons:
        train = shots[shots["season"] != season]
        test = shots[shots["season"] == season]
        model = fit_model(train)
        xg[test.index], source[test.index] = model.predict(test)
        rows.append(_season_metrics(season, prepare_shots(train), prepare_shots(test), xg, source, model))
    return xg, source, pd.DataFrame(rows).set_index("season")


def _season_metrics(season: int, train: pd.DataFrame, test: pd.DataFrame, xg: pd.Series, source: pd.Series, model: XgModel) -> dict:
    trainable = train[~train["is_pen"] & ~train["is_own"] & ~train["is_shootout"] & train["has_xy"]]
    scored = test[source[test.index] == SOURCE_MODEL]
    y = scored["is_goal"].to_numpy()
    p = xg[scored.index].to_numpy()
    features, stats = build_features(trainable)
    distance_only = ["dist", "log_dist"]
    beta_distance = fit_logistic(features[distance_only], trainable["is_goal"].to_numpy())
    p_distance = predict_logistic(build_features(scored, stats)[0][distance_only], beta_distance)
    return {
        "season": season,
        "tiros_modelo": len(y),
        "log_loss_modelo": log_loss(y, p),
        "log_loss_solo_distancia": log_loss(y, p_distance),
        "log_loss_constante": log_loss(y, np.full(len(y), model.base_rate)),
        "auc": auc(y, p),
        "brier": float(np.mean((p - y) ** 2)),
        "xG_total": float(p.sum()),
        "goles": int(y.sum()),
    }


def player_tables(shots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """xG por jugador y partido, y por jugador y temporada (sin los tiros de las tandas de penales)."""
    played = shots[~shots["is_shootout"]].copy()
    played["xg_open"] = played["xg"].where(~played["is_pen"], 0.0)
    keys = ["season", "player_id", "name", "team_name"]
    per_match = (
        played.groupby(["season", "match_id", "player_id", "name", "team_name"], dropna=False)
        .agg(tiros=("xg", "size"), xG=("xg", "sum"), goles=("is_goal", "sum"))
        .reset_index()
    )
    per_match["goles_menos_xG"] = per_match["goles"] - per_match["xG"]
    per_season = (
        played.groupby(keys, dropna=False)
        .agg(partidos=("match_id", "nunique"), tiros=("xg", "size"), xG=("xg", "sum"), goles=("is_goal", "sum"), xG_sin_penales=("xg_open", "sum"))
        .reset_index()
    )
    per_season["xG_por_tiro"] = per_season["xG"] / per_season["tiros"]
    per_season["goles_menos_xG"] = per_season["goles"] - per_season["xG"]
    return per_match, per_season


def load_shots(base_dir: Path, seasons: list[int]) -> pd.DataFrame:
    """Tiros del bundle publicado, sin los de partidos administrativos (no hubo partido: no deberia haber tiros)."""
    frames = []
    for season in seasons:
        dataset = base_dir / str(season) / "dashboard" / "current"
        shots = pd.read_parquet(dataset / "shot_events.parquet").assign(season=season)
        matches = pd.read_parquet(dataset / "matches.parquet")
        if "status" in matches.columns:
            shots = shots[~shots["match_id"].isin(matches.loc[is_administrative(matches["status"]), "match_id"])]
        frames.append(shots)
    return pd.concat(frames, ignore_index=True)


def compare_with_provider(base_dir: Path, shots: pd.DataFrame) -> pd.DataFrame:
    """xG propio sumado por equipo y partido contra el ``expectedGoals`` de equipo del proveedor."""
    rows = []
    for season in sorted(shots["season"].unique()):
        stats = pd.read_parquet(base_dir / str(season) / "dashboard" / "current" / "team_stats.parquet")
        stats = stats[(stats["KEY"] == "expectedGoals") & (stats["PERIOD"].astype(str).str.upper() == "ALL")].drop_duplicates("MATCH_ID")
        if stats.empty:
            continue
        mine = shots[shots["season"] == season].groupby(["match_id", "is_home"])["xg"].sum().unstack()
        mine.columns = ["xg_visita", "xg_local"]
        joined = stats.set_index("MATCH_ID")[["HOMEVALUE", "AWAYVALUE"]].join(mine, how="inner").dropna()
        provider = np.r_[joined["HOMEVALUE"].to_numpy(dtype=float), joined["AWAYVALUE"].to_numpy(dtype=float)]
        own = np.r_[joined["xg_local"].to_numpy(), joined["xg_visita"].to_numpy()]
        rows.append(
            {
                "season": season,
                "equipo_partidos": len(provider),
                "correlacion": float(np.corrcoef(provider, own)[0, 1]),
                "proveedor_medio": float(provider.mean()),
                "propio_medio": float(own.mean()),
                "ratio": float(own.sum() / provider.sum()),
                "MAE": float(np.mean(np.abs(provider - own))),
            }
        )
    return pd.DataFrame(rows).set_index("season") if rows else pd.DataFrame()


def goals_match_scoreboard(base_dir: Path, shots: pd.DataFrame) -> pd.Series:
    """Fraccion de partidos con mapa de tiros y sin autogoles cuyos goles del mapa coinciden con el marcador, por temporada.

    Los partidos sin mapa de tiros (SofaScore no lo tiene) no cuentan: no hay nada que comparar."""
    results = []
    for season in sorted(shots["season"].unique()):
        matches = pd.read_parquet(base_dir / str(season) / "dashboard" / "current" / "matches.parquet")
        if "status" in matches.columns:  # un marcador fijado o anulado por la federacion no tiene por que coincidir con los goles de la cancha
            matches = matches[~(is_official_award(matches["status"]) | is_annulled(matches["status"]))]
        matches = matches[["match_id", "home_score", "away_score"]]
        season_shots = prepare_shots(shots[shots["season"] == season])
        matches = matches[matches["match_id"].isin(season_shots["match_id"])]
        goals = season_shots[(season_shots["is_goal"] == 1) & ~season_shots["is_own"]].groupby(["match_id", "is_home"]).size().unstack(fill_value=0)
        goals = goals.rename(columns={True: "g_local", False: "g_visita"}).reset_index()
        own = season_shots[season_shots["is_own"]].groupby("match_id").size().rename("autogoles")
        joined = matches.merge(goals, on="match_id", how="left").fillna({"g_local": 0, "g_visita": 0}).merge(own, on="match_id", how="left").fillna({"autogoles": 0})
        clean = joined[joined["autogoles"] == 0]
        results.append(pd.Series({season: float(((clean["g_local"] == clean["home_score"]) & (clean["g_visita"] == clean["away_score"])).mean())}))
    return pd.concat(results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="xG propio por tiro de la Liga 1, validado dejando una temporada fuera.")
    parser.add_argument("--league", default="Liga 1 Peru")
    parser.add_argument("--seasons", default="2022,2023,2024,2025,2026")
    parser.add_argument("--out", type=Path, required=True, help="Carpeta de salida (xg_tiros.parquet y tablas por jugador).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(__file__).resolve().parents[1] / "data" / args.league
    seasons = [int(token) for token in args.seasons.split(",")]
    shots = prepare_shots(load_shots(base_dir, seasons))
    print("tiros:", shots.groupby("season").size().to_dict(), "| con coordenadas (%):", (shots.groupby("season")["has_xy"].mean() * 100).round(1).to_dict())
    print("goles del mapa = marcador (partidos sin autogoles, %):", (goals_match_scoreboard(base_dir, shots) * 100).round(1).to_dict())

    xg, source, metrics = leave_one_season_out(shots)
    shots["xg"], shots["xg_source"] = xg, source
    print("\n=== validacion dejando una temporada fuera ===")
    print(metrics.round(4).to_string())
    print("\n=== contra el xG de equipo del proveedor ===")
    print(compare_with_provider(base_dir, shots).round(3).to_string())

    per_match, per_season = player_tables(shots)
    args.out.mkdir(parents=True, exist_ok=True)
    columns = ["season", "match_id", "shot_id", "player_id", "name", "team_id", "team_name", "is_home", "shot_type", "situation", "body_part", "time", "x", "y", "is_goal", "xg", "xg_source"]
    shots[[column for column in columns if column in shots.columns]].to_parquet(args.out / "xg_tiros.parquet", index=False)
    per_match.round(4).to_csv(args.out / "xg_jugador_partido.csv", index=False, encoding="utf-8-sig")
    per_season.round(4).to_csv(args.out / "xg_jugador_temporada.csv", index=False, encoding="utf-8-sig")
    metrics.round(4).to_csv(args.out / "xg_validacion.csv", encoding="utf-8-sig")
    print("\nfuentes de xG:", shots["xg_source"].value_counts().to_dict(), "| salida:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
