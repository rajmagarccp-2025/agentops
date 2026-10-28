import re
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
    workflow_queue_backend: str = "database"
    workflow_pubsub_project_id: str | None = None
    workflow_pubsub_topic_id: str | None = None
    workflow_pubsub_subscription_id: str | None = None
    workflow_pubsub_poll_batch_size: int = 10
    workflow_pubsub_ack_extension_seconds: int = 60
    workflow_outbox_retention_days: int = 30
    workflow_worker_concurrency: int = 4
    workflow_job_timeout_seconds: int = 600
    workflow_job_lease_seconds: int = 900
    secret_expiry_scan_interval_seconds: int = 300
    audit_archive_after_days: int = 365
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50
    redis_cache_timeout_seconds: float = 0.1
    redis_cache_max_connections: int = 16
    secret_cache_ttl_seconds: int = 300
    secret_cache_max_value_bytes: int = 65_536
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: SecretStr = SecretStr("minioadmin")
    s3_bucket_name: str = "platform-artifacts"
    rag_document_storage_backend: str = "postgres"
    gcs_document_bucket: str | None = None
    rag_document_max_bytes: int = 10 * 1024 * 1024
    gcp_secret_manager_project_id: str | None = None
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
    llm_max_input_tokens: int = 32_768
    llm_max_output_tokens: int = 8_192
    llm_max_total_tokens: int = 40_960
    llm_tenant_requests_per_minute: int = 60
    llm_tenant_daily_token_budget: int = 100_000
    llm_provider: str = "mock"
    vertex_project_id: str | None = None
    vertex_location: str = "us-central1"
    vertex_model_reasoning: str = "gemini-2.5-flash"
    vertex_model_fast: str = "gemini-2.5-flash-lite"
    vertex_model_long_context: str = "gemini-2.5-pro"
    vertex_model_structured: str = "gemini-2.5-flash"
    vertex_max_output_tokens: int = 8192
    vertex_max_concurrent_requests: int = 16
    rag_embedding_provider: str = "hash"
    vertex_embedding_model: str = "text-embedding-005"
    vertex_embedding_dimensions: int = 768
    demo_mode: bool = False
    otel_service_name: str = "agentic-platform-api"
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_required: bool = False
    opa_url: str | None = None
    opa_required: bool = False
    opa_timeout_seconds: float = 1.0

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
            if self.rag_document_storage_backend != "gcs":
                raise ValueError("RAG_DOCUMENT_STORAGE_BACKEND must be 'gcs' in production")
        if self.llm_provider not in {"mock", "vertex"}:
            raise ValueError("LLM_PROVIDER must be 'mock' or 'vertex'")
        if self.rag_embedding_provider not in {"hash", "vertex"}:
            raise ValueError("RAG_EMBEDDING_PROVIDER must be 'hash' or 'vertex'")
        if self.llm_timeout_seconds <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be positive")
        if self.llm_timeout_seconds > 300:
            raise ValueError("LLM_TIMEOUT_SECONDS must not exceed 300 seconds")
        if self.opa_timeout_seconds <= 0 or self.opa_timeout_seconds > 30:
            raise ValueError("OPA_TIMEOUT_SECONDS must be between 0 and 30 seconds")
        if self.opa_required and not self.opa_url:
            raise ValueError("OPA_URL is required when OPA_REQUIRED=true")
        if not 0 <= self.llm_max_retries <= 5:
            raise ValueError("LLM_MAX_RETRIES must be between 0 and 5")
        if self.llm_max_input_tokens < 1:
            raise ValueError("LLM_MAX_INPUT_TOKENS must be positive")
        if self.llm_max_output_tokens < 1:
            raise ValueError("LLM_MAX_OUTPUT_TOKENS must be positive")
        if self.llm_max_total_tokens < 1:
            raise ValueError("LLM_MAX_TOTAL_TOKENS must be positive")
        if self.llm_max_total_tokens < (
            self.llm_max_input_tokens + self.llm_max_output_tokens
        ):
            raise ValueError(
                "LLM_MAX_TOTAL_TOKENS must cover the input and output token limits"
            )
        if self.llm_tenant_requests_per_minute < 1:
            raise ValueError("LLM_TENANT_REQUESTS_PER_MINUTE must be positive")
        if self.llm_tenant_daily_token_budget < 1:
            raise ValueError("LLM_TENANT_DAILY_TOKEN_BUDGET must be positive")
        if self.vertex_max_output_tokens < 1:
            raise ValueError("VERTEX_MAX_OUTPUT_TOKENS must be positive")
        if self.vertex_max_concurrent_requests < 1:
            raise ValueError("VERTEX_MAX_CONCURRENT_REQUESTS must be positive")
        if self.vertex_embedding_dimensions != 768:
            raise ValueError("VERTEX_EMBEDDING_DIMENSIONS must be 768 for the active schema")
        if (self.llm_provider == "vertex" or self.rag_embedding_provider == "vertex") and (
            not self.vertex_project_id or not self.vertex_location
        ):
            raise ValueError("Vertex providers require VERTEX_PROJECT_ID and VERTEX_LOCATION")
        if self.vertex_project_id and not re.fullmatch(
            r"[a-z][a-z0-9-]{4,28}[a-z0-9]", self.vertex_project_id
        ):
            raise ValueError("VERTEX_PROJECT_ID is invalid")
        if self.rag_document_storage_backend not in {"postgres", "gcs"}:
            raise ValueError("RAG_DOCUMENT_STORAGE_BACKEND must be 'postgres' or 'gcs'")
        if self.rag_document_storage_backend == "gcs" and not self.gcs_document_bucket:
            raise ValueError(
                "GCS_DOCUMENT_BUCKET is required when RAG_DOCUMENT_STORAGE_BACKEND=gcs"
            )
        if env_name == "production":
            if self.llm_provider != "vertex":
                raise ValueError("LLM_PROVIDER must be 'vertex' in production")
            if self.rag_embedding_provider != "vertex":
                raise ValueError("RAG_EMBEDDING_PROVIDER must be 'vertex' in production")
        if self.rag_document_max_bytes < 1:
            raise ValueError("RAG_DOCUMENT_MAX_BYTES must be positive")
        if self.rag_document_max_bytes > 10 * 1024 * 1024:
            raise ValueError("RAG_DOCUMENT_MAX_BYTES must not exceed 10 MiB")
        if self.redis_cache_timeout_seconds <= 0:
            raise ValueError("REDIS_CACHE_TIMEOUT_SECONDS must be positive")
        if self.redis_max_connections < 1:
            raise ValueError("REDIS_MAX_CONNECTIONS must be positive")
        if self.redis_cache_max_connections < 1:
            raise ValueError("REDIS_CACHE_MAX_CONNECTIONS must be positive")
        if self.workflow_queue_backend not in {"database", "pubsub"}:
            raise ValueError("WORKFLOW_QUEUE_BACKEND must be 'database' or 'pubsub'")
        if self.workflow_queue_backend == "pubsub" and not all(
            (
                self.workflow_pubsub_project_id,
                self.workflow_pubsub_topic_id,
                self.workflow_pubsub_subscription_id,
            )
        ):
            raise ValueError("Pub/Sub queue backend requires project, topic, and subscription IDs")
        if self.workflow_pubsub_poll_batch_size < 1:
            raise ValueError("WORKFLOW_PUBSUB_POLL_BATCH_SIZE must be positive")
        if not 10 <= self.workflow_pubsub_ack_extension_seconds <= 600:
            raise ValueError("WORKFLOW_PUBSUB_ACK_EXTENSION_SECONDS must be between 10 and 600")
        if self.workflow_outbox_retention_days < 1:
            raise ValueError("WORKFLOW_OUTBOX_RETENTION_DAYS must be positive")
        if self.secret_cache_ttl_seconds < 1:
            raise ValueError("SECRET_CACHE_TTL_SECONDS must be positive")
        if self.secret_cache_max_value_bytes < 1:
            raise ValueError("SECRET_CACHE_MAX_VALUE_BYTES must be positive")
        if self.gcp_secret_manager_project_id and not re.fullmatch(
            r"[a-z][a-z0-9-]{4,28}[a-z0-9]", self.gcp_secret_manager_project_id
        ):
            raise ValueError("GCP_SECRET_MANAGER_PROJECT_ID is invalid")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
