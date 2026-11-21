---
id: T-0006
title: SqlHabitRepository for habits
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: storage  # from docs/ai/modules.yaml
depends_on: [T-0002, T-0005]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/storage/repository.py, src/habits/storage/__init__.py, tests/storage/test_repository.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: M  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 1
base: int/M1  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/storage/test_repository.py -x -q", "uv run --frozen ruff check src/habits/storage tests/storage", "uv run --frozen pyright src/habits/storage"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Implement the habit part of `habits.core.HabitRepository` on SQLAlchemy, returning core dataclasses only.

## Interface
```python
# habits.core (exists)
class HabitRepository(Protocol):
    def add_habit(self, draft: HabitDraft, created_at: datetime) -> Habit: ...   # draft already validated
    def get_habit(self, habit_id: int) -> Habit | None: ...
    def list_habits(self, include_archived: bool) -> list[Habit]: ...            # ordered by id asc
    def update_habit(self, habit: Habit) -> Habit: ...                           # habit exists
    def delete_habit(self, habit_id: int) -> bool: ...                           # False if missing
# habits/storage/repository.py
class SqlHabitRepository(HabitRepository):
    def __init__(self, session: Session) -> None: ...
# Uses session.flush(), never commit(): the caller owns the transaction.
# Datetimes: stored naive UTC (dt.astimezone(UTC).replace(tzinfo=None)), returned tz-aware UTC (.replace(tzinfo=UTC)).
# frequency stored as Frequency.value, read back as Frequency(value).
# __init__.py: add SqlHabitRepository to the existing re-exports (Base, HabitRow, make_engine, make_session_factory).
```
Core types: `Habit(id, name, description, frequency, target_per_week, archived, created_at)`, `HabitDraft(name, description=None, frequency=Frequency.DAILY, target_per_week=None)`.

## Steps
1. Private `_to_habit(row: HabitRow) -> Habit` mapper.
2. Implement the five methods (`update_habit` copies every mutable field onto the row; `delete_habit` uses `session.get`).
3. Tests first in `tests/storage/test_repository.py`: use the `migrated_db_url` fixture from `tests/conftest.py` with `make_engine` + `make_session_factory`; dispose the engine at the end.

## Acceptance criteria
- [ ] add then get round-trips every field; created_at comes back tz-aware UTC and equal — `test_add_get_roundtrip`
- [ ] a non-UTC aware created_at is stored as the same instant — `test_created_at_normalized_to_utc`
- [ ] list ordering by id and archived filter — `test_list_habits`
- [ ] update persists all mutable fields; delete returns True then False; get missing → None — `test_update_delete`
- [ ] repository never commits: rollback after add leaves the table empty — `test_no_commit`

## Out of scope
- Check-in methods (M2), services, API.

## Notes from architect
- ORM rows never leave this module.
- `class SqlHabitRepository(HabitRepository)` explicitly subclasses the Protocol so pyright checks it.

## Log
- 2026-11-21 21:13 created from batch batch-M1.md (by architect)
- 2026-11-21 21:13 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:27 status ready -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 21:28 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:28 status in_review -> changes_requested (by run_review): round 1
- 2026-11-21 21:28 status changes_requested -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 21:29 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:29 status in_review -> approved (by run_review): round 2
