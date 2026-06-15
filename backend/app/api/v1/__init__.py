"""API v1 router — mounts all v1 sub-routers."""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.entitlements import router as entitlements_router
from app.api.v1.quotas import router as quotas_router
from app.api.v1.users import router as users_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(entitlements_router)
api_router.include_router(quotas_router)
