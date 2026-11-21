from datetime import date, datetime

import pytest

from habits.core import (
    CheckInExists,
    CheckInNotFound,
    FutureCheckIn,
    HabitArchived,
    HabitDraft,
    HabitNotFound,
    HabitPatch,
    InvalidRange,
    check_in,
    compute_stats,
    create_habit,
    get_stats,
    list_check_ins,
    undo_check_in,
    update_habit,
)
from tests.core.fakes import FakeHabitRepository

NOW = datetime(2026, 3, 10, 12, 0, 0)
TODAY = date(2026, 3, 10)


def _repo_with_habit() -> tuple[FakeHabitRepository, int]:
    repo = FakeHabitRepository()
    habit = create_habit(repo, HabitDraft(name="Run"), NOW)
    return repo, habit.id


def test_check_in_ok() -> None:
    repo, hid = _repo_with_habit()
    created = datetime(2026, 3, 10, 18, 30, 0)
    result = check_in(repo, hid, TODAY, TODAY, created)
    assert result.habit_id == hid
    assert result.day == TODAY
    assert result.created_at == created
    assert repo.list_checkins(hid, None, None) == [result]


def test_check_in_errors() -> None:
    repo, hid = _repo_with_habit()
    with pytest.raises(HabitNotFound):
        check_in(repo, 999, TODAY, TODAY, NOW)
    with pytest.raises(FutureCheckIn):
        check_in(repo, hid, date(2026, 3, 11), TODAY, NOW)
    check_in(repo, hid, TODAY, TODAY, NOW)
    with pytest.raises(CheckInExists):
        check_in(repo, hid, TODAY, TODAY, NOW)

    update_habit(repo, hid, HabitPatch(archived=True))
    with pytest.raises(HabitArchived):
        check_in(repo, hid, date(2026, 3, 9), TODAY, NOW)
    # archived is reported before the future-day check
    with pytest.raises(HabitArchived):
        check_in(repo, hid, date(2026, 3, 11), TODAY, NOW)


def test_undo_and_list() -> None:
    repo, hid = _repo_with_habit()
    for d in (date(2026, 3, 8), date(2026, 3, 5), date(2026, 3, 9)):
        check_in(repo, hid, d, TODAY, NOW)

    assert [c.day for c in list_check_ins(repo, hid, None, None)] == [
        date(2026, 3, 5),
        date(2026, 3, 8),
        date(2026, 3, 9),
    ]
    assert [c.day for c in list_check_ins(repo, hid, date(2026, 3, 8), date(2026, 3, 9))] == [
        date(2026, 3, 8),
        date(2026, 3, 9),
    ]
    assert [c.day for c in list_check_ins(repo, hid, date(2026, 3, 9), None)] == [date(2026, 3, 9)]
    with pytest.raises(InvalidRange):
        list_check_ins(repo, hid, date(2026, 3, 9), date(2026, 3, 8))
    assert len(list_check_ins(repo, hid, date(2026, 3, 9), date(2026, 3, 9))) == 1
    with pytest.raises(HabitNotFound):
        list_check_ins(repo, 999, None, None)

    undo_check_in(repo, hid, date(2026, 3, 8))
    assert [c.day for c in list_check_ins(repo, hid, None, None)] == [
        date(2026, 3, 5),
        date(2026, 3, 9),
    ]
    with pytest.raises(CheckInNotFound):
        undo_check_in(repo, hid, date(2026, 3, 8))
    with pytest.raises(HabitNotFound):
        undo_check_in(repo, 999, date(2026, 3, 8))


def test_get_stats() -> None:
    repo, hid = _repo_with_habit()
    days = [date(2026, 3, 8), date(2026, 3, 9), date(2026, 3, 10)]
    for d in days:
        check_in(repo, hid, d, TODAY, NOW)
    habit = repo.get_habit(hid)
    assert habit is not None
    assert get_stats(repo, hid, TODAY) == compute_stats(habit, days, TODAY)
    with pytest.raises(HabitNotFound):
        get_stats(repo, 999, TODAY)
