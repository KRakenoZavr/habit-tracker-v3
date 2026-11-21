"""Pydantic models of the HTTP contract (names match openapi components)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from habits import core


class Health(BaseModel):
    status: Literal["ok"] = "ok"


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    frequency: core.Frequency = core.Frequency.DAILY
    target_per_week: int | None = Field(default=None, ge=1, le=7)

    def to_draft(self) -> core.HabitDraft:
        return core.HabitDraft(
            name=self.name,
            description=self.description,
            frequency=self.frequency,
            target_per_week=self.target_per_week,
        )


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    frequency: core.Frequency | None = None
    target_per_week: int | None = Field(default=None, ge=1, le=7)
    archived: bool | None = None

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


class ErrorDetail(BaseModel):
    loc: list[str | int]
    msg: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None = None


class Error(BaseModel):
    error: ErrorBody
