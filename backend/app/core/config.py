from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CobraQ"
    debug: bool = False

    # JWT
    secret_key: str = "cobraq_super_secret_key_change_this_in_production_32chars_minimum"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # AI Provider: "grok" (xAI, OpenAI-compatible) hoặc "anthropic" (legacy)
    ai_provider: str = "grok"
    ai_api_key: str = ""  # XAI_API_KEY cho Grok, ANTHROPIC_API_KEY cho Claude
    grok_api_key: str = ""  # legacy alias
    anthropic_api_key: str = ""  # legacy
    ai_base_url: str = "https://api.x.ai/v1"
    ai_model: str = "grok-3-mini"

    # Research pipeline. Local SLM is the target deployment; API is retained
    # only as a reference baseline and development fallback.
    cobraq_model_backend: str = "local"
    cobraq_base_model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    cobraq_adapter_path: str = "artifacts/adapters/history12_lora"
    cobraq_corpus_dir: str = "data/research/history12_kntt"
    cobraq_collection: str = "cobraq_history12_kntt_v1"
    cobraq_embedding_model: str = "intfloat/multilingual-e5-small"

    # Paths
    data_dir: str = "data"
    uploads_dir: str = "data/uploads"

@lru_cache
def get_settings() -> Settings:
    return Settings()
