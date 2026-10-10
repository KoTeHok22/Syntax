from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    app_name: str = "syntax"
    app_version: str = "0.1.0"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://syntax:syntax@localhost:5432/syntax"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60
    jwt_issuer: str = "syntax"
    pvn_oidc_issuer: str = ""
    pvn_oidc_audience: str = ""
    pvn_oidc_jwks_url: str = ""
    pvn_oidc_algorithms: list[str] = ["RS256"]
    pvn_oidc_http_timeout_seconds: float = 5
    pvn_oidc_cache_ttl_seconds: int = 300
    pvn_oidc_trusted_client_ids: list[str] = []
    pvn_oidc_id_claim: str = ""
    pvn_oidc_achievements_claim: str = ""
    ats_allowed_webhook_urls: list[str] = []
    ats_timeout_seconds: float = 5
    ats_webhook_secret: str = ""

    grade_cooldown_months: int = 3
    tasks_per_session: int = 20
    session_time_limit_minutes: int = 45

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_vision_model: str = ""
    llm_timeout_seconds: int = 240

    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = 1024
    embedding_timeout_seconds: int = 10
    embedding_failure_cooldown_seconds: int = 120
    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_model: str = ""
    rerank_timeout_seconds: int = 20
    rerank_top_n: int = 50

    @property
    def embeddings_enabled(self) -> bool:
        return bool(self.embedding_base_url and self.embedding_api_key and self.embedding_model)

    @property
    def rerank_enabled(self) -> bool:
        return bool(self.rerank_model and (self.rerank_base_url or self.embedding_base_url) and (self.rerank_api_key or self.embedding_api_key))

    html_render_enabled: bool = False
    html_render_timeout_seconds: float = 30
    html_render_viewport_width: int = 390
    html_render_viewport_height: int = 650

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    app_base_url: str = "http://localhost:8000"

    seed_demo: bool = False

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
