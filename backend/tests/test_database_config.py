from pydantic import ValidationError

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
