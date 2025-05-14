import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Dict, Union, Any
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Bot token ve api bilgileri
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_ID = os.getenv("API_ID", "")
API_HASH = os.getenv("API_HASH", "")

class Settings(BaseSettings):
    # Proje ismi
    PROJECT_NAME: str = "MicroBot API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # JWT Ayarları
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super_secret_key_change_in_production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    ALGORITHM: str = "HS256"
    
    # Veritabanı
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./microbot.db")
    
    # Telegram API
    BOT_TOKEN: str = BOT_TOKEN
    API_ID: str = API_ID
    API_HASH: str = API_HASH
    
    # Redis Cache
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "False").lower() in ("true", "1", "t")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    
    # Debug modu
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    # API Rate Limits
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", 60))
    
    # Admin root kullanıcısı
    ROOT_ADMIN_USERNAME: str = os.getenv("ROOT_ADMIN_USERNAME", "admin")
    ROOT_ADMIN_PASSWORD_HASH: str = os.getenv("ROOT_ADMIN_PASSWORD_HASH", "$2b$12$tVdyZmXSkfAoiF.JX8rFbeS2lXLkGiEJ/P4keSK4yYrGlnpVYyDCm")  # Default: "admin"
    
    # CORS ayarları
    CORS_ORIGINS: List[str] = [
        "http://localhost:5176", 
        "http://localhost:5175", 
        "http://localhost:5174", 
        "http://localhost:3000", 
        "http://localhost:8000",
        "https://microbot-panel.siyahkare.com",
        "https://microbot-miniapp.vercel.app",
        "https://microbot-api.siyahkare.com",
        "https://web.telegram.org",
        "https://t.me",
        "*"  # Tüm originler (üretim ortamında kaldırılmalı)
    ]
    
    # Log dosya yolları
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    ERROR_LOG_FILE: str = os.path.join(LOG_DIR, "errors.log")
    
    # Telegram oturumlar için dosya yolları
    SESSIONS_DIR: str = os.getenv("SESSIONS_DIR", "sessions")
    
    # Sunucu portu
    PORT: int = int(os.getenv("PORT", 8000))
    
    # İzin verilen dosya tipleri ve boyutları
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "gif", "mp4", "pdf", "doc", "docx", "xls", "xlsx", "txt"]
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", 10))  # MB cinsinden
    
    # Statik dosya yolu
    STATIC_DIR: str = "app/static"
    
    # Log ayarları
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Veritabanı ayarları
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    SESSION_NAME: str = "session-name"
    USER_MODE: bool = True
    PHONE: str = "phone-number"
    
    # PostgreSQL ayarları
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[str] = "5432"
    
    # API güvenlik ayarları
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Dosya yolları ve klasörler
    LOGS_DIR: str = "logs"
    
    # Hız limitleme ayarları
    RATE_LIMIT_PER_MINUTE: int = 20

    # Redis ayarları
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PREFIX: str = "microbot"
    REDIS_TTL: int = 600  # 10 dakika

    # Cache ayarları
    DEFAULT_CACHE_TTL: int = 60  # 1 dakika

    # GraphQL ayarları
    GRAPHQL_ENABLED: bool = True
    GRAPHQL_PATH: str = "/graphql"
    GRAPHIQL_ENABLED: bool = True

    # AI Özellikler
    AI_FEATURES_ENABLED: bool = True
    CONTENT_ANALYSIS_CACHE_TTL: int = 3600  # 1 saat
    CONTENT_OPTIMIZATION_ENABLED: bool = True

    # Prometheus metrikleri
    METRICS_ENABLED: bool = True
    METRICS_PATH: str = "/metrics"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=True,
        extra="allow"
    )

    def __init__(self, **data):
        super().__init__(**data)
        
        # PostgreSQL bağlantısı ayarlanması (.env'den gelmediyse)
        if self.DATABASE_URL.startswith("postgresql://") and "@localhost" in self.DATABASE_URL:
            if all([self.POSTGRES_USER, self.POSTGRES_PASSWORD, self.POSTGRES_DB, self.POSTGRES_HOST]):
                self.DATABASE_URL = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
        # Log klasörünü oluştur
        if not os.path.exists(self.LOGS_DIR):
            os.makedirs(self.LOGS_DIR)
            
        # Sessions klasörünü oluştur
        # Güvenli bir şekilde klasör oluştur
        try:
            os.makedirs(self.LOGS_DIR, exist_ok=True)
            os.makedirs(self.SESSIONS_DIR, exist_ok=True)
        except PermissionError as e:
            print(f"[WARNING] Klasör oluşturulamadı: {e}")


settings = Settings()
