from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "CobraQ"
    debug: bool = False

    # JWT
    secret_key: str = "cobraq_super_secret_key_change_this_in_production_32chars_minimum"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # AI
    anthropic_api_key: str = "YOUR_KEY_HERE"

    # Paths
    data_dir: str = "data"
    uploads_dir: str = "data/uploads"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
