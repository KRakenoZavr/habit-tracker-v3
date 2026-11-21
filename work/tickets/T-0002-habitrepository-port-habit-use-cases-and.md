---
id: T-0002
title: HabitRepository port, habit use cases and in-memory fake
status: escalated  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: core  # from docs/ai/modules.yaml
depends_on: [T-0001]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/core/ports.py, src/habits/core/services.py, src/habits/core/__init__.py, tests/core/fakes.py, tests/core/test_services.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: int/M1  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/core/test_services.py -x -q", "uv run --frozen ruff check src/habits/core tests/core", "uv run --frozen pyright src/habits/core"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Add the repository port and the habit CRUD use cases to `habits.core`, plus an in-memory fake repository that core tests (now and in M2) use instead of a DB.

## Interface
```python
# ports.py
class HabitRepository(Protocol):
    def add_habit(self, draft: HabitDraft, created_at: datetime) -> Habit: ...   # draft already validated
    def get_habit(self, habit_id: int) -> Habit | None: ...
    def list_habits(self, include_archived: bool) -> list[Habit]: ...            # ordered by id asc
    def update_habit(self, habit: Habit) -> Habit: ...                           # habit exists
    def delete_habit(self, habit_id: int) -> bool: ...                           # False if missing
# services.py — each takes the repository first; raise DomainError subclasses, never return None for failure
def create_habit(repo: HabitRepository, draft: HabitDraft, now: datetime) -> Habit: ...        # InvalidHabit
def get_habit(repo: HabitRepository, habit_id: int) -> Habit: ...                               # HabitNotFound
def list_habits(repo: HabitRepository, include_archived: bool = False) -> list[Habit]: ...
def update_habit(repo: HabitRepository, habit_id: int, patch: HabitPatch) -> Habit: ...        # HabitNotFound, InvalidHabit
def delete_habit(repo: HabitRepository, habit_id: int) -> None: ...                            # HabitNotFound
# tests/core/fakes.py
class FakeHabitRepository:   # satisfies HabitRepository; dict storage, ids start at 1 and increment
    def __init__(self) -> None: ...
```
Existing (from the previous ticket): `Habit`, `HabitDraft`, `HabitPatch`, `Frequency`, errors, `validate_draft(draft) -> HabitDraft`, `apply_patch(habit, patch) -> Habit` in `habits.core`.

## Steps
1. `ports.py`: the Protocol above.
2. `services.py`: `create_habit` = `validate_draft` then `repo.add_habit(draft, now)`; `update_habit` = get or HabitNotFound, `apply_patch`, `repo.update_habit`; `delete_habit` raises HabitNotFound when `repo.delete_habit` returns False.
3. Messages name the id, e.g. `HabitNotFound(f"habit {habit_id} not found")`.
4. `core/__init__.py`: also re-export `HabitRepository` and `services` functions (keep existing exports).
5. `tests/core/fakes.py`: `FakeHabitRepository` (`created_at` stored as given; `list_habits` sorted by id, filters archived unless asked).
6. Tests first in `tests/core/test_services.py`, using the fake (import: `from tests.core.fakes import FakeHabitRepository`).

## Acceptance criteria
- [ ] create normalizes via validate_draft and stores `now` as created_at — `test_create_habit`
- [ ] invalid draft raises InvalidHabit and stores nothing — `test_create_habit_invalid`
- [ ] get/update/delete of a missing id raise HabitNotFound — `test_missing_habit_raises`
- [ ] list hides archived by default, shows with include_archived=True, sorted by id — `test_list_habits`
- [ ] update applies the patch and persists it — `test_update_habit`
- [ ] pyright accepts `FakeHabitRepository` as a `HabitRepository` (annotate a variable with the Protocol in a test) — `test_fake_satisfies_port`

## Out of scope
- Check-in methods on the port (M2), SQL implementation.

## Notes from architect
- Services never call the clock: `now` is a parameter.
- pytest runs with `--import-mode=importlib` and `pythonpath=["."]`; tests have no `__init__.py`.

## Log
- 2026-11-21 21:13 created from batch batch-M1.md (by architect)
- 2026-11-21 21:13 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:20 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:20 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:21 status in_review -> escalated (by run_review): round 1
