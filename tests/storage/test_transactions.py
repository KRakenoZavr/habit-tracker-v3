from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from habits.core import CheckInExists, HabitDraft, HabitNotFound
from habits.storage.db import make_engine, make_session_factory
from habits.storage.repository import SqlHabitRepository

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
DAY = date(2026, 1, 1)


@pytest.fixture
def engine(migrated_db_url: str) -> Iterator[Engine]:
    eng = make_engine(migrated_db_url)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def factory(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


def _create_habit(factory: sessionmaker[Session]) -> int:
    with factory() as session:
        habit = SqlHabitRepository(session).add_habit(HabitDraft(name="run"), NOW)
        session.commit()
        return habit.id


def test_checkin_rolled_back_with_caller(factory: sessionmaker[Session]) -> None:
    habit_id = _create_habit(factory)

    with factory() as session_b:
        SqlHabitRepository(session_b).add_checkin(habit_id, DAY, NOW)
        session_b.rollback()

    with factory() as session_c:
        assert SqlHabitRepository(session_c).list_checkins(habit_id, None, None) == []


def test_engine_still_enforces_fk_and_commits(engine: Engine, factory: sessionmaker[Session]) -> None:
    with engine.connect() as conn:
        assert conn.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == 1

    habit_id = _create_habit(factory)
    with factory() as session_b:
        SqlHabitRepository(session_b).add_checkin(habit_id, DAY, NOW)
        session_b.commit()

    with factory() as session_c:
        checkins = SqlHabitRepository(session_c).list_checkins(habit_id, None, None)
    assert [c.day for c in checkins] == [DAY]


def test_checkin_for_deleted_habit_is_not_found(factory: sessionmaker[Session]) -> None:
    habit_id = _create_habit(factory)

    with factory() as session_a:
        assert SqlHabitRepository(session_a).delete_habit(habit_id) is True
        session_a.commit()

    with factory() as session_b, pytest.raises(HabitNotFound):
        SqlHabitRepository(session_b).add_checkin(habit_id, DAY, NOW)


def test_open_transaction_blocks_second_writer(migrated_db_url: str) -> None:
    separator = "&" if "?" in migrated_db_url else "?"
    eng = make_engine(f"{migrated_db_url}{separator}timeout=0.2")
    try:
        factory = make_session_factory(eng)
        with factory() as session_a, factory() as session_b:
            session_a.execute(sa.text("SELECT 1"))
            with pytest.raises(OperationalError, match="database is locked"):
                session_b.execute(sa.text("SELECT 1"))
            session_a.rollback()
    finally:
        eng.dispose()


def test_duplicate_still_conflicts(factory: sessionmaker[Session]) -> None:
    habit_id = _create_habit(factory)

    with factory() as session_b:
        repo = SqlHabitRepository(session_b)
        repo.add_checkin(habit_id, DAY, NOW)
        session_b.commit()
        with pytest.raises(CheckInExists):
            repo.add_checkin(habit_id, DAY, NOW)
