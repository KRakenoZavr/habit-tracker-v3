import json
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from habits import core
from habits.api.schemas import CheckIn, CheckInCreate, Stats

NOW = datetime(2026, 1, 15, 8, 30, tzinfo=UTC)


def test_checkin_from_core() -> None:
    c = CheckIn.from_core(core.CheckIn(habit_id=3, day=date(2026, 1, 15), created_at=NOW))
    assert (c.habit_id, c.day, c.created_at) == (3, date(2026, 1, 15), NOW)
    data = json.loads(c.model_dump_json())
    assert data["day"] == "2026-01-15"
    assert data["created_at"].endswith("Z") or "+" in data["created_at"]


def test_stats_from_core() -> None:
    s = core.HabitStats(
        habit_id=1,
        streak_unit="week",
        current_streak=2,
        longest_streak=5,
        total_checkins=11,
        period_count=3,
        period_target=4,
        period_done=False,
        as_of=date(2026, 1, 15),
    )
    out = Stats.from_core(s)
    assert out.model_dump() == {
        "habit_id": 1,
        "streak_unit": "week",
        "current_streak": 2,
        "longest_streak": 5,
        "total_checkins": 11,
        "period_count": 3,
        "period_target": 4,
        "period_done": False,
        "as_of": date(2026, 1, 15),
    }


def test_checkin_create() -> None:
    assert CheckInCreate.model_validate({}).day is None
    assert CheckInCreate.model_validate({"day": None}).day is None
    assert CheckInCreate.model_validate_json('{"day": "2026-01-15"}').day == date(2026, 1, 15)
    with pytest.raises(ValidationError):
        CheckInCreate.model_validate({"day": "nope"})
    with pytest.raises(ValidationError):
        CheckInCreate.model_validate({"day": 20260115})
    with pytest.raises(ValidationError):
        CheckInCreate.model_validate_json('{"day": 20260115}')
    with pytest.raises(ValidationError):
        CheckInCreate.model_validate({"day": "1768435200"})
    with pytest.raises(ValidationError):
        CheckInCreate.model_validate_json('{"day": "1768435200"}')
    assert CheckInCreate.model_validate({"day": date(2026, 1, 15)}).day == date(2026, 1, 15)


CHECKIN_DATA = {"habit_id": 1, "day": "2026-01-15", "created_at": "2026-01-15T08:30:00Z"}
STATS_DATA = {
    "habit_id": 1,
    "streak_unit": "day",
    "current_streak": 0,
    "longest_streak": 0,
    "total_checkins": 0,
    "period_count": 0,
    "period_target": 1,
    "period_done": False,
    "as_of": "2026-01-15",
}


@pytest.mark.parametrize("model, data", [(CheckIn, CHECKIN_DATA), (Stats, STATS_DATA)])
def test_response_fields_required(model: type[CheckIn] | type[Stats], data: dict) -> None:
    model.model_validate(data)
    for field in data:
        partial = {k: v for k, v in data.items() if k != field}
        with pytest.raises(ValidationError) as exc:
            model.model_validate(partial)
        assert [(e["type"], e["loc"]) for e in exc.value.errors()] == [("missing", (field,))]
