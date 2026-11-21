from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from habits import core
from habits.api.schemas import Habit, HabitCreate, HabitUpdate
from habits.api.settings import Settings


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HABITS_DATABASE_URL", raising=False)
    monkeypatch.delenv("HABITS_TIMEZONE", raising=False)
    assert Settings.from_env() == Settings()

    monkeypatch.setenv("HABITS_DATABASE_URL", "sqlite:///x.db")
    monkeypatch.setenv("HABITS_TIMEZONE", "Europe/Berlin")
    s = Settings.from_env()
    assert s.database_url == "sqlite:///x.db"
    assert s.timezone == "Europe/Berlin"

    monkeypatch.setenv("HABITS_TIMEZONE", "Not/AZone")
    with pytest.raises(ValueError, match="Not/AZone"):
        Settings.from_env()


def test_habit_create_to_draft() -> None:
    assert HabitCreate(name="Run").to_draft() == core.HabitDraft(name="Run")
    draft = HabitCreate(
        name="Read", description="d", frequency=core.Frequency.WEEKLY, target_per_week=3
    ).to_draft()
    assert draft == core.HabitDraft(
        name="Read", description="d", frequency=core.Frequency.WEEKLY, target_per_week=3
    )


def test_habit_update_to_patch() -> None:
    assert HabitUpdate().to_patch() == core.HabitPatch()
    assert HabitUpdate(description=None).to_patch().description == ""
    assert HabitUpdate(description="").to_patch().description == ""
    assert HabitUpdate(description="x").to_patch().description == "x"
    patch = HabitUpdate(name="n", archived=True).to_patch()
    assert patch == core.HabitPatch(name="n", archived=True)
    assert HabitUpdate(archived=False).to_patch().archived is False


def test_habit_from_core() -> None:
    created = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    h = Habit.from_core(
        core.Habit(
            id=1,
            name="Run",
            description=None,
            frequency=core.Frequency.DAILY,
            target_per_week=None,
            archived=False,
            created_at=created,
        )
    )
    assert h.created_at.tzinfo is not None
    assert h.created_at == created
    dumped = h.model_dump_json()
    assert "2024-01-02T03:04:05Z" in dumped or "+00:00" in dumped


def test_field_limits() -> None:
    for bad in (0, 8):
        with pytest.raises(ValidationError):
            HabitCreate(name="x", target_per_week=bad)
    with pytest.raises(ValidationError):
        HabitCreate(name="")
