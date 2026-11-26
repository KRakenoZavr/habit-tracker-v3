from datetime import UTC, date, datetime
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from habits.core import CheckIn, CheckInExists, Frequency, Habit, HabitDraft, HabitNotFound, HabitRepository
from habits.storage.models import CheckInRow, HabitRow

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


def _to_checkin(row: CheckInRow) -> CheckIn:
    return CheckIn(
        habit_id=row.habit_id,
        day=row.day,
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

    def add_checkin(self, habit_id: int, day: date, created_at: datetime) -> CheckIn:
        message = f"habit {habit_id} already checked in on {day}"
        existing = self._session.scalar(
            sa.select(CheckInRow.id).where(CheckInRow.habit_id == habit_id, CheckInRow.day == day)
        )
        if existing is not None:
            raise CheckInExists(message)
        row = CheckInRow(
            habit_id=habit_id,
            day=day,
            created_at=created_at.astimezone(UTC).replace(tzinfo=None),
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            if self.get_habit(habit_id) is None:
                raise HabitNotFound(f"habit {habit_id} not found") from exc
            raise CheckInExists(message) from exc
        return _to_checkin(row)

    def delete_checkin(self, habit_id: int, day: date) -> bool:
        if not _in_range(habit_id):
            return False
        result = cast(
            "sa.CursorResult[Any]",
            self._session.execute(
                sa.delete(CheckInRow).where(CheckInRow.habit_id == habit_id, CheckInRow.day == day)
            ),
        )
        return result.rowcount == 1

    def list_checkins(self, habit_id: int, start: date | None, end: date | None) -> list[CheckIn]:
        if not _in_range(habit_id):
            return []
        stmt = sa.select(CheckInRow).where(CheckInRow.habit_id == habit_id).order_by(CheckInRow.day)
        if start is not None:
            stmt = stmt.where(CheckInRow.day >= start)
        if end is not None:
            stmt = stmt.where(CheckInRow.day <= end)
        return [_to_checkin(row) for row in self._session.scalars(stmt)]
