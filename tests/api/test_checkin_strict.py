from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from habits.api.app import create_app
from habits.api.deps import get_now
from habits.api.settings import Settings


def _make_habit(client: TestClient) -> int:
    response = client.post("/habits", json={"name": "Read"})
    assert response.status_code == 201
    return response.json()["id"]


def _error_code(response) -> str:
    return response.json()["error"]["code"]


@pytest.mark.parametrize("day", ["1768435200", "2026-01-15T00:00:00"])
def test_delete_rejects_timestamp_day(client: TestClient, day: str) -> None:
    habit_id = _make_habit(client)
    created = client.post(f"/habits/{habit_id}/checkins", json={"day": "2026-01-15"})
    assert created.status_code == 201

    response = client.delete(f"/habits/{habit_id}/checkins/{day}")
    assert response.status_code == 422
    assert _error_code(response) == "validation_error"

    listed = client.get(f"/habits/{habit_id}/checkins")
    assert [c["day"] for c in listed.json()] == ["2026-01-15"]


@pytest.mark.parametrize(
    "query",
    ["start=1768435200", "end=2026-01-15T00:00", "start=2026-01-15T00:00:00"],
)
def test_list_rejects_non_iso_dates(client: TestClient, query: str) -> None:
    habit_id = _make_habit(client)
    response = client.get(f"/habits/{habit_id}/checkins?{query}")
    assert response.status_code == 422
    assert _error_code(response) == "validation_error"


def test_list_accepts_iso_dates(client: TestClient) -> None:
    habit_id = _make_habit(client)
    client.post(f"/habits/{habit_id}/checkins", json={"day": "2026-01-15"})
    response = client.get(f"/habits/{habit_id}/checkins?start=2026-01-01&end=2026-01-31")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_null_body_rejected(client: TestClient) -> None:
    habit_id = _make_habit(client)

    response = client.post(
        f"/habits/{habit_id}/checkins",
        content="null",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert _error_code(response) == "validation_error"
    assert client.get(f"/habits/{habit_id}/checkins").json() == []

    no_body = client.post(f"/habits/{habit_id}/checkins")
    assert no_body.status_code == 201
    assert no_body.json()["day"] == "2026-01-15"

    habit_id_2 = _make_habit(client)
    empty = client.post(f"/habits/{habit_id_2}/checkins", json={})
    assert empty.status_code == 201
    assert empty.json()["day"] == "2026-01-15"


@pytest.fixture
def now_calls() -> list[int]:
    return []


@pytest.fixture
def tokyo_client(migrated_db_url: str, now_calls: list[int]) -> Iterator[TestClient]:
    app = create_app(Settings(database_url=migrated_db_url, timezone="Asia/Tokyo"))

    def fixed_now() -> datetime:
        now_calls.append(1)
        return datetime(2026, 1, 14, 15, 30, tzinfo=UTC)

    app.dependency_overrides[get_now] = fixed_now
    with TestClient(app) as test_client:
        yield test_client
    app.state.engine.dispose()


def test_today_derived_from_now(tokyo_client: TestClient, now_calls: list[int]) -> None:
    habit_id = _make_habit(tokyo_client)

    now_calls.clear()
    created = tokyo_client.post(f"/habits/{habit_id}/checkins")
    assert created.status_code == 201
    assert created.json()["day"] == "2026-01-15"
    assert len(now_calls) == 1

    now_calls.clear()
    stats = tokyo_client.get(f"/habits/{habit_id}/stats")
    assert stats.status_code == 200
    assert stats.json()["as_of"] == "2026-01-15"
    assert len(now_calls) == 1
