from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from pathlib import Path

class Settings(BaseSettings):
    # Temel Ayarlar
    PROJECT_NAME: str = "MicroBot"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # PostgreSQL Ayarları
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    SQLALCHEMY_DATABASE_URI: Optional[str] = None
    
    # JWT Ayarları
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 gün
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Telegram Ayarları
    TELEGRAM_API_ID: Optional[int] = None
    TELEGRAM_API_HASH: Optional[str] = None
    
    # Redis Ayarları
    REDIS_URL: str = "redis://redis:6379/0"
    
    # CORS Ayarları
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Session Ayarları
    SESSION_DIR: str = "sessions"
    
    # Worker Ayarları
    GUNICORN_WORKERS: int = 4
    MAX_WORKERS: int = 8
    WORKER_CONCURRENCY: int = 10
    
    # Backup Ayarları
    BACKUP_RETENTION_DAYS: int = 7
    BACKUP_SCHEDULE: str = "0 0 * * *"
    BACKUP_S3_BUCKET: Optional[str] = None
    BACKUP_S3_ACCESS_KEY: Optional[str] = None
    BACKUP_S3_SECRET_KEY: Optional[str] = None
    
    # SSL Ayarları
    SSL_CERT_PATH: Optional[str] = None
    SSL_KEY_PATH: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # PostgreSQL URI oluştur
        if not self.SQLALCHEMY_DATABASE_URI:
            self.SQLALCHEMY_DATABASE_URI = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
            )
        
        # Session dizinini oluştur
        session_dir = Path(self.SESSION_DIR)
        session_dir.mkdir(parents=True, exist_ok=True)

settings = Settings() 