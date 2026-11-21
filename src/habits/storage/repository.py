from datetime import UTC, datetime
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.orm import Session

from habits.core import Frequency, Habit, HabitDraft, HabitNotFound, HabitRepository
from habits.storage.models import HabitRow

INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1


def _in_range(habit_id: int) -> bool:
    return INT64_MIN <= habit_id <= INT64_MAX


def _to_habit(row: HabitRow) -> Habit:
    return Habit(
        id=row.id,
        name=row.name,
        description=row.description,
        frequency=Frequency(row.frequency),
        target_per_week=row.target_per_week,
        archived=row.archived,
        created_at=row.created_at.replace(tzinfo=UTC),
    )


class SqlHabitRepository(HabitRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_habit(self, draft: HabitDraft, created_at: datetime) -> Habit:
        row = HabitRow(
            name=draft.name,
            description=draft.description,
            frequency=draft.frequency.value,
            target_per_week=draft.target_per_week,
            archived=False,
            created_at=created_at.astimezone(UTC).replace(tzinfo=None),
        )
        self._session.add(row)
        self._session.flush()
        return _to_habit(row)

    def get_habit(self, habit_id: int) -> Habit | None:
        if not _in_range(habit_id):
            return None
        row = self._session.get(HabitRow, habit_id)
        return None if row is None else _to_habit(row)

    def list_habits(self, include_archived: bool) -> list[Habit]:
        stmt = sa.select(HabitRow).order_by(HabitRow.id)
        if not include_archived:
            stmt = stmt.where(HabitRow.archived.is_(False))
        return [_to_habit(row) for row in self._session.scalars(stmt)]

    def update_habit(self, habit: Habit) -> Habit:
        row = self._session.get(HabitRow, habit.id, populate_existing=True) if _in_range(habit.id) else None
        if row is None:
            raise HabitNotFound(f"habit {habit.id} not found")
        row.name = habit.name
        row.description = habit.description
        row.frequency = habit.frequency.value
        row.target_per_week = habit.target_per_week
        row.archived = habit.archived
        self._session.flush()
        return _to_habit(row)

    def delete_habit(self, habit_id: int) -> bool:
        if not _in_range(habit_id):
            return False
        result = cast(
            "sa.CursorResult[Any]",
            self._session.execute(sa.delete(HabitRow).where(HabitRow.id == habit_id)),
        )
        return result.rowcount == 1
