from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from habits.api.app import create_app
from habits.api.deps import get_now, get_today
from habits.api.settings import Settings

FIXED_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
FIXED_TODAY = date(2026, 1, 15)


@pytest.fixture
def client(migrated_db_url: str) -> Iterator[TestClient]:
    app = create_app(Settings(database_url=migrated_db_url))
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    app.dependency_overrides[get_today] = lambda: FIXED_TODAY
    with TestClient(app) as test_client:
        yield test_client
    app.state.engine.dispose()
