"""Request-scoped dependencies."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from habits.core import HabitRepository
from habits.storage.repository import SqlHabitRepository


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def get_repo(session: Session = Depends(get_session, scope="function")) -> HabitRepository:
    return SqlHabitRepository(session)


def get_now() -> datetime:
    return datetime.now(UTC)


def get_today(request: Request, now: datetime = Depends(get_now)) -> date:
    return now.astimezone(ZoneInfo(request.app.state.settings.timezone)).date()
