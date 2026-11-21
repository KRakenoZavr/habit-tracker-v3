---
id: T-0001
title: Core models, domain errors and habit validation rules
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: core  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/core/__init__.py, src/habits/core/models.py, src/habits/core/errors.py, src/habits/core/rules.py, tests/core/test_rules.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 1
base: int/M1  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/core/test_rules.py -x -q", "uv run --frozen ruff check src/habits/core tests/core", "uv run --frozen pyright src/habits/core"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Create the pure domain types, the domain error hierarchy and the habit validation rules of `habits.core`. Stdlib only.

## Interface
```python
# models.py
class Frequency(StrEnum): DAILY = "daily"; WEEKLY = "weekly"
NAME_MAX = 100
DESCRIPTION_MAX = 500
@dataclass(frozen=True, slots=True)
class HabitDraft:
    name: str
    description: str | None = None
    frequency: Frequency = Frequency.DAILY
    target_per_week: int | None = None
@dataclass(frozen=True, slots=True)
class Habit:
    id: int; name: str; description: str | None; frequency: Frequency
    target_per_week: int | None   # None for daily, 1..7 for weekly
    archived: bool; created_at: datetime   # tz-aware UTC
@dataclass(frozen=True, slots=True)
class HabitPatch:          # every field None = "leave unchanged"
    name: str | None = None
    description: str | None = None   # "" clears the description (stored as None)
    frequency: Frequency | None = None
    target_per_week: int | None = None
    archived: bool | None = None
# errors.py
class DomainError(Exception):
    code: ClassVar[str]
    def __init__(self, message: str) -> None: ...   # str(err) == message; also self.message = message
class InvalidHabit(DomainError): code = "invalid_habit"
class InvalidRange(DomainError): code = "invalid_range"
class FutureCheckIn(DomainError): code = "future_checkin"
class HabitNotFound(DomainError): code = "habit_not_found"
class CheckInNotFound(DomainError): code = "checkin_not_found"
class CheckInExists(DomainError): code = "checkin_exists"
class HabitArchived(DomainError): code = "habit_archived"
# rules.py
def validate_draft(draft: HabitDraft) -> HabitDraft:
    """Return a normalized copy or raise InvalidHabit.
    name: strip(); 1..NAME_MAX chars after strip. description: strip(); "" -> None; <= DESCRIPTION_MAX chars.
    daily: target_per_week must be None. weekly: target_per_week required, 1..7."""
def apply_patch(habit: Habit, patch: HabitPatch) -> Habit:
    """Return the updated habit or raise InvalidHabit. Same field rules as validate_draft.
    If the resulting frequency is daily, target_per_week becomes None (a non-None patch.target_per_week with a
    resulting daily frequency -> InvalidHabit). Switching to weekly without any target -> InvalidHabit.
    id and created_at never change."""
```

## Steps
1. Write `models.py` and `errors.py` exactly as in the Interface (use `dataclasses.replace` for copies later).
2. Write `rules.py`: `validate_draft` and `apply_patch` (apply_patch: merge fields, then reuse the same checks).
3. `core/__init__.py` re-exports every public name above (`__all__`).
4. Tests first in `tests/core/test_rules.py`: table tests for every rule and every error branch.

## Acceptance criteria
- [ ] name stripped, blank / 101 chars rejected, 100 accepted — `test_validate_draft_name`
- [ ] description "" / whitespace -> None, 501 chars rejected — `test_validate_draft_description`
- [ ] daily with target rejected; weekly target None/0/8 rejected, 1 and 7 accepted — `test_validate_draft_frequency_target`
- [ ] apply_patch: unchanged on empty patch; description "" clears; weekly->daily clears target; daily->weekly without target rejected; daily + target rejected; archived toggles; id/created_at kept — `test_apply_patch_*`
- [ ] every error subclass has its `code` and `str(err) == message` — `test_error_codes`

## Out of scope
- Check-ins, streaks, services, repository port (later tickets).

## Notes from architect
- Stdlib only: no pydantic/sqlalchemy/fastapi imports in `habits.core` (an architecture test enforces this).
- pyright runs in strict mode on `src/`: full type hints, no `Any`.

## Log
- 2026-11-21 21:13 created from batch batch-M1.md (by architect)
- 2026-11-21 21:13 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:13 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:15 status in_progress -> blocked (by run_loop): gates still failing after 3 worker runs
- 2026-11-21 21:17 status blocked -> in_progress (by architect): gate failure was global (ruff linted docs/*.pyi); fixed on int/M1 and merged
- 2026-11-21 21:17 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:18 status in_review -> changes_requested (by run_review): round 1
- 2026-11-21 21:18 status changes_requested -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:18 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:18 status in_review -> approved (by run_review): round 2
