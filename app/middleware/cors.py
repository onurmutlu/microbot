from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import logging

from app.config import settings

logger = logging.getLogger("app.middleware.cors")

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

def setup_secure_cors(app: FastAPI):
    """
    FastAPI uygulaması için güvenli CORS ayarlarını yapılandırır.
    
    CORS (Cross-Origin Resource Sharing) ayarları, API'nin hangi kaynaklardan
    gelen isteklere yanıt vereceğini belirler.
    """
    try:
        # Ayarlardan izin verilen kaynakları al
        origins = settings.CORS_ORIGINS

        # CORS middleware'i ekle
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=settings.CORS_ALLOW_METHODS,
            allow_headers=["*"],
            expose_headers=[
                "Content-Disposition", 
                "X-Request-ID", 
                "X-Rate-Limit-Limit", 
                "X-Rate-Limit-Remaining", 
                "X-Rate-Limit-Reset"
            ],
            max_age=3600  # 1 saat
        )
        
        logger.info(f"CORS ayarları yapılandırıldı. İzin verilen kaynaklar: {origins}")
        
        # Uyarı: Eğer * (tüm kaynaklar) izin veriliyorsa, güvenlik uyarısı göster
        if "*" in origins:
            logger.warning(
                "GÜVENLİK UYARISI: CORS ayarlarında tüm kaynaklara (*) izin verildi. "
                "Üretim ortamında yalnızca güvenilen kaynakları açıkça belirtin."
            )
    except Exception as e:
        logger.error(f"CORS ayarları yapılandırılırken hata oluştu: {str(e)}")
        # Hata durumunda varsayılan güvenli ayarları kullan
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:8000"],  # Sadece yerel geliştirme
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
            max_age=3600
        )
        logger.info("Güvenli varsayılan CORS ayarları uygulandı")

def get_cors_info():
    """
    Mevcut CORS yapılandırması hakkında bilgi döndürür.
    """
    return {
        "origins": settings.CORS_ORIGINS,
        "allow_credentials": settings.CORS_ALLOW_CREDENTIALS,
        "allow_methods": settings.CORS_ALLOW_METHODS,
        "max_age": 3600
    } 