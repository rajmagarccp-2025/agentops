from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from platform_api.config import get_settings


class Base(DeclarativeBase):
    pass


def get_resolved_db_url(url: str) -> str:
    # In local development outside docker container, replace 'postgres' host with '127.0.0.1'
    if "@postgres:" in url or "@postgres/" in url:
        import os

        if not os.path.exists("/.dockerenv"):
            url = url.replace("@postgres:", "@127.0.0.1:").replace("@postgres/", "@127.0.0.1/")
    if "postgresql" in url and "connect_timeout" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}connect_timeout=1"
    return url


db_url = get_resolved_db_url(get_settings().database_url)


def create_app_engine():
    settings = get_settings()
    raw_url = settings.database_url
    url = get_resolved_db_url(raw_url)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, future=True)

    try:
        eng = create_engine(
            url,
            future=True,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=2,
            pool_recycle=settings.database_pool_recycle_seconds,
        )
        # Test connection with a fast 2-second limit.
        with eng.connect():
            pass
        return eng
    except Exception as exc:
        if settings.app_env.lower() == "production":
            raise RuntimeError(
                "Production database connection failed; refusing to silently fall back "
                "to local SQLite storage."
            ) from exc
        print(f"Warning: Primary DB unavailable ({exc}), falling back to SQLite platform_dev.db")
        return create_engine(
            "sqlite:///./platform_dev.db",
            connect_args={"check_same_thread": False},
            future=True,
        )


engine = create_app_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _ensure_missing_columns() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table in Base.metadata.sorted_tables:
            table_name = table.name
            if not inspector.has_table(table_name):
                continue
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name in existing_cols:
                    continue
                column_type = column.type.compile(dialect=engine.dialect)
                stmt = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {column_type}"
                conn.execute(text(stmt))


def _ensure_audit_append_only_triggers() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        trigger_names = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name IN ('audit_logs', 'audit_log_archive')")
            ).fetchall()
        }
        for table in ("audit_logs", "audit_log_archive"):
            for action in ("no_update", "no_delete"):
                trigger_name = f"{table}_{action}"
                if trigger_name in trigger_names:
                    continue
                conn.execute(
                    text(
                        f"CREATE TRIGGER {trigger_name} BEFORE {'UPDATE' if action == 'no_update' else 'DELETE'} "
                        f"ON {table} BEGIN SELECT RAISE(ABORT, 'audit log tables are append-only'); END"
                    )
                )


def init_db() -> None:
    try:
        import platform_api.identity_models  # noqa
        import platform_api.agents.models  # noqa
        import platform_api.incidents.models  # noqa
        import platform_api.finops.models  # noqa
        import platform_api.llmops_service.models  # noqa
        import platform_api.secrets.models  # noqa
        import platform_api.inventory.models  # noqa
        import platform_api.learning.models  # noqa
        import platform_api.rag_service.models  # noqa
        import platform_api.remediation.models  # noqa
        import platform_api.security_investigation.models  # noqa
        import platform_api.governance.models  # noqa
        import platform_api.changes.models  # noqa
        import platform_api.integrations.models  # noqa
        import platform_api.mcp.models  # noqa
        import platform_api.workflow_queue  # noqa

        Base.metadata.create_all(bind=engine)
        _ensure_missing_columns()
        _ensure_audit_append_only_triggers()

        with engine.begin() as conn:
            inspector = inspect(conn)
            if "llm_requests" in inspector.get_table_names():
                existing_cols = {c["name"] for c in inspector.get_columns("llm_requests")}
                for col, col_type in [
                    ("model_id", "VARCHAR(36)"),
                    ("user_id", "VARCHAR(255)"),
                    ("project_id", "VARCHAR(36)"),
                    ("environment_id", "VARCHAR(36)"),
                    ("error_message", "VARCHAR(1000)"),
                ]:
                    if col not in existing_cols:
                        conn.execute(text(f"ALTER TABLE llm_requests ADD COLUMN {col} {col_type}"))
    except Exception as exc:
        print(f"Database initialization warning: {exc}")


init_db()


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
