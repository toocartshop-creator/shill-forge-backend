from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "ShillForge API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    ALLOWED_ORIGINS: List[str] = ["*"]
    MONGODB_URL: str = "mongodb+srv://user:pass@cluster.mongodb.net/shillforge"
    MONGODB_DB_NAME: str = "shillforge"
    TELEGRAM_BOT_TOKEN: str = ""
    JWT_SECRET_KEY: str = "change-this-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 43200
    ADMIN_SECRET_KEY: str = "change-this-admin-secret"
    USE_REDIS: bool = False
    POINTS_PER_REFERRAL: int = 200
    POINTS_REFERRER_BONUS: int = 50
    DAILY_TAP_LIMIT: int = 1000
    TAP_ENERGY_MAX: int = 500
    TOKENS_PER_POINTS_RATIO: int = 2
    VIDEO_WATCH_REWARD: int = 500
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
