import subprocess
import sys

import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from habits.storage.models import Base
from tests.conftest import REPO_ROOT, alembic_config


def test_upgrade_head(migrated_db_url: str) -> None:
    cfg = alembic_config(migrated_db_url)
    engine = sa.create_engine(migrated_db_url)
    try:
        with engine.connect() as conn:
            version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        tables = sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()
    assert version == ScriptDirectory.from_config(cfg).get_current_head()
    assert "habits" in tables


def test_no_drift(migrated_db_url: str) -> None:
    engine = sa.create_engine(migrated_db_url)
    try:
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    finally:
        engine.dispose()
    assert diff == []


def test_downgrade_base(migrated_db_url: str) -> None:
    command.downgrade(alembic_config(migrated_db_url), "base")
    engine = sa.create_engine(migrated_db_url)
    try:
        tables = sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()
    assert "habits" not in tables


def test_cli_heads(migrated_db_url: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-x", "dummy=1", "heads"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
