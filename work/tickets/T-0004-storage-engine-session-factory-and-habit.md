---
id: T-0004
title: Storage engine, session factory and HabitRow ORM model
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: storage  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/storage/__init__.py, src/habits/storage/db.py, src/habits/storage/models.py, tests/storage/test_db.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: int/M1  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/storage/test_db.py -x -q", "uv run --frozen ruff check src/habits/storage tests/storage", "uv run --frozen pyright src/habits/storage"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
SQLAlchemy 2 (sync) engine and session helpers with SQLite pragmas, and the `habits` table ORM model (ADR-0003).

## Interface
```python
# db.py
def make_engine(url: str) -> Engine:
    """create_engine(url). For sqlite URLs: connect_args={"check_same_thread": False} and a "connect" event
    listener that runs PRAGMA foreign_keys=ON on every DBAPI connection."""
def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """sessionmaker(bind=engine, expire_on_commit=False)."""
# models.py
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
# __init__.py re-exports: Base, HabitRow, make_engine, make_session_factory
```

## Steps
1. `db.py` with `sqlalchemy.event.listens_for(engine, "connect")` for the pragma (sqlite only: `engine.dialect.name == "sqlite"`).
2. `models.py` with explicit `mapped_column(...)` types as listed (the next ticket's migration must match them exactly).
3. Tests first in `tests/storage/test_db.py` using an in-memory URL `sqlite://` and `Base.metadata.create_all`.

## Acceptance criteria
- [ ] `PRAGMA foreign_keys` returns 1 on a new connection — `test_foreign_keys_on`
- [ ] insert + select a HabitRow through a session from the factory; `archived` defaults to False — `test_habit_row_roundtrip`
- [ ] frequency "monthly" violates the check constraint (IntegrityError) — `test_frequency_check_constraint`

## Out of scope
- Alembic migrations, repository, check-in table (M2).

## Notes from architect
- Imports allowed: sqlalchemy, stdlib, habits.core. Never fastapi/pydantic.
- pyright strict on src: use `Mapped[...]` + `mapped_column`, no untyped `Column`.

## Log
- 2026-11-21 21:13 created from batch batch-M1.md (by architect)
- 2026-11-21 21:13 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:14 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:16 status in_progress -> blocked (by run_loop): gates still failing after 3 worker runs
- 2026-11-21 21:17 status blocked -> in_progress (by architect): gate failure was global (ruff linted docs/*.pyi); fixed on int/M1 and merged
- 2026-11-21 21:17 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:19 status in_review -> approved (by run_review): round 1
