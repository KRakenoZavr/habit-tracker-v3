# covers: [src/habits/core/**]
# verified_at: none
# owner: architect
#
# Public API of habits.core — pure domain logic. Imports allowed: stdlib only (dataclasses, datetime, enum, typing,
# collections.abc). NEVER sqlalchemy, fastapi, pydantic, habits.storage, habits.api. Never read the clock: `now` and
# `today` are parameters. Items marked (M2) are added in milestone M2, not before.
# Re-exported from habits/core/__init__.py: every public name below.

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import ClassVar, Literal, Protocol

# ---------------------------------------------------------------- habits/core/models.py
class Frequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"

NAME_MAX = 100
DESCRIPTION_MAX = 500

@dataclass(frozen=True, slots=True)
class HabitDraft:          # input to create_habit; not yet validated
    name: str
    description: str | None = None
    frequency: Frequency = Frequency.DAILY
    target_per_week: int | None = None

@dataclass(frozen=True, slots=True)
class Habit:
    id: int
    name: str
    description: str | None
    frequency: Frequency
    target_per_week: int | None   # None for daily, 1..7 for weekly
    archived: bool
    created_at: datetime          # tz-aware UTC

@dataclass(frozen=True, slots=True)
class HabitPatch:          # every field None = "leave unchanged"
    name: str | None = None
    description: str | None = None   # "" clears the description (stored as None)
    frequency: Frequency | None = None
    target_per_week: int | None = None
    archived: bool | None = None

@dataclass(frozen=True, slots=True)
class CheckIn:             # (M2)
    habit_id: int
    day: date
    created_at: datetime   # tz-aware UTC

@dataclass(frozen=True, slots=True)
class HabitStats:          # (M2)
    habit_id: int
    streak_unit: Literal["day", "week"]
    current_streak: int
    longest_streak: int
    total_checkins: int
    period_count: int      # daily: 1 if today checked else 0; weekly: check-ins in this ISO week
    period_target: int     # daily: 1; weekly: target_per_week
    period_done: bool      # period_count >= period_target
    as_of: date            # the `today` used

# ---------------------------------------------------------------- habits/core/errors.py
class DomainError(Exception):
    code: ClassVar[str]
    def __init__(self, message: str) -> None: ...   # str(err) == message
class InvalidHabit(DomainError): code = "invalid_habit"         # -> 422
class InvalidRange(DomainError): code = "invalid_range"         # -> 422 (M2)
class FutureCheckIn(DomainError): code = "future_checkin"       # -> 422 (M2)
class HabitNotFound(DomainError): code = "habit_not_found"      # -> 404
class CheckInNotFound(DomainError): code = "checkin_not_found"  # -> 404 (M2)
class CheckInExists(DomainError): code = "checkin_exists"       # -> 409 (M2)
class HabitArchived(DomainError): code = "habit_archived"       # -> 409 (M2)

# ---------------------------------------------------------------- habits/core/rules.py
def validate_draft(draft: HabitDraft) -> HabitDraft:
    """Return a normalized copy or raise InvalidHabit.
    name: strip(); 1..NAME_MAX chars after strip. description: strip(); "" -> None; <= DESCRIPTION_MAX chars.
    daily: target_per_week must be None. weekly: target_per_week required, 1..7."""
def apply_patch(habit: Habit, patch: HabitPatch) -> Habit:
    """Return the updated habit or raise InvalidHabit. Same field rules as validate_draft.
    If the resulting frequency is daily, target_per_week becomes None (a non-None patch.target_per_week with a
    resulting daily frequency -> InvalidHabit). Switching to weekly without any target -> InvalidHabit.
    id and created_at never change."""
def validate_checkin_day(day: date, today: date) -> None:   # (M2) day > today -> FutureCheckIn
    ...

# ---------------------------------------------------------------- habits/core/streaks.py  (M2)
def week_start(day: date) -> date: ...   # Monday of day's ISO week
def compute_stats(habit: Habit, days: Sequence[date], today: date) -> HabitStats:
    """days: check-in days of this habit (any order, no duplicates). Days > today are ignored.
    Rules (ADR-0005): daily current streak = consecutive days ending today, or ending yesterday if today is not
    checked; weekly: a week is met when count >= target_per_week; current = consecutive met weeks ending this week
    if met, else ending last week. longest = longest run anywhere (>= current). total_checkins counts days <= today."""

# ---------------------------------------------------------------- habits/core/ports.py
class HabitRepository(Protocol):
    def add_habit(self, draft: HabitDraft, created_at: datetime) -> Habit: ...   # draft already validated
    def get_habit(self, habit_id: int) -> Habit | None: ...
    def list_habits(self, include_archived: bool) -> list[Habit]: ...            # ordered by id asc
    def update_habit(self, habit: Habit) -> Habit: ...                           # habit exists
    def delete_habit(self, habit_id: int) -> bool: ...                           # False if missing; cascades check-ins
    # (M2)
    def add_checkin(self, habit_id: int, day: date, created_at: datetime) -> CheckIn: ...  # duplicate -> CheckInExists
    def delete_checkin(self, habit_id: int, day: date) -> bool: ...              # False if missing
    def list_checkins(self, habit_id: int, start: date | None, end: date | None) -> list[CheckIn]: ...  # inclusive, day asc

# ---------------------------------------------------------------- habits/core/services.py
# Use cases. Each takes the repository first. They raise DomainError subclasses, never return None for failure.
def create_habit(repo: HabitRepository, draft: HabitDraft, now: datetime) -> Habit: ...        # InvalidHabit
def get_habit(repo: HabitRepository, habit_id: int) -> Habit: ...                               # HabitNotFound
def list_habits(repo: HabitRepository, include_archived: bool = False) -> list[Habit]: ...
def update_habit(repo: HabitRepository, habit_id: int, patch: HabitPatch) -> Habit: ...        # HabitNotFound, InvalidHabit
def delete_habit(repo: HabitRepository, habit_id: int) -> None: ...                            # HabitNotFound
# (M2)
def check_in(repo: HabitRepository, habit_id: int, day: date, today: date, now: datetime) -> CheckIn:
    """Order of checks: HabitNotFound, HabitArchived, FutureCheckIn, then repo.add_checkin (CheckInExists)."""
def undo_check_in(repo: HabitRepository, habit_id: int, day: date) -> None: ...                # HabitNotFound, CheckInNotFound
def list_check_ins(repo: HabitRepository, habit_id: int, start: date | None, end: date | None) -> list[CheckIn]:
    """HabitNotFound; start and end both set and start > end -> InvalidRange."""
def get_stats(repo: HabitRepository, habit_id: int, today: date) -> HabitStats: ...            # HabitNotFound
