from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

NAME_MAX = 100
DESCRIPTION_MAX = 500


class Frequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass(frozen=True, slots=True)
class HabitDraft:
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
    target_per_week: int | None
    archived: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class HabitPatch:
    name: str | None = None
    description: str | None = None
    frequency: Frequency | None = None
    target_per_week: int | None = None
    archived: bool | None = None
