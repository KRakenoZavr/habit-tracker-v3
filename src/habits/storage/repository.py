from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from habits.core import Frequency, Habit, HabitDraft, HabitRepository
from habits.storage.models import HabitRow


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
        row = self._session.get(HabitRow, habit_id)
        return None if row is None else _to_habit(row)

    def list_habits(self, include_archived: bool) -> list[Habit]:
        stmt = sa.select(HabitRow).order_by(HabitRow.id)
        if not include_archived:
            stmt = stmt.where(HabitRow.archived.is_(False))
        return [_to_habit(row) for row in self._session.scalars(stmt)]

    def update_habit(self, habit: Habit) -> Habit:
        row = self._session.get(HabitRow, habit.id)
        if row is None:
            raise LookupError(f"habit {habit.id} does not exist")
        row.name = habit.name
        row.description = habit.description
        row.frequency = habit.frequency.value
        row.target_per_week = habit.target_per_week
        row.archived = habit.archived
        self._session.flush()
        return _to_habit(row)

    def delete_habit(self, habit_id: int) -> bool:
        row = self._session.get(HabitRow, habit_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True
