import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.exc import IntegrityError

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
            context = MigrationContext.configure(
                conn, opts={"compare_server_default": True, "compare_type": True}
            )
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()
    assert diff == []


def test_upgrade_uses_supplied_connection(tmp_path: Path) -> None:
    url_a = f"sqlite:///{(tmp_path / 'a.db').as_posix()}"
    url_b = f"sqlite:///{(tmp_path / 'b.db').as_posix()}"
    cfg = alembic_config(url_a)
    engine_a = sa.create_engine(url_a)
    engine_b = sa.create_engine(url_b)
    try:
        with engine_b.connect() as conn_b:
            cfg.attributes["connection"] = conn_b
            command.upgrade(cfg, "head")
            conn_b.commit()
        tables_a = sa.inspect(engine_a).get_table_names()
        tables_b = sa.inspect(engine_b).get_table_names()
    finally:
        engine_a.dispose()
        engine_b.dispose()
    assert "habits" in tables_b
    assert "habits" not in tables_a


def test_migrated_constraints(migrated_db_url: str) -> None:
    engine = sa.create_engine(migrated_db_url)
    insert = sa.text(
        "INSERT INTO habits (name, frequency, created_at) VALUES ('x', :freq, '2026-01-01 00:00:00')"
    )
    try:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(insert, {"freq": "monthly"})
        with engine.begin() as conn:
            conn.execute(insert, {"freq": "daily"})
            archived = conn.execute(sa.text("SELECT archived FROM habits")).scalar_one()
    finally:
        engine.dispose()
    assert not archived


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
