import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from habits.storage.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    url = os.environ.get("HABITS_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    assert url is not None
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        context.configure(
            connection=supplied,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(_database_url())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
