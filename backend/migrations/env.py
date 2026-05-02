import asyncio
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from app.adapters.sqlalchemy.models import Base
from app.adapters.sqlalchemy.session import make_engine
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import Connection

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

REPO_ROOT = Path(__file__).resolve().parents[2]


class MigrationSettings(BaseSettings):
    alembic_database_url: str | None = None
    database_url: str

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


def get_database_url() -> str:
    settings = MigrationSettings()  # type: ignore[call-arg]
    return settings.alembic_database_url or settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = make_engine(get_database_url())

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
