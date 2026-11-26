from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parent.parent


def alembic_config(url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture
def migrated_db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """sqlite:///<tmp_path>/test.db upgraded to "head"; sets HABITS_DATABASE_URL to it."""
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setenv("HABITS_DATABASE_URL", url)
    command.upgrade(alembic_config(url), "head")
    return url
