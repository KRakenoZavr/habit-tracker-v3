import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from habits.api.errors import STATUS_BY_CODE, install_error_handlers
from habits.core import (
    CheckInExists,
    CheckInNotFound,
    DomainError,
    FutureCheckIn,
    HabitArchived,
    HabitNotFound,
    InvalidHabit,
    InvalidRange,
)


class Body(BaseModel):
    name: str
    count: int


def _make_error(code: str, message: str) -> DomainError:
    cls: type[DomainError] = type("_TestError", (DomainError,), {"code": code})
    return cls(message)


REAL_ERRORS: dict[str, type[DomainError]] = {
    "habit_not_found": HabitNotFound,
    "checkin_not_found": CheckInNotFound,
    "checkin_exists": CheckInExists,
    "habit_archived": HabitArchived,
    "invalid_habit": InvalidHabit,
    "invalid_range": InvalidRange,
    "future_checkin": FutureCheckIn,
}


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/raise/{code}")
    def raise_error(code: str) -> None:
        if code in REAL_ERRORS:
            raise REAL_ERRORS[code](f"msg for {code}")
        raise _make_error(code, f"msg for {code}")

    @app.post("/body")
    def body(payload: Body) -> dict[str, str]:
        return {"name": payload.name}

    return app


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("habit_not_found", 404),
        ("checkin_not_found", 404),
        ("checkin_exists", 409),
        ("habit_archived", 409),
        ("invalid_habit", 422),
        ("invalid_range", 422),
        ("future_checkin", 422),
    ],
)
def test_domain_error_mapping(code: str, status: int) -> None:
    assert len(STATUS_BY_CODE) == 7
    assert REAL_ERRORS[code].code == code
    client = TestClient(_app())
    resp = client.get(f"/raise/{code}")
    assert resp.status_code == status
    assert resp.json() == {"error": {"code": code, "message": f"msg for {code}", "details": None}}


def test_unknown_code_is_400() -> None:
    resp = TestClient(_app()).get("/raise/weird_code")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "weird_code"


def test_validation_error_envelope() -> None:
    client = TestClient(_app())
    resp = client.post("/body", json={"name": 1})
    assert resp.status_code == 422
    assert resp.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed",
            "details": [
                {"loc": ["body", "name"], "msg": "Input should be a valid string"},
                {"loc": ["body", "count"], "msg": "Field required"},
            ],
        }
    }
