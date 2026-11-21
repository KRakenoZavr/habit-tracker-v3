from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from habits.core import Frequency, HabitDraft, HabitNotFound
from habits.storage import HabitRow, SqlHabitRepository, make_engine, make_session_factory

CREATED = datetime(2024, 3, 5, 12, 30, 15, tzinfo=UTC)


@pytest.fixture
def session(migrated_db_url: str) -> Iterator[Session]:
    engine = make_engine(migrated_db_url)
    factory = make_session_factory(engine)
    with factory() as s:
        yield s
    engine.dispose()


def test_add_get_roundtrip(session: Session) -> None:
    repo = SqlHabitRepository(session)
    draft = HabitDraft(name="Read", description="30 pages", frequency=Frequency.WEEKLY, target_per_week=3)
    added = repo.add_habit(draft, CREATED)
    assert added.id > 0
    assert added.archived is False
    got = repo.get_habit(added.id)
    assert got == added
    assert got is not None
    assert got.name == "Read"
    assert got.description == "30 pages"
    assert got.frequency is Frequency.WEEKLY
    assert got.target_per_week == 3
    assert got.created_at == CREATED
    assert got.created_at.tzinfo is not None
    assert got.created_at.utcoffset() == timedelta(0)


def test_created_at_normalized_to_utc(session: Session) -> None:
    repo = SqlHabitRepository(session)
    local = datetime(2024, 3, 5, 15, 30, 15, tzinfo=timezone(timedelta(hours=3)))
    added = repo.add_habit(HabitDraft(name="Run"), local)
    got = repo.get_habit(added.id)
    assert got is not None
    assert got.created_at == local
    assert got.created_at == CREATED
    assert got.created_at.utcoffset() == timedelta(0)


def test_list_habits(session: Session) -> None:
    repo = SqlHabitRepository(session)
    a = repo.add_habit(HabitDraft(name="A"), CREATED)
    b = repo.add_habit(HabitDraft(name="B"), CREATED)
    c = repo.add_habit(HabitDraft(name="C"), CREATED)
    repo.update_habit(replace(b, archived=True))
    assert [h.id for h in repo.list_habits(include_archived=True)] == [a.id, b.id, c.id]
    assert [h.id for h in repo.list_habits(include_archived=False)] == [a.id, c.id]


def test_update_delete(session: Session) -> None:
    repo = SqlHabitRepository(session)
    added = repo.add_habit(HabitDraft(name="Old", description="d"), CREATED)
    changed = replace(
        added,
        name="New",
        description=None,
        frequency=Frequency.WEEKLY,
        target_per_week=4,
        archived=True,
    )
    updated = repo.update_habit(replace(changed, created_at=CREATED + timedelta(days=5)))
    assert updated == changed
    assert updated.created_at == CREATED
    assert repo.get_habit(added.id) == changed
    assert repo.delete_habit(added.id) is True
    assert repo.delete_habit(added.id) is False
    assert repo.get_habit(added.id) is None
    assert repo.get_habit(9999) is None


def test_no_commit(session: Session) -> None:
    repo = SqlHabitRepository(session)
    repo.add_habit(HabitDraft(name="Temp"), CREATED)
    session.rollback()
    assert session.scalar(sa.select(sa.func.count()).select_from(HabitRow)) == 0


def test_update_delete_do_not_commit(session: Session) -> None:
    repo = SqlHabitRepository(session)
    added = repo.add_habit(HabitDraft(name="Base", description="d"), CREATED)
    session.commit()

    repo.update_habit(replace(added, name="Changed", description=None, archived=True))
    session.rollback()
    assert repo.get_habit(added.id) == added

    assert repo.delete_habit(added.id) is True
    session.rollback()
    assert repo.get_habit(added.id) == added


@pytest.fixture
def two_sessions(migrated_db_url: str) -> Iterator[tuple[Session, Session]]:
    engine = make_engine(migrated_db_url)
    factory = make_session_factory(engine)
    with factory() as a, factory() as b:
        yield a, b
    engine.dispose()


def test_racing_deletes(two_sessions: tuple[Session, Session]) -> None:
    a, b = two_sessions
    habit = SqlHabitRepository(a).add_habit(HabitDraft(name="Race"), CREATED)
    a.commit()
    repo_b = SqlHabitRepository(b)
    assert repo_b.get_habit(habit.id) is not None
    assert SqlHabitRepository(a).delete_habit(habit.id) is True
    a.commit()
    assert repo_b.delete_habit(habit.id) is False


def test_update_vanished_row(two_sessions: tuple[Session, Session]) -> None:
    a, b = two_sessions
    habit = SqlHabitRepository(a).add_habit(HabitDraft(name="Gone"), CREATED)
    a.commit()
    repo_b = SqlHabitRepository(b)
    assert repo_b.get_habit(habit.id) is not None
    assert SqlHabitRepository(a).delete_habit(habit.id) is True
    a.commit()
    with pytest.raises(HabitNotFound):
        repo_b.update_habit(replace(habit, name="Changed"))


def test_out_of_range_ids(session: Session) -> None:
    repo = SqlHabitRepository(session)
    habit = repo.add_habit(HabitDraft(name="Edge"), CREATED)
    for bad in (2**63, -(2**63) - 1):
        assert repo.get_habit(bad) is None
        assert repo.delete_habit(bad) is False
        with pytest.raises(HabitNotFound):
            repo.update_habit(replace(habit, id=bad))
    assert repo.get_habit(2**63 - 1) is None
