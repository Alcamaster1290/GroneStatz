import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api.router import router
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.scheduler import start_scheduler

logger = logging.getLogger(__name__)

settings = get_settings()
origin_regex = settings.CORS_ORIGIN_REGEX.strip() if settings.CORS_ORIGIN_REGEX else None
if origin_regex == "":
    origin_regex = None

allowed_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]
mobile_allowed_origins = [
    origin.strip()
    for origin in settings.MOBILE_CORS_ORIGINS.split(",")
    if origin.strip()
]
if settings.APP_ENV.lower() == "prod":
    for origin in (
        "https://fantasyliga1peru.com",
        "https://www.fantasyliga1peru.com",
    ):
        if origin not in allowed_origins:
            allowed_origins.append(origin)
for origin in mobile_allowed_origins:
    if origin not in allowed_origins:
        allowed_origins.append(origin)

app = FastAPI(title="Fantasy Liga 1 2026", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def _startup_scheduler() -> None:
    app.state.scheduler_task = start_scheduler()


@app.on_event("shutdown")
async def _shutdown_scheduler() -> None:
    task = getattr(app.state, "scheduler_task", None)
    if task:
        task.cancel()


@app.exception_handler(OperationalError)
def handle_db_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    logger.warning(
        "db_unavailable method=%s path=%s detail=%s",
        request.method,
        request.url.path,
        str(exc),
    )
    return JSONResponse(status_code=503, content={"detail": "db_unavailable"})


@app.exception_handler(IntegrityError)
def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    detail = "db_integrity_error"
    orig = getattr(exc, "orig", None)
    constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
    if constraint:
        detail = f"db_integrity_error:{constraint}"
    return JSONResponse(status_code=400, content={"detail": detail})


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unexpected_error")
    return JSONResponse(status_code=500, content={"detail": "server_error"})


@app.get("/health")
def health() -> dict:
    return {"ok": True, "env": settings.APP_ENV}


@app.get("/health/db")
def health_db():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"ok": True, "env": settings.APP_ENV, "db": "up"}
    except OperationalError as exc:
        logger.warning("health_db_unavailable detail=%s", str(exc))
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "env": settings.APP_ENV,
                "db": "down",
                "detail": "db_unavailable",
            },
        )
