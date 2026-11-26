from __future__ import annotations

from datetime import date, datetime

from habits.core.errors import CheckInNotFound, HabitArchived, HabitNotFound, InvalidRange
from habits.core.models import CheckIn, Habit, HabitDraft, HabitPatch, HabitStats
from habits.core.ports import HabitRepository
from habits.core.rules import apply_patch, validate_checkin_day, validate_draft
from habits.core.streaks import compute_stats


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


def check_in(repo: HabitRepository, habit_id: int, day: date, today: date, now: datetime) -> CheckIn:
    habit = get_habit(repo, habit_id)
    if habit.archived:
        raise HabitArchived(f"habit {habit_id} is archived")
    validate_checkin_day(day, today)
    return repo.add_checkin(habit_id, day, now)


def undo_check_in(repo: HabitRepository, habit_id: int, day: date) -> None:
    get_habit(repo, habit_id)
    if not repo.delete_checkin(habit_id, day):
        raise CheckInNotFound(f"no check-in for habit {habit_id} on {day}")


def list_check_ins(
    repo: HabitRepository, habit_id: int, start: date | None, end: date | None
) -> list[CheckIn]:
    get_habit(repo, habit_id)
    if start is not None and end is not None and start > end:
        raise InvalidRange(f"start {start} is after end {end}")
    return repo.list_checkins(habit_id, start, end)


def get_stats(repo: HabitRepository, habit_id: int, today: date) -> HabitStats:
    habit = get_habit(repo, habit_id)
    days = [c.day for c in repo.list_checkins(habit_id, None, None)]
    return compute_stats(habit, days, today)
