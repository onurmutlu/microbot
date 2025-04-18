import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_ID: str = os.environ.get("API_ID", "api-id")
    API_HASH: str = os.environ.get("API_HASH", "api-hash")
    BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "bot-token")
    SESSION_NAME: str = os.environ.get("SESSION_NAME", "session-name")
    USER_MODE: bool = os.environ.get("USER_MODE", "true")
    PHONE: str = os.environ.get("PHONE", "phone-number")
    
    DATABASE_URL: str = "sqlite:///./telegram_bot.db"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "your-secret-key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 gün
    SESSION_DIR: str = "sessions"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
