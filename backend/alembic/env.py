from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context
from app.core.config import get_settings
from app.models import (  # noqa: F401  (import to register tables on SQLModel.metadata)
    AILog,
    Article,
    DarijaGlossary,
    RawArticle,
    SocialPost,
    Source,
    Subscriber,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic runs synchronously; the app uses asyncpg, so swap the driver here.
_settings = get_settings()
_sync_url = _settings.database_url_str.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", _sync_url)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
