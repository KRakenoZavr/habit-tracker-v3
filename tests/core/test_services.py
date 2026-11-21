from datetime import UTC, datetime

import pytest

from habits.core import (
    HabitDraft,
    HabitNotFound,
    HabitPatch,
    HabitRepository,
    InvalidHabit,
    services,
)
from tests.core.fakes import FakeHabitRepository

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_create_habit() -> None:
    repo = FakeHabitRepository()
    habit = services.create_habit(repo, HabitDraft(name="  Read  "), NOW)
    assert habit.id == 1
    assert habit.name == "Read"
    assert habit.created_at == NOW
    assert repo.get_habit(1) == habit


def test_create_habit_invalid() -> None:
    repo = FakeHabitRepository()
    with pytest.raises(InvalidHabit):
        services.create_habit(repo, HabitDraft(name="   "), NOW)
    assert repo.list_habits(include_archived=True) == []


def test_missing_habit_raises() -> None:
    repo = FakeHabitRepository()
    with pytest.raises(HabitNotFound):
        services.get_habit(repo, 42)
    with pytest.raises(HabitNotFound):
        services.update_habit(repo, 42, HabitPatch(name="x"))
    with pytest.raises(HabitNotFound):
        services.delete_habit(repo, 42)


def test_list_habits() -> None:
    repo = FakeHabitRepository()
    a = services.create_habit(repo, HabitDraft(name="a"), NOW)
    b = services.create_habit(repo, HabitDraft(name="b"), NOW)
    c = services.create_habit(repo, HabitDraft(name="c"), NOW)
    services.update_habit(repo, b.id, HabitPatch(archived=True))
    assert services.list_habits(repo) == [a, c]
    assert [h.id for h in services.list_habits(repo, include_archived=True)] == [1, 2, 3]


def test_update_habit() -> None:
    repo = FakeHabitRepository()
    habit = services.create_habit(repo, HabitDraft(name="old"), NOW)
    updated = services.update_habit(repo, habit.id, HabitPatch(name="new"))
    assert updated.name == "new"
    assert services.get_habit(repo, habit.id).name == "new"


def test_update_habit_blank_name() -> None:
    repo = FakeHabitRepository()
    habit = services.create_habit(repo, HabitDraft(name="old"), NOW)
    with pytest.raises(InvalidHabit):
        services.update_habit(repo, habit.id, HabitPatch(name="   "))
    assert services.get_habit(repo, habit.id) == habit


def test_delete_habit() -> None:
    repo = FakeHabitRepository()
    habit = services.create_habit(repo, HabitDraft(name="x"), NOW)
    services.delete_habit(repo, habit.id)
    assert repo.get_habit(habit.id) is None


def test_fake_satisfies_port() -> None:
    repo: HabitRepository = FakeHabitRepository()
    assert repo.list_habits(include_archived=False) == []
