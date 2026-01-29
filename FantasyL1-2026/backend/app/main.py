from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api.router import router
from app.core.config import get_settings
from app.services.scheduler import start_scheduler

settings = get_settings()
origin_regex = settings.CORS_ORIGIN_REGEX.strip() if settings.CORS_ORIGIN_REGEX else None
if origin_regex == "":
    origin_regex = None

app = FastAPI(title="Fantasy Liga 1 2026", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
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
    return JSONResponse(status_code=503, content={"detail": "db_unavailable"})


@app.get("/health")
def health() -> dict:
    return {"ok": True, "env": settings.APP_ENV}
