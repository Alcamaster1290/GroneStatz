from fastapi import APIRouter

from app.api import admin, auth, catalog, fantasy

router = APIRouter()
router.include_router(auth.router)
router.include_router(catalog.router)
router.include_router(fantasy.router)
router.include_router(admin.router)
