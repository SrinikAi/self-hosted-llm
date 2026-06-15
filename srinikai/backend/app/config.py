"""Application settings, loaded from environment / .env file."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SriniKai"
    env: str = "development"

    # Database
    database_url: str = "sqlite:///./srinikai.db"

    # Auth / security
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_alg: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:5500"
    rate_limit_auth: str = "10/minute"
    rate_limit_chat: str = "30/minute"

    # Model backend
    llama_server_url: str = "http://localhost:8080"
    model_name: str = "SriniKai"
    request_timeout_seconds: int = 120
    max_input_chars: int = 16000
    max_history_messages: int = 20

    # Embeddings / RAG. Leave embeddings_url empty to use the local fallback.
    embeddings_url: str = ""
    embeddings_model: str = "SriniKai-embed"
    memory_top_k: int = 4
    memory_min_score: float = 0.20

    # Internet access (web tool)
    web_enabled: bool = True
    web_max_results: int = 4
    web_fetch_chars: int = 4000

    @property
    def is_prod(self) -> bool:
        return self.env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
