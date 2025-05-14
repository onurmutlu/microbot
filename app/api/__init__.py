from fastapi import APIRouter

from app.api.v1 import api_v1_router as v1_router

router = APIRouter(prefix="/api")

# API versiyonlarını ekle
router.include_router(v1_router)
