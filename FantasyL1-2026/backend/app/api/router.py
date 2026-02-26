from fastapi import APIRouter

from app.api import admin, auth, catalog, fantasy, leagues, notifications, premium, public, ranking, zeroclaw

router = APIRouter()
router.include_router(auth.router)
router.include_router(catalog.router)
router.include_router(fantasy.router)
router.include_router(admin.router)
router.include_router(leagues.router)
router.include_router(ranking.router)
router.include_router(public.router)
router.include_router(premium.router)
router.include_router(notifications.router)
router.include_router(zeroclaw.router)
