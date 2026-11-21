from __future__ import annotations

from datetime import datetime

from habits.core.errors import HabitNotFound
from habits.core.models import Habit, HabitDraft, HabitPatch
from habits.core.ports import HabitRepository
from habits.core.rules import apply_patch, validate_draft


def create_habit(repo: HabitRepository, draft: HabitDraft, now: datetime) -> Habit:
    return repo.add_habit(validate_draft(draft), now)


def get_habit(repo: HabitRepository, habit_id: int) -> Habit:
    habit = repo.get_habit(habit_id)
    if habit is None:
        raise HabitNotFound(f"habit {habit_id} not found")
    return habit


def list_habits(repo: HabitRepository, include_archived: bool = False) -> list[Habit]:
    return repo.list_habits(include_archived)


def update_habit(repo: HabitRepository, habit_id: int, patch: HabitPatch) -> Habit:
    habit = get_habit(repo, habit_id)
    return repo.update_habit(apply_patch(habit, patch))


def delete_habit(repo: HabitRepository, habit_id: int) -> None:
    if not repo.delete_habit(habit_id):
        raise HabitNotFound(f"habit {habit_id} not found")
