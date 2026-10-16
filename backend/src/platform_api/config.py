from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    api_version: str = "v1"
    database_url: str = "postgresql+psycopg://platform:platform@localhost:5432/platform"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 1_800
    workflow_queue_max_pending: int = 1_000
    workflow_worker_concurrency: int = 4
    workflow_job_timeout_seconds: int = 600
    workflow_job_lease_seconds: int = 900
    secret_expiry_scan_interval_seconds: int = 300
    audit_archive_after_days: int = 365
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: SecretStr = SecretStr("minioadmin")
    s3_bucket_name: str = "platform-artifacts"
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    oidc_audience: str | None = "agentic-platform-api"
    oidc_public_key: str | None = None
    oidc_algorithms: list[str] = ["RS256", "HS256"]
    jwt_demo_secret: SecretStr = SecretStr("local-demo-secret-change-me-32-bytes")
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "agentic-platform"
    jwt_audience: str = "agentic-platform-api"
    jwt_demo_token_minutes: int = 30
    llm_max_retries: int = 1
    llm_timeout_seconds: float = 30.0
    demo_mode: bool = False
    otel_service_name: str = "agentic-platform-api"
    otel_exporter_otlp_endpoint: str | None = None

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_security_defaults(self) -> "Settings":
        env_name = self.app_env.lower()
        local_secret = "local-demo-secret-change-me-32-bytes"
        dev_template_secret = "replace-with-a-long-random-secret-at-least-32-bytes"
        current_secret = self.jwt_demo_secret.get_secret_value()

        if (not self.demo_mode or env_name == "production") and (
            current_secret in (local_secret, dev_template_secret)
        ):
            raise ValueError("JWT_DEMO_SECRET must be replaced outside demo mode")

        if env_name == "production":
            if self.demo_mode:
                raise ValueError("DEMO_MODE must be disabled in production")
            if not self.database_url or self.database_url.strip() == "":
                raise ValueError("DATABASE_URL must be configured for production")
            database_lower = self.database_url.lower()
            if (
                "localhost" in database_lower
                or "127.0.0.1" in database_lower
                or database_lower.startswith("sqlite")
            ):
                raise ValueError(
                    "DATABASE_URL must not use local dev SQLite or localhost values in production"
                )
            if self.redis_url and (
                "localhost" in self.redis_url.lower() or "127.0.0.1" in self.redis_url.lower()
            ):
                raise ValueError("REDIS_URL must not use localhost in production")
            if not self.oidc_issuer_url or not self.oidc_client_id:
                raise ValueError(
                    "OIDC_ISSUER_URL and OIDC_CLIENT_ID must be configured in production"
                )

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
