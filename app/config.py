import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

class Settings(BaseSettings):
    # Proje ismi
    PROJECT_NAME: str = "MicroBot API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    API_ID: int = 12345  # Varsayılan değer
    API_HASH: str = "your_api_hash"  # Varsayılan değer
    BOT_TOKEN: str = "your_bot_token"  # Varsayılan değer
    SESSION_NAME: str = "session-name"
    USER_MODE: bool = True
    PHONE: str = "phone-number"
    
    # Veritabanı ayarları
    DATABASE_URL: str = "sqlite:///./microbot.db"  # Varsayılan olarak SQLite
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    SECRET_KEY: str = "your_secret_key"  # Varsayılan değer
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SESSION_DIR: str = "sessions"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # PostgreSQL ayarları
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[str] = "5432"
    
    # API güvenlik ayarları
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Dosya yolları ve klasörler
    LOGS_DIR: str = "logs"
    
    # Izleme ve loglama seviyesi
    LOG_LEVEL: str = "INFO"
    
    # Hız limitleme ayarları
    RATE_LIMIT_PER_MINUTE: int = 20

    # Redis ayarları
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    
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
        if not os.path.exists(self.SESSION_DIR):
            os.makedirs(self.SESSION_DIR)

settings = Settings()
