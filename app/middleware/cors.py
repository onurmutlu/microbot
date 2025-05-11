from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)

def add_cors_middleware(
    app: FastAPI,
    allow_origins: Optional[List[str]] = None,
    allow_origin_regex: Optional[str] = None,
    allow_credentials: bool = True,
    allow_methods: Optional[List[str]] = None,
    allow_headers: Optional[List[str]] = None,
    max_age: int = 600
):
    """
    FastAPI uygulamasına CORS middleware ekler.
    
    Args:
        app: FastAPI uygulaması
        allow_origins: İzin verilen originler listesi
        allow_origin_regex: İzin verilen origin regex
        allow_credentials: Credentials izni
        allow_methods: İzin verilen HTTP metodları
        allow_headers: İzin verilen HTTP header'ları
        max_age: Preflight sonuçları önbellek süresi (saniye)
    """
    
    # Ayarları konfigürasyondan al veya varsayılanları kullan
    if allow_origins is None:
        allow_origins = getattr(settings, "CORS_ORIGINS", ["*"])
    
    if allow_origin_regex is None:
        allow_origin_regex = getattr(settings, "CORS_ORIGIN_REGEX", None)
    
    if allow_methods is None:
        allow_methods = getattr(settings, "CORS_METHODS", ["*"])
    
    if allow_headers is None:
        allow_headers = getattr(settings, "CORS_HEADERS", ["*"])
    
    # CORS middleware'ini ekle
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
        max_age=max_age,
        expose_headers=["Content-Disposition", "X-Request-ID", "X-Rate-Limit-Limit", "X-Rate-Limit-Remaining", "X-Rate-Limit-Reset"]
    )
    
    # Log bilgisi
    origins_info = ", ".join(allow_origins) if allow_origins != ["*"] else "all origins"
    logger.info(f"CORS middleware eklendi. İzin verilen origins: {origins_info}")
    
    return app

def setup_secure_cors(app: FastAPI, frontend_url: str):
    """
    Production ortamı için güvenli CORS yapılandırması yapar.
    
    Args:
        app: FastAPI uygulaması
        frontend_url: Frontend URL'i
    """
    # Güvenli CORS ayarları
    allow_origins = [frontend_url]
    
    # Telegram web app URL'i ekleniyor
    if "t.me" not in allow_origins:
        allow_origins.append("https://web.telegram.org")
    
    # Geliştirme ortamı için localhost ekleniyor
    if settings.DEBUG:
        allow_origins.extend([
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:5000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5000"
        ])
    
    # Güvenli header listesi
    secure_headers = [
        "Accept",
        "Accept-Language",
        "Authorization",
        "Content-Type",
        "Origin",
        "Referer",
        "User-Agent",
        "X-Requested-With",
        "X-CSRF-Token",
        "X-Telegram-Init-Data",
        "X-Api-Key"
    ]
    
    # Güvenli metodlar
    secure_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    
    # CORS middleware'ini ekle
    return add_cors_middleware(
        app=app,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=secure_methods,
        allow_headers=secure_headers,
        max_age=3600  # 1 saat
    ) 