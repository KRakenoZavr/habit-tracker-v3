from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from habits.core import CheckInExists, HabitDraft
from habits.storage import CheckInRow, HabitRow, SqlHabitRepository, make_engine, make_session_factory

CREATED = datetime(2024, 3, 5, 12, 30, 15, tzinfo=UTC)


@pytest.fixture
def session(migrated_db_url: str) -> Iterator[Session]:
    engine = make_engine(migrated_db_url)
    factory = make_session_factory(engine)
    with factory() as s:
        yield s
    engine.dispose()


def test_add_and_list_checkins(session: Session) -> None:
    repo = SqlHabitRepository(session)
    habit = repo.add_habit(HabitDraft(name="Read"), CREATED)
    other = repo.add_habit(HabitDraft(name="Run"), CREATED)
    days = [date(2024, 3, 7), date(2024, 3, 5), date(2024, 3, 6), date(2024, 3, 9)]
    for d in days:
        added = repo.add_checkin(habit.id, d, CREATED)
        assert added.habit_id == habit.id
        assert added.day == d
        assert added.created_at == CREATED
    repo.add_checkin(other.id, date(2024, 3, 6), CREATED)

    everything = repo.list_checkins(habit.id, None, None)
    assert [c.day for c in everything] == sorted(days)
    assert all(c.habit_id == habit.id for c in everything)
    assert everything[0].created_at == CREATED
    assert everything[0].created_at.tzinfo is not None
    assert everything[0].created_at.utcoffset() == timedelta(0)

    ranged = repo.list_checkins(habit.id, date(2024, 3, 6), date(2024, 3, 7))
    assert [c.day for c in ranged] == [date(2024, 3, 6), date(2024, 3, 7)]
    assert [c.day for c in repo.list_checkins(habit.id, date(2024, 3, 7), None)] == [
        date(2024, 3, 7),
        date(2024, 3, 9),
    ]
    assert [c.day for c in repo.list_checkins(habit.id, None, date(2024, 3, 5))] == [date(2024, 3, 5)]
    assert repo.list_checkins(2**63, None, None) == []


def test_duplicate_checkin(session: Session) -> None:
    repo = SqlHabitRepository(session)
    habit = repo.add_habit(HabitDraft(name="Read"), CREATED)
    repo.add_checkin(habit.id, date(2024, 3, 5), CREATED)
    with pytest.raises(CheckInExists):
        repo.add_checkin(habit.id, date(2024, 3, 5), CREATED)
    # session still usable
    repo.add_checkin(habit.id, date(2024, 3, 6), CREATED)
    assert len(repo.list_checkins(habit.id, None, None)) == 2


def test_unique_constraint(session: Session) -> None:
    repo = SqlHabitRepository(session)
    habit = repo.add_habit(HabitDraft(name="Read"), CREATED)
    naive = CREATED.replace(tzinfo=None)
    session.add(CheckInRow(habit_id=habit.id, day=date(2024, 3, 5), created_at=naive))
    session.flush()
    session.add(CheckInRow(habit_id=habit.id, day=date(2024, 3, 5), created_at=naive))
    with pytest.raises(IntegrityError):
        session.flush()


def test_delete_checkin(session: Session) -> None:
    repo = SqlHabitRepository(session)
    habit = repo.add_habit(HabitDraft(name="Read"), CREATED)
    repo.add_checkin(habit.id, date(2024, 3, 5), CREATED)
    assert repo.delete_checkin(habit.id, date(2024, 3, 5)) is True
    assert repo.delete_checkin(habit.id, date(2024, 3, 5)) is False
    assert repo.delete_checkin(2**63, date(2024, 3, 5)) is False
    assert repo.list_checkins(habit.id, None, None) == []


def test_delete_habit_cascades(session: Session) -> None:
    repo = SqlHabitRepository(session)
    habit = repo.add_habit(HabitDraft(name="Read"), CREATED)
    repo.add_checkin(habit.id, date(2024, 3, 5), CREATED)
    repo.add_checkin(habit.id, date(2024, 3, 6), CREATED)
    assert repo.delete_habit(habit.id) is True
    count = session.scalar(sa.select(sa.func.count()).select_from(CheckInRow))
    assert count == 0
    assert session.scalar(sa.select(sa.func.count()).select_from(HabitRow)) == 0
