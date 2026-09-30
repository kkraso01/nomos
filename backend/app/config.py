from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    debug: bool = True
    root_dir: str = "/mnt/jellyfin/Projects/NOMOS/NOMOS_agent_handoff"
    database_url: str = "postgresql+psycopg://nomos:nomos@localhost:5432/nomos"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "nomos"
    s3_secret_key: str = "nomossecret"
    s3_bucket_public: str = "nomos-public"
    s3_bucket_private: str = "nomos-private"

    opensearch_url: str = "http://localhost:9200"
    opensearch_username: str = ""
    opensearch_password: str = ""

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480

    default_remote_ai_policy: str = "PUBLIC_ONLY"
    remote_ai_policy: str = "PUBLIC_ONLY"

    # NOMOS is a paid lawyer service. When True, the bulk-ingestion gate also
    # requires the source to be recorded as commercially reusable (a human
    # legal-clearance decision); no source may be ingested for resale otherwise.
    commercial_service_mode: bool = True

    # Server-side subscription usage enforcement (FREE/DEMO per-day search limits vs
    # PRO unlimited). Default off so local/dev + tests are unaffected; enable in prod.
    enforce_usage_limits: bool = False

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-v4-flash-0731"

    admin_email: str = "admin@nomos.local"
    admin_password: str = "adminpass"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()