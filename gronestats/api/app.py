"""API de solo lectura sobre el release de servicio.

Cada respuesta de ``/v1`` es inmutable dentro de un release: lleva ``ETag`` por release y ``Cache-Control`` para que un caché
(Cloudflare) absorba la lectura, y responde 304 si el cliente ya la tiene. ``POST /internal/reload`` (solo desde localhost)
abre el release que apunta ``current``; si no cumple el esquema, sigue sirviendo el anterior.
"""

from __future__ import annotations

import hashlib
import os
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from gronestats.api import queries
from gronestats.api.store import ReleaseError, Store
from gronestats.web_bundle.schema import SCHEMA_VERSION

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=600"


class Tournament(str, Enum):
    apertura = "Apertura"
    clausura = "Clausura"
    acumulada = "Acumulada"


class Condition(str, Enum):
    general = "general"
    local = "local"
    visita = "visita"


class Values(str, Enum):
    promedio = "promedio"
    total = "total"


class Order(str, Enum):
    desc = "desc"
    asc = "asc"


SortKey = Enum("SortKey", {key: key for key in queries.LEAGUE_SORTS}, type=str)


def create_app(bundle_dir: Path | None = None, images_dir: Path | None = None) -> FastAPI:
    root = Path(__file__).resolve().parents[1]
    bundle_dir = Path(bundle_dir or os.getenv("GRONESTATS_WEB_BUNDLE") or root / "data" / "Liga 1 Peru" / "web")
    images_dir = Path(images_dir or os.getenv("GRONESTATS_IMAGES_DIR") or root / "images")
    store = Store(bundle_dir, images_dir)
    app = FastAPI(title="GroneStats API", version=SCHEMA_VERSION)
    app.state.store = store

    def run(function: Callable[..., dict[str, Any]], *args: Any) -> dict[str, Any]:
        try:
            return function(store.release, *args)
        except queries.NotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.middleware("http")
    async def immutable_per_release(request: Request, call_next):
        if request.method != "GET" or not request.url.path.startswith("/v1/"):
            return await call_next(request)
        etag = f'W/"{store.release.release_id}:{hashlib.sha1(str(request.url).encode()).hexdigest()[:16]}"'
        headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        response = await call_next(request)
        if response.status_code == 200:
            response.headers.update(headers)
        return response

    @app.get("/v1/release")
    def release() -> dict[str, Any]:
        return queries.release_info(store.release)

    @app.get("/v1/status")
    def status() -> dict[str, Any]:
        return queries.status(store.release)

    @app.get("/v1/seasons")
    def seasons() -> dict[str, Any]:
        return queries.seasons(store.release)

    @app.get("/v1/teams")
    def teams(season: int | None = None) -> dict[str, Any]:
        return queries.teams(store.release, season)

    @app.get("/v1/seasons/{season}/standings")
    def standings(season: int, tournament: Tournament | None = None, round: int | None = Query(default=None, ge=0)) -> dict[str, Any]:
        return run(queries.standings, season, tournament.value if tournament else None, round)

    @app.get("/v1/seasons/{season}/league-table")
    def league_table(
        season: int,
        tournament: Tournament | None = None,
        round: int | None = Query(default=None, ge=0),
        condition: Condition = Condition.general,
        values: Values = Values.promedio,
        sort: SortKey = SortKey.pts,  # type: ignore[assignment]
        order: Order = Order.desc,
    ) -> dict[str, Any]:
        return run(queries.league_table, season, tournament.value if tournament else None, round, condition.value, values.value, sort.value, order.value)

    @app.get("/v1/teams/{team_id}/seasons/{season}/matches")
    def team_matches(team_id: int, season: int) -> dict[str, Any]:
        return run(queries.team_matches, team_id, season)

    @app.get("/v1/teams/{team_id}/seasons/{season}/title-race")
    def team_title_race(team_id: int, season: int, tournament: Tournament | None = None) -> dict[str, Any]:
        return run(queries.team_title_race, team_id, season, tournament.value if tournament else None)

    @app.get("/v1/teams/{team_id}/seasons/{season}/players")
    def team_players(team_id: int, season: int) -> dict[str, Any]:
        return run(queries.team_players, team_id, season)

    @app.get("/v1/matches/{match_id}")
    def match(match_id: int) -> dict[str, Any]:
        return run(queries.match_detail, match_id)

    @app.get("/v1/players/{player_id}")
    def player(player_id: int, season: int | None = None) -> dict[str, Any]:
        return run(queries.player_profile, player_id, season)

    @app.get("/v1/players/{player_id}/shots")
    def player_shots(player_id: int, season: int | None = None) -> dict[str, Any]:
        return run(queries.player_shots, player_id, season)

    @app.get("/v1/players/{player_id}/heatmap")
    def player_heatmap(player_id: int, season: int | None = None) -> dict[str, Any]:
        return run(queries.player_heatmap, player_id, season)

    @app.post("/internal/reload")
    def reload(request: Request):
        host = request.client.host if request.client else ""
        if host not in LOCAL_HOSTS:
            raise HTTPException(status_code=403, detail="solo desde localhost")
        try:
            loaded = store.reload()
        except ReleaseError as exc:
            return JSONResponse(status_code=409, content={"reloaded": False, "error": str(exc), "release_id": store.release.release_id})
        return {"reloaded": True, "release_id": loaded.release_id}

    for folder in ("players", "teams"):
        if (images_dir / folder).exists():
            app.mount(f"/assets/{folder}", StaticFiles(directory=images_dir / folder), name=f"assets-{folder}")
    return app
