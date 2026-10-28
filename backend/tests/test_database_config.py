from pydantic import ValidationError

from platform_api import database
from platform_api.config import Settings


def test_database_pool_settings_are_configurable() -> None:
    settings = Settings(
        database_pool_size=12,
        database_max_overflow=24,
        database_pool_timeout_seconds=45,
        database_pool_recycle_seconds=900,
    )

    assert settings.database_pool_size == 12
    assert settings.database_max_overflow == 24
    assert settings.database_pool_timeout_seconds == 45
    assert settings.database_pool_recycle_seconds == 900


def test_database_engine_uses_configured_pool_settings(monkeypatch) -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://platform:password@db.example/platform",
        database_pool_size=12,
        database_max_overflow=24,
        database_pool_timeout_seconds=45,
        database_pool_recycle_seconds=900,
    )
    engine = type("EngineStub", (), {"connect": lambda self: _ConnectionContext()})()
    engine_options = {}

    def create_engine_stub(url: str, **kwargs: object) -> object:
        engine_options.update(kwargs)
        return engine

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(database, "create_engine", create_engine_stub)

    assert database.create_app_engine() is engine
    assert engine_options == {
        "future": True,
        "pool_pre_ping": True,
        "pool_size": 12,
        "max_overflow": 24,
        "pool_timeout": 45,
        "pool_recycle": 900,
    }


class _ConnectionContext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: object) -> None:
        return None


def test_production_rejects_local_database_and_missing_oidc_configuration() -> None:
    try:
        Settings(
            app_env="production",
            demo_mode=False,
            database_url="postgresql://postgres:postgres@localhost:5432/platform",
            redis_url="redis://localhost:6379/0",
            oidc_issuer_url=None,
            oidc_client_id=None,
            jwt_demo_secret="production-jwt-secret-32-char-max",
        )
    except ValidationError as exc:
        messages = str(exc)
        assert (
            "DATABASE_URL" in messages or "OIDC_ISSUER_URL" in messages or "REDIS_URL" in messages
        )
    else:
        raise AssertionError("Production settings should reject local-only infrastructure defaults")


def test_production_rejects_mock_model_providers() -> None:
    required_settings = {
        "app_env": "production",
        "demo_mode": False,
        "database_url": "postgresql+psycopg://user:pass@db.example/platform",
        "redis_url": "redis://redis.example:6379/0",
        "oidc_issuer_url": "https://issuer.example",
        "oidc_client_id": "platform",
        "jwt_demo_secret": "production-jwt-secret-32-char-max",
        "rag_document_storage_backend": "gcs",
        "gcs_document_bucket": "synthetic-bucket",
        "vertex_project_id": "synthetic-project",
    }

    try:
        Settings(**required_settings, llm_provider="mock")
    except ValidationError as exc:
        assert "LLM_PROVIDER must be 'vertex'" in str(exc)
    else:
        raise AssertionError("Production must reject mock LLM providers")

    try:
        Settings(
            **required_settings,
            llm_provider="vertex",
            rag_embedding_provider="hash",
        )
    except ValidationError as exc:
        assert "RAG_EMBEDDING_PROVIDER must be 'vertex'" in str(exc)
    else:
        raise AssertionError("Production must reject hash embedding providers")
