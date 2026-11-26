from fastapi.testclient import TestClient


def _create(client: TestClient, **body: object) -> dict:
    response = client.post("/habits", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_stats_daily(client: TestClient) -> None:
    habit = _create(client, name="Read")
    for day in ("2026-01-13", "2026-01-14"):
        assert client.post(f"/habits/{habit['id']}/checkins", json={"day": day}).status_code == 201

    response = client.get(f"/habits/{habit['id']}/stats")
    assert response.status_code == 200
    assert response.json() == {
        "habit_id": habit["id"],
        "streak_unit": "day",
        "current_streak": 2,
        "longest_streak": 2,
        "total_checkins": 2,
        "period_count": 0,
        "period_target": 1,
        "period_done": False,
        "as_of": "2026-01-15",
    }


def test_stats_weekly(client: TestClient) -> None:
    habit = _create(client, name="Run", frequency="weekly", target_per_week=2)
    assert client.post(f"/habits/{habit['id']}/checkins", json={"day": "2026-01-14"}).status_code == 201

    response = client.get(f"/habits/{habit['id']}/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["streak_unit"] == "week"
    assert body["period_target"] == 2
    assert body["total_checkins"] == 1
    assert body["period_done"] is False


def test_stats_missing_habit(client: TestClient) -> None:
    response = client.get("/habits/999/stats")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "habit_not_found"


def test_stats_bad_id(client: TestClient) -> None:
    response = client.get("/habits/abc/stats")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
