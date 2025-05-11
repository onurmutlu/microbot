from fastapi import APIRouter, Depends, Request
from strawberry.fastapi import GraphQLRouter
from typing import Optional
from fastapi.responses import JSONResponse
from fastapi import status

from app.api.v1.endpoints.graphql.schema import schema, get_context
from app.config import settings
from app.services.cache_service import cache_service

# GraphQL router'ı oluştur
graphql_router = GraphQLRouter(
    schema=schema,
    context_getter=get_context,
    graphiql=settings.GRAPHIQL_ENABLED  # Yapılandırmadan GraphiQL durumunu al
)

# Ana router
router = APIRouter(tags=["GraphQL"])

# GraphQL endpoint'lerini kaydet
router.include_router(graphql_router, prefix="/graphql")

# GraphQL durumunu kontrol eden endpoint
@router.get("/graphql/info", response_model=None)
async def graphql_info():
    """GraphQL durumu hakkında bilgi verir"""
    try:
        introspection_enabled = settings.GRAPHIQL_ENABLED
        
        return {
            "status": "online",
            "graphiql_enabled": settings.GRAPHIQL_ENABLED,
            "schema_version": getattr(settings, "GRAPHQL_SCHEMA_VERSION", "1.0"),
            "endpoint": "/api/v1/graphql",
            "introspection": "enabled" if introspection_enabled else "disabled",
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": str(e)}
        )

# GraphQL kullanılabilirlik kontrolü
@router.get("/health", include_in_schema=False)
async def graphql_health():
    """
    GraphQL API sağlık kontrolü
    """
    if not settings.GRAPHQL_ENABLED:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "disabled", "message": "GraphQL API is disabled"}
        )
    
    return {"status": "ok", "message": "GraphQL API is operational"} 