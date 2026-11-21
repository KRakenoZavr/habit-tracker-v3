from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from habits.storage import Base, HabitRow, make_engine, make_session_factory


def test_foreign_keys_on() -> None:
    engine = make_engine("sqlite://")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_habit_row_roundtrip() -> None:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.add(HabitRow(name="Read", frequency="daily", created_at=datetime(2024, 1, 1)))
        session.commit()
        row = session.query(HabitRow).one()
        assert row.id == 1
        assert row.name == "Read"
        assert row.description is None
        assert row.target_per_week is None
        assert row.archived is False
        assert row.created_at == datetime(2024, 1, 1)


def test_frequency_check_constraint() -> None:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.add(HabitRow(name="Read", frequency="monthly", created_at=datetime(2024, 1, 1)))
        with pytest.raises(IntegrityError):
            session.commit()
