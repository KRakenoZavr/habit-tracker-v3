---
id: T-0017
title: Check-in methods on the port, check-in and stats use cases, fake update
status: ready  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M2
module: core  # from docs/ai/modules.yaml
depends_on: [T-0015, T-0016]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/core/ports.py, src/habits/core/services.py, src/habits/core/__init__.py, tests/core/fakes.py, tests/core/test_checkin_services.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: M  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: none               # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/core -x -q", "uv run --frozen ruff check src/habits/core tests/core", "uv run --frozen pyright src/habits/core tests/core"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Grow the `HabitRepository` port with check-in methods and add the check-in and stats use cases. `SqlHabitRepository` already implements the new methods.

## Interface
```python
# ports.py — add to HabitRepository
def add_checkin(self, habit_id: int, day: date, created_at: datetime) -> CheckIn: ...  # duplicate -> CheckInExists
def delete_checkin(self, habit_id: int, day: date) -> bool: ...              # False if missing
def list_checkins(self, habit_id: int, start: date | None, end: date | None) -> list[CheckIn]: ...  # inclusive, day asc
# services.py — add
def check_in(repo: HabitRepository, habit_id: int, day: date, today: date, now: datetime) -> CheckIn:
    """Order of checks: HabitNotFound, HabitArchived, FutureCheckIn (validate_checkin_day), then repo.add_checkin (CheckInExists)."""
def undo_check_in(repo: HabitRepository, habit_id: int, day: date) -> None: ...   # HabitNotFound, CheckInNotFound
def list_check_ins(repo: HabitRepository, habit_id: int, start: date | None, end: date | None) -> list[CheckIn]:
    """HabitNotFound; start and end both set and start > end -> InvalidRange."""
def get_stats(repo: HabitRepository, habit_id: int, today: date) -> HabitStats: ...  # HabitNotFound; compute_stats(habit, days, today)
# __init__.py: also export the four new functions
# tests/core/fakes.py: FakeHabitRepository gains the three methods (duplicate -> CheckInExists; delete_habit also drops its check-ins)
```
Exists in `habits.core`: `CheckIn`, `HabitStats`, `validate_checkin_day`, `compute_stats`, errors `HabitArchived`, `CheckInNotFound`, `InvalidRange`, `CheckInExists`, `HabitNotFound`, and `get_habit(repo, id)`.

## Steps
1. Extend the Protocol, then the fake, then the services.
2. Tests first in `tests/core/test_checkin_services.py` with the fake; keep `tests/core/test_services.py` green.

## Acceptance criteria
- [ ] check_in on a missing / archived habit / future day / duplicate raises the right error in that order (archived + future → HabitArchived) — `test_check_in_errors`
- [ ] check_in stores `now` as created_at — `test_check_in_ok`
- [ ] undo missing → CheckInNotFound; list start > end → InvalidRange; list filters inclusively — `test_undo_and_list`
- [ ] get_stats delegates to compute_stats with the habit's days — `test_get_stats`
- [ ] whole project still type-checks: `SqlHabitRepository` satisfies the grown Protocol (global pyright gate) — `uv run --frozen pyright`

## Out of scope
- API routes and schemas.

## Log
- 2026-11-21 21:42 created from batch batch-M2.md (by architect)
- 2026-11-21 21:42 status draft -> ready (by architect): batch lint clean
