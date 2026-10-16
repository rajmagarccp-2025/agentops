from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from platform_api import (
    identity_models,  # noqa: F401
    models,  # noqa: F401
    workflow_queue,  # noqa: F401
)
from platform_api.agents import models as agent_models  # noqa: F401
from platform_api.changes import models as change_models  # noqa: F401
from platform_api.config import get_settings
from platform_api.database import Base
from platform_api.finops import models as finops_models  # noqa: F401
from platform_api.governance import models as governance_models  # noqa: F401
from platform_api.incidents import models as incident_models  # noqa: F401
from platform_api.integrations import models as integration_models  # noqa: F401
from platform_api.inventory import models as inventory_models  # noqa: F401
from platform_api.learning import models as learning_models  # noqa: F401
from platform_api.llmops_service import models as llmops_models  # noqa: F401
from platform_api.mcp import models as mcp_models  # noqa: F401
from platform_api.rag_service import models as rag_models  # noqa: F401
from platform_api.remediation import models as remediation_models  # noqa: F401
from platform_api.secrets import models as secret_models  # noqa: F401
from platform_api.security_investigation import models as security_models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
