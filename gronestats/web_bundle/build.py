"""Constructor del release de servicio entre temporadas.

Junta los bundles publicados de cada temporada (``<temporada>/dashboard/current``) con las salidas de análisis ya generadas
(xG, importancia, probabilidad de título, formaciones) y las tablas de referencia, y escribe ``releases/<id>/`` con un
``manifest.json``. Después copia el release a ``current/``. No recalcula análisis: eso es la fase ``build-analytics`` del plan siguiente.

    py -3.11 -m gronestats.web_bundle.build --out "gronestats/data/Liga 1 Peru/web"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from gronestats.analysis.match_status import is_annulled, is_official_award
from gronestats.analysis.standings import ADJUSTMENTS_FILE, load_adjustments, season_tables, tournament_table
from gronestats.analysis.title_race import parse_match_dates, tournament_of
from gronestats.web_bundle.schema import SCHEMA_VERSION, TABLES, TOURNAMENTS
from gronestats.web_bundle.validate import validate_bundle

DEFAULT_SEASONS = (2022, 2023, 2024, 2025, 2026)
KEEP_RELEASES_IN_LOG = 5
INT_COLUMNS = {"season", "round_number", "match_id", "home_id", "away_id", "home_score", "away_score", "team_id", "player_id", "shot_id", "minute", "k"}


def _season_table(data_dir: Path, season: int, name: str, columns: list[str] | None = None) -> pd.DataFrame:
    path = data_dir / str(season) / "dashboard" / "current" / f"{name}.parquet"
    return pd.read_parquet(path, columns=columns) if path.exists() else pd.DataFrame(columns=columns or [])


def _ids(frame: pd.DataFrame, column: str) -> set[int]:
    if column not in frame.columns or frame.empty:
        return set()
    return {int(value) for value in pd.to_numeric(frame[column], errors="coerce").dropna()}


def _typed(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    """Columnas en el orden del esquema y los ids como enteros que admiten nulos."""
    frame = frame[list(TABLES[name].columns)].copy()
    for column in frame.columns:
        if column in INT_COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    return frame.reset_index(drop=True)


def build_matches(data_dir: Path, seasons: Iterable[int]) -> pd.DataFrame:
    frames = []
    for season in seasons:
        matches = _season_table(data_dir, season, "matches")
        if matches.empty:
            continue
        matches = matches.assign(season=season)
        matches["tournament"] = matches["tournament"].map(tournament_of)  # la final, los playoffs y la promoción no son torneos cortos
        matches = matches.dropna(subset=["tournament"])
        matches["date"] = parse_match_dates(matches["fecha"])
        if "status" not in matches.columns:
            matches["status"] = pd.NA
        frames.append(matches)
    result = _typed(pd.concat(frames, ignore_index=True), "matches")
    for column in ("status", "estadio", "ciudad", "arbitro"):
        result[column] = result[column].astype("string")
    return result.sort_values(["season", "date", "match_id"]).reset_index(drop=True)


def build_teams(data_dir: Path, seasons: Iterable[int], reference_dir: Path) -> pd.DataFrame:
    sources = (("name", "short_name"), ("full_name", "full_name"), ("color", "team_colors"), ("level", "competitiveness_level"), ("stadium", "stadium_name_city"), ("department", "department"), ("region", "region"))
    teams: dict[int, dict] = {}
    for season in sorted(seasons):
        for row in _season_table(data_dir, season, "teams").itertuples(index=False):
            current = teams.setdefault(int(row.team_id), {})
            for target, source in sources:
                value = getattr(row, source, None)
                if value is not None and not pd.isna(value):
                    current[target] = value  # una temporada posterior corrige a la anterior; un nulo no borra un valor
    reference = reference_dir / "nivel_competitividad_faltante.csv"
    if reference.exists():
        for row in pd.read_csv(reference, encoding="utf-8-sig").itertuples():
            teams.setdefault(int(row.team_id), {}).setdefault("level", row.nivel_asignado)  # solo completa: no pisa un nivel que sí trae una temporada
    rows = [{"team_id": team_id, **{column: values.get(column) for column in TABLES["teams"].columns if column != "team_id"}} for team_id, values in teams.items()]
    for row in rows:
        row["name"] = row["name"] or str(row["team_id"])
    return _typed(pd.DataFrame(rows), "teams").sort_values("team_id").reset_index(drop=True)


def build_players(data_dir: Path, seasons: Iterable[int], images_dir: Path | None) -> pd.DataFrame:
    players: dict[int, dict] = {}
    for season in sorted(seasons):
        for row in _season_table(data_dir, season, "players").itertuples(index=False):
            players[int(row.player_id)] = {"name": row.name, "short_name": row.short_name, "position": row.position, "team_id": row.team_id}
    for season in sorted(seasons):  # jugadores que solo aparecen en un partido (no en la tabla de jugadores)
        seen = _season_table(data_dir, season, "player_match", ["player_id", "name", "team_id", "position"]).drop_duplicates("player_id", keep="last")
        for row in seen.itertuples(index=False):
            players.setdefault(int(row.player_id), {"name": row.name, "short_name": row.name, "position": row.position, "team_id": row.team_id})
    photos = {int(path.stem): path.name for path in images_dir.iterdir() if path.is_file() and path.stem.isdigit()} if images_dir is not None and images_dir.exists() else {}
    rows = [{"player_id": player_id, **values, "photo": photos.get(player_id)} for player_id, values in players.items()]
    return _typed(pd.DataFrame(rows), "players").sort_values("player_id").reset_index(drop=True)


ZERO_WHEN_PLAYED = ("goals", "assists", "saves")


def fill_omitted_zeros(player_match: pd.DataFrame) -> pd.DataFrame:
    """SofaScore omite las estadísticas en cero de quien jugó: ahí un nulo es 0 (los goles suman unos 20 menos que el marcador por
    temporada, los autogoles). Las tarjetas no se rellenan: vienen nulas en todas las filas y eso es un dato ausente, no un cero."""
    result = player_match.copy()
    played = pd.to_numeric(result["minutesplayed"], errors="coerce") > 0
    for column in ZERO_WHEN_PLAYED:
        values = pd.to_numeric(result[column], errors="coerce")
        result[column] = values.where(~(played & values.isna()), 0)
    return result


def _concat_seasons(data_dir: Path, seasons: Iterable[int], name: str, columns: list[str]) -> pd.DataFrame:
    frames = []
    for season in seasons:
        frame = _season_table(data_dir, season, name, columns)
        if not frame.empty:
            frames.append(frame.assign(season=season))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=[*columns, "season"])


def build_standings(matches: pd.DataFrame, adjustments: pd.DataFrame) -> pd.DataFrame:
    """Tabla de cada torneo tras cada fecha (partidos con ronda ≤ N ya jugados) y la acumulada final (``round_number`` 0).

    Los ajustes oficiales (sanciones, adjudicados sin goles) se aplican solo a la última fecha de cada torneo y a la acumulada.
    """
    frames = []
    base = matches.assign(tour=matches["tournament"])
    for season in sorted(int(value) for value in matches["season"].unique()):
        season_matches = base[base["season"] == season]
        for tournament in TOURNAMENTS:
            rounds = sorted(int(value) for value in season_matches.loc[season_matches["tour"] == tournament, "round_number"].dropna().unique())
            for round_number in rounds:
                subset = season_matches[(season_matches["tour"] == tournament) & (season_matches["round_number"] <= round_number)]
                table = tournament_table(subset, adjustments if round_number == rounds[-1] else None, season=season, tournament=tournament)
                frames.append(table.assign(season=season, tournament=tournament, round_number=round_number))
        frames.append(season_tables(season_matches, season, adjustments)["Acumulada"].assign(season=season, tournament="Acumulada", round_number=0))
    return _typed(pd.concat(frames, ignore_index=True), "standings")


def build_venues(reference_dir: Path) -> pd.DataFrame:
    table = pd.read_csv(reference_dir / "altitud_estadios_medida.csv", encoding="utf-8-sig")
    table = table.rename(columns={"ciudad_en_el_maestro": "ciudad", "precision_ubicacion": "precision", "fuente_altitud": "fuente"})
    return table[list(TABLES["venues"].columns)].drop_duplicates(["estadio", "ciudad"]).reset_index(drop=True)


def _file_version(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:8]


def build_model_runs(analytics_dir: Path) -> pd.DataFrame:
    rows = []
    xg_metrics = analytics_dir / "xg-prototipo" / "xg_validacion.csv"
    if xg_metrics.exists():
        table = pd.read_csv(xg_metrics)
        seasons = [int(season) for season in table["season"]] if "season" in table.columns else []
        rows.append({"model": "xg", "version": _file_version(xg_metrics), "trained_on": f"dejando una temporada fuera: {seasons}", "params": json.dumps({"l2": 1.0}), "metrics": table.to_json(orient="records")})
    elo = analytics_dir / "title-race" / "parametros_elo.json"
    if elo.exists():
        data = json.loads(elo.read_text(encoding="utf-8"))
        rows.append(
            {"model": "elo", "version": _file_version(elo), "trained_on": f"temporadas {data.get('fit_seasons')}", "params": json.dumps({**data.get("params", {}), "sigma": data.get("sigma"), "n_sim": data.get("n_sim")}),
             "metrics": json.dumps({"perdida_ajuste": data.get("perdida_ajuste"), "fuera_de_muestra": data.get("fuera_de_muestra")}, default=str)}
        )
    return pd.DataFrame(rows, columns=list(TABLES["model_runs"].columns))


LEDGER_MODE = {"detail": "details", "shots": "shotmap", "heatmaps": "heatmaps", "lineups": "lineups", "momentum": "momentum", "team_stats": "team_stats", "average_positions": "average_positions"}
GAP_STATE = {"vacio": "missing_from_source", "error": "failed", "bloqueado": "blocked"}  # sin registro (o cualquier otro estado): pending


def read_ledger(data_dir: Path, season: int) -> dict[tuple[str, object], str]:
    """Último estado de cada (modo, partido) en el registro de scrapeo de la temporada; vacío si no hay registro."""
    path = data_dir / str(season) / "raw" / "scrape_ledger.jsonl"
    last: dict[tuple[str, object], str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                last[(str(entry.get("mode")), entry.get("match_id"))] = str(entry.get("status"))
    return last


def build_team_cards(data_dir: Path, seasons: Iterable[int], matches: pd.DataFrame) -> pd.DataFrame:
    """Amarillas y rojas por equipo y partido (``Team Stats``, periodo ALL). SofaScore omite las rojas cuando no hubo ninguna, así que
    en un partido con estadísticas de equipo una clave ausente es 0; un partido sin estadísticas de equipo no tiene fila."""
    rows = []
    teams = {int(row.match_id): (int(row.home_id), int(row.away_id)) for row in matches.itertuples()}
    for season in seasons:
        stats = _season_table(data_dir, season, "team_stats", ["MATCH_ID", "KEY", "PERIOD", "HOMEVALUE", "AWAYVALUE"])
        if stats.empty:
            continue
        stats = stats[stats["PERIOD"].astype(str).str.upper() == "ALL"].assign(MATCH_ID=lambda f: pd.to_numeric(f["MATCH_ID"], errors="coerce"))
        by_key = {key: stats[stats["KEY"] == key].drop_duplicates("MATCH_ID").set_index("MATCH_ID") for key in ("yellowCards", "redCards")}

        def value(key: str, match_id: int, side: str) -> int:
            frame = by_key[key]
            if match_id not in frame.index:
                return 0
            number = pd.to_numeric(frame.at[match_id, f"{side}VALUE"], errors="coerce")
            return 0 if pd.isna(number) else int(number)

        for match_id in sorted(int(value) for value in stats["MATCH_ID"].dropna().unique()):
            if match_id not in teams:
                continue
            for side, team_id in zip(("HOME", "AWAY"), teams[match_id]):
                rows.append({"season": season, "match_id": match_id, "team_id": team_id, "yellow": value("yellowCards", match_id, side), "red": value("redCards", match_id, side)})
    return pd.DataFrame(rows, columns=list(TABLES["team_cards"].columns))


def build_coverage(data_dir: Path, seasons: Iterable[int], matches: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Por temporada y tipo de dato: partidos esperados (jugados, sin marcador fijado ni anulados), los que tienen ese dato y, de los
    que faltan, cuántos SofaScore no tiene (404), cuántos nunca se pidieron, cuántos dieron error y cuántos se cortaron por bloqueo."""
    rows = []
    for season in seasons:
        ledger = read_ledger(data_dir, season)
        season_matches = matches[matches["season"] == season]
        normal = season_matches[season_matches["home_score"].notna() & season_matches["away_score"].notna() & ~is_official_award(season_matches["status"]) & ~is_annulled(season_matches["status"])]
        expected = _ids(normal, "match_id")
        sources = {
            "detail": _ids(tables["player_match"][tables["player_match"]["season"] == season], "match_id"),
            "shots": _ids(tables["shot_events"][tables["shot_events"]["season"] == season], "match_id"),
            "heatmaps": _ids(tables["heatmap_points"][tables["heatmap_points"]["season"] == season], "match_id"),
            "lineups": _ids(tables["lineups"][tables["lineups"]["season"] == season], "match_id"),
            "momentum": _ids(_season_table(data_dir, season, "match_momentum", ["match_id"]), "match_id"),
            "team_stats": _ids(_season_table(data_dir, season, "team_stats", ["MATCH_ID"]), "MATCH_ID"),
            "average_positions": _ids(_season_table(data_dir, season, "average_positions", ["match_id"]), "match_id"),
        }
        for kind, present_ids in sources.items():
            missing_ids = expected - present_ids
            states = Counter(GAP_STATE.get(ledger.get((LEDGER_MODE[kind], match_id)), "pending") for match_id in missing_ids)
            rows.append(
                {"season": season, "kind": kind, "expected": len(expected), "present": len(expected & present_ids), "missing": len(missing_ids),
                 "missing_from_source": states["missing_from_source"], "pending": states["pending"], "failed": states["failed"], "blocked": states["blocked"]}
            )
    return pd.DataFrame(rows)


def ledger_summary(data_dir: Path, seasons: Iterable[int]) -> dict[str, dict[str, dict[str, int]]]:
    """Estado actual de cada intento de scrapeo por temporada: modo -> estado -> partidos (el último intento de cada partido manda)."""
    summary: dict[str, dict[str, dict[str, int]]] = {}
    for season in seasons:
        last = read_ledger(data_dir, season)
        if not last:
            continue
        modes = {mode for mode, _ in last}
        summary[str(season)] = {mode: dict(Counter(status for (m, _), status in last.items() if m == mode)) for mode in sorted(modes)}
    return summary


def _publish_current(release: Path, out_dir: Path) -> None:
    temporary, current = out_dir / "current.tmp", out_dir / "current"
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(release, temporary)
    if current.exists():
        shutil.rmtree(current)
    temporary.rename(current)


def build_web_bundle(data_dir: Path, analytics_dir: Path, reference_dir: Path, out_dir: Path, *, seasons: Iterable[int] = DEFAULT_SEASONS, images_dir: Path | None = None, release_id: str | None = None) -> Path:
    """Escribe ``out_dir/releases/<id>/``, lo valida y lo copia a ``out_dir/current``. Devuelve la carpeta del release."""
    data_dir, analytics_dir, reference_dir, out_dir = Path(data_dir), Path(analytics_dir), Path(reference_dir), Path(out_dir)
    seasons = tuple(seasons)
    release_id = release_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    release = out_dir / "releases" / release_id
    release.mkdir(parents=True, exist_ok=True)

    matches = build_matches(data_dir, seasons)
    adjustments = load_adjustments(data_dir / ADJUSTMENTS_FILE)
    xg_shots = pd.read_parquet(analytics_dir / "xg-prototipo" / "xg_tiros.parquet").rename(columns={"time": "minute"})
    xg_shots = xg_shots[xg_shots["season"].isin(seasons)].assign(is_home=lambda f: f["is_home"].astype(bool), is_goal=lambda f: f["is_goal"].astype(bool))
    lineups = pd.read_parquet(analytics_dir / "formaciones" / "formaciones_equipo_partido.parquet")
    importance = pd.read_parquet(analytics_dir / "title-race" / "importancia_equipo_partido.parquet").rename(columns={"tour": "tournament"})
    probability = pd.read_parquet(analytics_dir / "title-race" / "probabilidad_titulo.parquet").rename(columns={"tour": "tournament"})
    known_gaps_path = data_dir / "known_gaps.csv"
    known_gaps = pd.read_csv(known_gaps_path, encoding="utf-8-sig") if known_gaps_path.exists() else pd.DataFrame(columns=list(TABLES["known_gaps"].columns))

    tables: dict[str, pd.DataFrame] = {
        "matches": matches,
        "teams": build_teams(data_dir, seasons, reference_dir),
        "players": build_players(data_dir, seasons, images_dir),
        "player_match": _typed(fill_omitted_zeros(_concat_seasons(data_dir, seasons, "player_match", ["match_id", "player_id", "team_id", "position", "minutesplayed", "goals", "assists", "yellowcards", "redcards", "saves", "rating"])), "player_match"),
        "shot_events": _typed(xg_shots, "shot_events"),
        "heatmap_points": _typed(_concat_seasons(data_dir, seasons, "heatmap_points", ["match_id", "player_id", "team_id", "x", "y"]), "heatmap_points"),
        "lineups": _typed(lineups[lineups["season"].isin(seasons)], "lineups"),
        "match_importance": _typed(importance[importance["season"].isin(seasons)], "match_importance"),
        "title_probability": _typed(probability[probability["season"].isin(seasons)], "title_probability"),
        "standings": build_standings(matches, adjustments),
        "venues": build_venues(reference_dir),
        "model_runs": build_model_runs(analytics_dir),
        "known_gaps": _typed(known_gaps, "known_gaps"),
    }
    tables["data_coverage"] = _typed(build_coverage(data_dir, seasons, matches, tables), "data_coverage")
    tables["team_cards"] = _typed(build_team_cards(data_dir, seasons, matches), "team_cards")

    played = matches[matches["home_score"].notna() & matches["away_score"].notna() & ~is_official_award(matches["status"]) & ~is_annulled(matches["status"])]
    data_as_of = played["date"].max()
    built_at = datetime.now().isoformat(timespec="seconds")
    previous = out_dir / "current" / "release_log.parquet"
    log = pd.read_parquet(previous) if previous.exists() else pd.DataFrame(columns=list(TABLES["release_log"].columns))
    entry = pd.DataFrame([{"release_id": release_id, "built_at": built_at, "matches": int(len(played)), "data_as_of": None if pd.isna(data_as_of) else data_as_of.isoformat()}])
    tables["release_log"] = pd.concat([log, entry], ignore_index=True).tail(KEEP_RELEASES_IN_LOG)

    for name, frame in tables.items():
        frame.to_parquet(release / f"{name}.parquet", index=False)
    models = {row.model: row.version for row in tables["model_runs"].itertuples()}
    manifest = {
        "release_id": release_id,
        "schema_version": SCHEMA_VERSION,
        "built_at": built_at,
        "data_as_of": None if pd.isna(data_as_of) else data_as_of.isoformat(),
        "seasons": list(seasons),
        "tables": {name: int(len(frame)) for name, frame in tables.items()},
        "models": models,
        "ledger": ledger_summary(data_dir, seasons),
    }
    (release / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    errors = validate_bundle(release)
    if errors:
        raise ValueError("el release no cumple el esquema: " + "; ".join(errors))
    _publish_current(release, out_dir)
    return release


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Construye el release de servicio (entre temporadas) para la API y la web.")
    parser.add_argument("--league", default="Liga 1 Peru")
    parser.add_argument("--data-dir", type=Path, default=None, help="Carpeta de la liga (por defecto gronestats/data/<liga>).")
    parser.add_argument("--analytics-dir", type=Path, default=root.parent / "docs" / "recursos-dashboard" / "datos-de-apoyo", help="Salidas de análisis y tablas de referencia.")
    parser.add_argument("--images-dir", type=Path, default=root / "images" / "players")
    parser.add_argument("--out", type=Path, default=None, help="Por defecto <data-dir>/web.")
    parser.add_argument("--seasons", default=",".join(str(season) for season in DEFAULT_SEASONS))
    args = parser.parse_args(argv)
    data_dir = args.data_dir or root / "data" / args.league
    out = args.out or data_dir / "web"
    release = build_web_bundle(data_dir, args.analytics_dir, args.analytics_dir, out, seasons=[int(token) for token in args.seasons.split(",")], images_dir=args.images_dir)
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    print(f"release {manifest['release_id']} (datos hasta {manifest['data_as_of']}) en {release}")
    for name, rows in manifest["tables"].items():
        print(f"  {name:18s} {rows:>9,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
