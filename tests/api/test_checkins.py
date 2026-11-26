import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text


def _create(client: TestClient, **body: object) -> dict:
    response = client.post("/habits", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _code(response: Any) -> str:
    return response.json()["error"]["code"]


def test_checkin_defaults_to_today(client: TestClient) -> None:
    habit = _create(client, name="Read")
    base = f"/habits/{habit['id']}/checkins"

    no_body = client.post(base)
    assert no_body.status_code == 201, no_body.text
    assert no_body.json()["habit_id"] == habit["id"]
    assert no_body.json()["day"] == "2026-01-15"
    assert no_body.json()["created_at"]

    other = _create(client, name="Run")
    empty = client.post(f"/habits/{other['id']}/checkins", json={})
    assert empty.status_code == 201, empty.text
    assert empty.json()["day"] == "2026-01-15"

    explicit = client.post(base, json={"day": "2026-01-10"})
    assert explicit.status_code == 201, explicit.text
    assert explicit.json()["day"] == "2026-01-10"


def test_checkin_errors(client: TestClient) -> None:
    habit = _create(client, name="Read")
    base = f"/habits/{habit['id']}/checkins"

    future = client.post(base, json={"day": "2026-01-16"})
    assert future.status_code == 422
    assert _code(future) == "future_checkin"

    assert client.post(base, json={"day": "2026-01-14"}).status_code == 201
    duplicate = client.post(base, json={"day": "2026-01-14"})
    assert duplicate.status_code == 409
    assert _code(duplicate) == "checkin_exists"

    bad_day = client.post(base, json={"day": "nope"})
    assert bad_day.status_code == 422
    assert _code(bad_day) == "validation_error"

    client.patch(f"/habits/{habit['id']}", json={"archived": True})
    archived = client.post(base)
    assert archived.status_code == 409
    assert _code(archived) == "habit_archived"

    missing = client.post("/habits/999/checkins")
    assert missing.status_code == 404
    assert _code(missing) == "habit_not_found"


def test_list_checkins(client: TestClient) -> None:
    habit = _create(client, name="Read")
    base = f"/habits/{habit['id']}/checkins"
    for day in ("2026-01-13", "2026-01-11", "2026-01-12", "2026-01-15"):
        assert client.post(base, json={"day": day}).status_code == 201

    everything = client.get(base)
    assert everything.status_code == 200
    assert [c["day"] for c in everything.json()] == ["2026-01-11", "2026-01-12", "2026-01-13", "2026-01-15"]

    ranged = client.get(base, params={"start": "2026-01-12", "end": "2026-01-13"})
    assert ranged.status_code == 200
    assert [c["day"] for c in ranged.json()] == ["2026-01-12", "2026-01-13"]

    only_start = client.get(base, params={"start": "2026-01-13"})
    assert [c["day"] for c in only_start.json()] == ["2026-01-13", "2026-01-15"]

    only_end = client.get(base, params={"end": "2026-01-11"})
    assert [c["day"] for c in only_end.json()] == ["2026-01-11"]

    inverted = client.get(base, params={"start": "2026-01-14", "end": "2026-01-12"})
    assert inverted.status_code == 422
    assert _code(inverted) == "invalid_range"

    bad = client.get(base, params={"start": "nope"})
    assert bad.status_code == 422
    assert _code(bad) == "validation_error"

    missing = client.get("/habits/999/checkins")
    assert missing.status_code == 404
    assert _code(missing) == "habit_not_found"


def test_delete_checkin(client: TestClient) -> None:
    habit = _create(client, name="Read")
    base = f"/habits/{habit['id']}/checkins"
    assert client.post(base, json={"day": "2026-01-14"}).status_code == 201

    deleted = client.delete(f"{base}/2026-01-14")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(base).json() == []

    again = client.delete(f"{base}/2026-01-14")
    assert again.status_code == 404
    assert _code(again) == "checkin_not_found"

    bad_day = client.delete(f"{base}/nope")
    assert bad_day.status_code == 422
    assert _code(bad_day) == "validation_error"

    missing = client.delete("/habits/999/checkins/2026-01-14")
    assert missing.status_code == 404
    assert _code(missing) == "habit_not_found"


def test_delete_habit_cascades_over_http(client: TestClient) -> None:
    habit = _create(client, name="Read")
    assert client.post(f"/habits/{habit['id']}/checkins").status_code == 201
    assert client.delete(f"/habits/{habit['id']}").status_code == 204
    assert client.get(f"/habits/{habit['id']}/checkins").status_code == 404

    with client.app.state.engine.connect() as conn:  # type: ignore[attr-defined]
        remaining = conn.execute(
            text("SELECT COUNT(*) FROM checkins WHERE habit_id = :id"), {"id": habit["id"]}
        ).scalar_one()
    assert remaining == 0

    recreated = _create(client, name="Read")
    listed = client.get(f"/habits/{recreated['id']}/checkins")
    assert listed.status_code == 200
    assert listed.json() == []


def test_duplicate_checkin_conflict(client: TestClient) -> None:
    habit = _create(client, name="Read")
    base = f"/habits/{habit['id']}/checkins"

    barrier = threading.Barrier(2)

    def post_same_day() -> Any:
        barrier.wait(timeout=10)
        return client.post(base, json={"day": "2026-01-14"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(post_same_day) for _ in range(2)]
        responses = [f.result(timeout=30) for f in futures]

    assert sorted(r.status_code for r in responses) == [201, 409]
    loser = next(r for r in responses if r.status_code == 409)
    assert _code(loser) == "checkin_exists"
    assert len(client.get(base).json()) == 1
