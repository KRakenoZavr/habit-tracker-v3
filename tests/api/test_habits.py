from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from habits.api.app import create_app
from habits.api.settings import Settings
from habits.core import services
from habits.storage.repository import SqlHabitRepository

FIXED_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def _create(client: TestClient, **body: object) -> dict:
    response = client.post("/habits", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_habit(client: TestClient) -> None:
    response = client.post("/habits", json={"name": "  Read  ", "description": "20 pages"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] >= 1
    assert body["name"] == "Read"
    assert body["description"] == "20 pages"
    assert body["frequency"] == "daily"
    assert body["target_per_week"] is None
    assert body["archived"] is False
    assert datetime.fromisoformat(body["created_at"]) == FIXED_NOW
    assert datetime.fromisoformat(body["created_at"]).utcoffset() == timedelta(0)


def test_create_habit_weekly(client: TestClient) -> None:
    body = _create(client, name="Run", frequency="weekly", target_per_week=3)
    assert body["frequency"] == "weekly"
    assert body["target_per_week"] == 3


def test_create_habit_blank_name(client: TestClient) -> None:
    response = client.post("/habits", json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_habit"


def test_create_habit_weekly_without_target(client: TestClient) -> None:
    response = client.post("/habits", json={"name": "Run", "frequency": "weekly"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_habit"


def test_create_habit_name_too_long(client: TestClient) -> None:
    response = client.post("/habits", json={"name": "x" * 101})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_get_habit(client: TestClient) -> None:
    created = _create(client, name="Read")
    response = client.get(f"/habits/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_habit_missing(client: TestClient) -> None:
    response = client.get("/habits/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "habit_not_found"


def test_get_habit_bad_id(client: TestClient) -> None:
    response = client.get("/habits/abc")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_habits(client: TestClient) -> None:
    first = _create(client, name="A")
    second = _create(client, name="B")
    third = _create(client, name="C")
    client.patch(f"/habits/{second['id']}", json={"archived": True})

    visible = client.get("/habits")
    assert visible.status_code == 200
    assert [h["id"] for h in visible.json()] == [first["id"], third["id"]]

    everything = client.get("/habits", params={"include_archived": "true"})
    assert everything.status_code == 200
    assert [h["id"] for h in everything.json()] == [first["id"], second["id"], third["id"]]


def test_update_habit(client: TestClient) -> None:
    created = _create(client, name="Read")
    response = client.patch(f"/habits/{created['id']}", json={"archived": True})
    assert response.status_code == 200
    assert response.json()["archived"] is True
    assert response.json()["name"] == "Read"


def test_update_habit_to_weekly(client: TestClient) -> None:
    created = _create(client, name="Read")
    response = client.patch(f"/habits/{created['id']}", json={"frequency": "weekly", "target_per_week": 4})
    assert response.status_code == 200
    body = response.json()
    assert body["frequency"] == "weekly"
    assert body["target_per_week"] == 4


def test_update_habit_missing(client: TestClient) -> None:
    response = client.patch("/habits/999", json={"archived": True})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "habit_not_found"


def test_delete_habit(client: TestClient) -> None:
    created = _create(client, name="Read")
    response = client.delete(f"/habits/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/habits/{created['id']}").status_code == 404


def test_delete_habit_missing(client: TestClient) -> None:
    response = client.delete("/habits/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "habit_not_found"


def test_write_committed_before_response(client: TestClient) -> None:
    created = _create(client, name="Read")
    listed = client.get("/habits").json()
    assert [h["id"] for h in listed] == [created["id"]]


def test_commit_happens_before_response_start(migrated_db_url: str) -> None:
    app = create_app(Settings(database_url=migrated_db_url))
    seen_at_response_start: list[list[int]] = []

    async def probe(scope: Any, receive: Any, send: Any) -> None:
        async def spying_send(message: Any) -> None:
            if message["type"] == "http.response.start" and scope["method"] == "POST":
                with app.state.session_factory() as other:
                    habits = services.list_habits(SqlHabitRepository(other), True)
                    seen_at_response_start.append([h.id for h in habits])
            await send(message)

        await app(scope, receive, spying_send)

    try:
        with TestClient(probe) as test_client:
            created = _create(test_client, name="Read")
    finally:
        app.state.engine.dispose()

    assert seen_at_response_start == [[created["id"]]]


def test_create_rejects_coerced_types(client: TestClient) -> None:
    for bad in (True, "3"):
        response = client.post("/habits", json={"name": "Run", "target_per_week": bad})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
    assert client.get("/habits", params={"include_archived": "true"}).json() == []


def test_update_rejects_coerced_types(client: TestClient) -> None:
    created = _create(client, name="Read")
    for payload in ({"archived": "false"}, {"target_per_week": True}):
        response = client.patch(f"/habits/{created['id']}", json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
    assert client.get(f"/habits/{created['id']}").json() == created


def test_required_response_fields(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


def test_openapi_required_fields() -> None:
    from habits.api.app import app

    schemas = app.openapi()["components"]["schemas"]
    assert "status" in schemas["Health"]["required"]
    assert "details" in schemas["ErrorBody"]["required"]


def test_module_app_importable() -> None:
    from habits.api.app import app

    assert isinstance(app, FastAPI)
    assert "/health" in app.openapi()["paths"]
