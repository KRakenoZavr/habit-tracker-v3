"""Pydantic models of the HTTP contract (names match openapi components)."""

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, StrictBool, StrictInt, StrictStr

from habits import core


class Health(BaseModel):
    status: Literal["ok"]


class HabitCreate(BaseModel):
    name: StrictStr = Field(min_length=1, max_length=100)
    description: StrictStr | None = Field(default=None, max_length=500)
    frequency: core.Frequency = core.Frequency.DAILY
    target_per_week: StrictInt | None = Field(default=None, ge=1, le=7)

    def to_draft(self) -> core.HabitDraft:
        return core.HabitDraft(
            name=self.name,
            description=self.description,
            frequency=self.frequency,
            target_per_week=self.target_per_week,
        )


class HabitUpdate(BaseModel):
    name: StrictStr | None = Field(default=None, min_length=1, max_length=100)
    description: StrictStr | None = Field(default=None, max_length=500)
    frequency: core.Frequency | None = None
    target_per_week: StrictInt | None = Field(default=None, ge=1, le=7)
    archived: StrictBool | None = None

    def to_patch(self) -> core.HabitPatch:
        description = self.description
        if "description" in self.model_fields_set and not description:
            description = ""
        return core.HabitPatch(
            name=self.name,
            description=description,
            frequency=self.frequency,
            target_per_week=self.target_per_week,
            archived=self.archived,
        )


class Habit(BaseModel):
    id: int
    name: str
    description: str | None
    frequency: core.Frequency
    target_per_week: int | None
    archived: bool
    created_at: datetime

    @classmethod
    def from_core(cls, h: core.Habit) -> "Habit":
        return cls(
            id=h.id,
            name=h.name,
            description=h.description,
            frequency=h.frequency,
            target_per_week=h.target_per_week,
            archived=h.archived,
            created_at=h.created_at,
        )


def _iso_date(value: object) -> object:
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raise ValueError("expected YYYY-MM-DD")


IsoDate = Annotated[date, BeforeValidator(_iso_date)]


class CheckInCreate(BaseModel):
    day: IsoDate | None = None


class CheckIn(BaseModel):
    habit_id: int
    day: date
    created_at: datetime

    @classmethod
    def from_core(cls, c: core.CheckIn) -> "CheckIn":
        return cls(habit_id=c.habit_id, day=c.day, created_at=c.created_at)


class Stats(BaseModel):
    habit_id: int
    streak_unit: Literal["day", "week"]
    current_streak: int = Field(ge=0)
    longest_streak: int = Field(ge=0)
    total_checkins: int = Field(ge=0)
    period_count: int = Field(ge=0)
    period_target: int = Field(ge=1)
    period_done: bool
    as_of: date

    @classmethod
    def from_core(cls, s: core.HabitStats) -> "Stats":
        return cls(
            habit_id=s.habit_id,
            streak_unit=s.streak_unit,
            current_streak=s.current_streak,
            longest_streak=s.longest_streak,
            total_checkins=s.total_checkins,
            period_count=s.period_count,
            period_target=s.period_target,
            period_done=s.period_done,
            as_of=s.as_of,
        )


class ErrorDetail(BaseModel):
    loc: list[str | int]
    msg: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None


class Error(BaseModel):
    error: ErrorBody
