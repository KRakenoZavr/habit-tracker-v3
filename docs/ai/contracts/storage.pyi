# covers: [src/habits/storage/**, migrations/**, alembic.ini]
# verified_at: none
# owner: architect
#
# Public API of habits.storage — SQLAlchemy 2 (sync) adapter implementing habits.core.HabitRepository (ADR-0003).
# Imports allowed: sqlalchemy, habits.core, stdlib. NEVER fastapi, pydantic, habits.api.
# ORM rows never leave this package: every public method returns habits.core dataclasses.
# Items marked (M2) are added in milestone M2.

from datetime import date, datetime
from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, sessionmaker
from habits.core import CheckIn, Habit, HabitDraft, HabitRepository

# ---------------------------------------------------------------- habits/storage/db.py
def make_engine(url: str) -> Engine:
    """create_engine(url). For sqlite URLs: connect_args={"check_same_thread": False} and a "connect" event
    listener that runs PRAGMA foreign_keys=ON on every DBAPI connection, sets isolation_level=None, and a "begin"
    listener that emits BEGIN (SQLAlchemy pysqlite recipe: savepoints always nest in a real transaction)."""
def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """sessionmaker(bind=engine, expire_on_commit=False)."""

# ---------------------------------------------------------------- habits/storage/models.py
class Base(DeclarativeBase): ...      # Base.metadata is Alembic's target_metadata

class HabitRow(Base):
    __tablename__ = "habits"
    id: Mapped[int]                    # Integer, primary key, autoincrement
    name: Mapped[str]                  # String(100), not null
    description: Mapped[str | None]    # String(500), nullable
    frequency: Mapped[str]             # String(10), not null; CheckConstraint "frequency IN ('daily','weekly')" name="ck_habits_frequency"
    target_per_week: Mapped[int | None]  # Integer, nullable
    archived: Mapped[bool]             # Boolean, not null, server_default=sa.false()
    created_at: Mapped[datetime]       # DateTime (naive, UTC), not null

class CheckInRow(Base):                # (M2)
    __tablename__ = "checkins"
    id: Mapped[int]                    # Integer, primary key, autoincrement
    habit_id: Mapped[int]              # ForeignKey("habits.id", ondelete="CASCADE"), not null
    day: Mapped[date]                  # Date, not null
    created_at: Mapped[datetime]       # DateTime (naive, UTC), not null
    # __table_args__ = (UniqueConstraint("habit_id", "day", name="uq_checkins_habit_day"),)

# ---------------------------------------------------------------- habits/storage/repository.py
class SqlHabitRepository(HabitRepository):
    """Implements every HabitRepository method (see core.pyi). Uses session.flush(), never commit():
    the caller owns the transaction. Datetimes: stored naive UTC (`dt.astimezone(UTC).replace(tzinfo=None)`),
    returned tz-aware UTC (`.replace(tzinfo=UTC)`). frequency stored as Frequency.value.
    add_checkin: SELECT first, raise CheckInExists if the row exists; additionally catch IntegrityError from the
    UNIQUE constraint inside `session.begin_nested()` and raise CheckInExists (race backstop).
    delete_habit: ONE `DELETE ... WHERE id = :id`; returns rowcount == 1 (two racing deletes: one True, one False);
    check-ins go via ON DELETE CASCADE. update_habit: raises HabitNotFound if the row no longer exists.
    Ids outside -2**63 .. 2**63-1 never reach SQL: get -> None, delete -> False, update -> HabitNotFound."""
    def __init__(self, session: Session) -> None: ...

# ---------------------------------------------------------------- migrations/ (Alembic)
# alembic.ini at repo root: script_location = migrations; sqlalchemy.url = sqlite:///./habits.db
# migrations/env.py: url = os.environ.get("HABITS_DATABASE_URL") or config.get_main_option("sqlalchemy.url");
#   target_metadata = habits.storage.models.Base.metadata; context.configure(..., render_as_batch=True);
#   if config.attributes.get("connection") is set, use that connection (tests pass one in).
# Revisions are linear, ids are the numbers: "0001" (create habits, M1), "0002" (create checkins, M2, down_revision "0001").
# File names: migrations/versions/0001_create_habits.py, migrations/versions/0002_create_checkins.py
