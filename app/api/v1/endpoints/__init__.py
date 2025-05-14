from fastapi import APIRouter

from app.api.v1.endpoints import auth, admin, licenses, telegram, dashboard_api, ai_insights, miniapp
from app.api.v1.endpoints.graphql import graphql_router, router as graphql_api_router

router = APIRouter(prefix="/v1")

# API endpoint'lerini ekle
router.include_router(auth.router)
router.include_router(admin.router)
router.include_router(licenses.router)
router.include_router(telegram.router)
router.include_router(dashboard_api.router)
router.include_router(ai_insights.router)
router.include_router(miniapp.router)
# GraphQL router'ı ekle - doğrudan router'ı kullan, graphql_router strawberry grafik arayüzü için
router.include_router(graphql_api_router)
