from fastapi import APIRouter

from app.api.v1.endpoints import admin, licenses, telegram, miniapp

api_v1_router = APIRouter()
api_v1_router.include_router(admin.router)
api_v1_router.include_router(licenses.router)
api_v1_router.include_router(telegram.router)
api_v1_router.include_router(miniapp.router)
