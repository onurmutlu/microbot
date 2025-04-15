import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./telegram_bot.db"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "your-secret-key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 gün
    SESSION_DIR: str = "sessions"
    
    class Config:
        env_file = ".env"

settings = Settings()
