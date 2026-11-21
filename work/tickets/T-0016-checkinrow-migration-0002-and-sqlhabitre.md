---
id: T-0016
title: CheckInRow, migration 0002 and SqlHabitRepository check-in methods
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M2
module: storage  # from docs/ai/modules.yaml
depends_on: [T-0015]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/storage/models.py, src/habits/storage/repository.py, src/habits/storage/__init__.py, migrations/versions/0002_create_checkins.py, tests/storage/test_checkin_repository.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: [migrations/**]  # lock files this ticket must touch (see .agents/config.json)
difficulty: M  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: int/M2  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/storage -x -q", "uv run --frozen ruff check src/habits/storage migrations tests/storage", "uv run --frozen pyright src/habits/storage migrations tests/storage/test_checkin_repository.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Persist check-ins: ORM row, Alembic migration 0002 and three repository methods. The existing drift test in `tests/storage/test_migrations.py` must keep passing (it judges the migration).

## Interface
```python
# models.py (add)
class CheckInRow(Base):
    __tablename__ = "checkins"
    id: Mapped[int]          # Integer, primary key, autoincrement
    habit_id: Mapped[int]    # ForeignKey("habits.id", ondelete="CASCADE"), not null
    day: Mapped[date]        # Date, not null
    created_at: Mapped[datetime]   # DateTime (naive, UTC), not null
    __table_args__ = (UniqueConstraint("habit_id", "day", name="uq_checkins_habit_day"),)
# migrations/versions/0002_create_checkins.py: revision = "0002", down_revision = "0001"; create/drop "checkins" exactly as above
# repository.py — add to SqlHabitRepository (same flush-never-commit and UTC rules as the habit methods)
def add_checkin(self, habit_id: int, day: date, created_at: datetime) -> CheckIn: ...
    # SELECT first: existing row -> raise CheckInExists(f"habit {habit_id} already checked in on {day}");
    # also wrap the INSERT+flush in `with self._session.begin_nested():` and turn IntegrityError into CheckInExists
def delete_checkin(self, habit_id: int, day: date) -> bool: ...      # False if missing
def list_checkins(self, habit_id: int, start: date | None, end: date | None) -> list[CheckIn]: ...  # inclusive bounds, day asc
# __init__.py: also export CheckInRow
```
Core (exists): `CheckIn(habit_id, day, created_at)`, `CheckInExists` in `habits.core`.

## Steps
1. CheckInRow and migration 0002 (`op.create_table` with the FK `ondelete="CASCADE"` and the named unique constraint).
2. The three methods with a private `_to_checkin(row)` mapper.
3. Tests first in `tests/storage/test_checkin_repository.py` using the `migrated_db_url` fixture from `tests/conftest.py`.

## Acceptance criteria
- [ ] add/list round-trip, ordered by day, start/end inclusive, created_at tz-aware UTC — `test_add_and_list_checkins`
- [ ] second add on the same day raises CheckInExists and the session is still usable afterwards — `test_duplicate_checkin`
- [ ] UNIQUE backstop: inserting a duplicate CheckInRow directly raises IntegrityError — `test_unique_constraint`
- [ ] delete returns True then False — `test_delete_checkin`
- [ ] deleting the habit through `delete_habit` removes its check-ins (FK cascade, PRAGMA on) — `test_delete_habit_cascades`
- [ ] `uv run --frozen pytest tests/storage -x -q` passes, including the existing drift test — `test_no_drift`

## Out of scope
- Adding the methods to the core Protocol (next ticket), API.

## Notes from architect
- Do not edit `tests/storage/test_migrations.py` or `tests/conftest.py`; they already upgrade to "head" and the drift test compares server defaults too.
- `delete_checkin`: ONE `sa.delete(...)` statement, return `rowcount == 1` (same pattern as `delete_habit`); ids outside int64 (use the existing `_in_range`) → False / [] without SQL.
- Dispose engines in tests (Windows file locks).

## Log
- 2026-11-21 21:42 created from batch batch-M2.md (by architect)
- 2026-11-21 21:42 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:45 status ready -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 21:46 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:47 status in_review -> approved (by run_review): round 1
