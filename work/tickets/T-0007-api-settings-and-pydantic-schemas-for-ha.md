---
id: T-0007
title: API settings and Pydantic schemas for habits and errors
status: ready  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: api  # from docs/ai/modules.yaml
depends_on: [T-0001]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/api/__init__.py, src/habits/api/settings.py, src/habits/api/schemas.py, tests/api/test_schemas.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: none               # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/api/test_schemas.py -x -q", "uv run --frozen ruff check src/habits/api tests/api", "uv run --frozen pyright src/habits/api"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Settings loaded from the environment and the Pydantic v2 models of the HTTP contract (ADR-0004), with converters to and from core types.

## Interface
```python
# settings.py
@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = "sqlite:///./habits.db"
    timezone: str = "UTC"            # IANA name, validated with zoneinfo.ZoneInfo at load time
    @classmethod
    def from_env(cls) -> "Settings": ...  # HABITS_DATABASE_URL, HABITS_TIMEZONE; unset -> defaults; bad tz -> ValueError
# schemas.py — CLASS NAMES must equal the openapi component names
class Health(BaseModel): status: Literal["ok"] = "ok"
class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    frequency: core.Frequency = core.Frequency.DAILY
    target_per_week: int | None = Field(default=None, ge=1, le=7)
    def to_draft(self) -> core.HabitDraft: ...
class HabitUpdate(BaseModel):          # absent field = unchanged
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    frequency: core.Frequency | None = None
    target_per_week: int | None = Field(default=None, ge=1, le=7)
    archived: bool | None = None
    def to_patch(self) -> core.HabitPatch: ...   # description sent (in model_fields_set) as null or "" -> "" (clear); absent -> None
class Habit(BaseModel):
    id: int; name: str; description: str | None; frequency: core.Frequency
    target_per_week: int | None; archived: bool; created_at: datetime
    @classmethod
    def from_core(cls, h: core.Habit) -> "Habit": ...
class ErrorDetail(BaseModel): loc: list[str | int]; msg: str
class ErrorBody(BaseModel): code: str; message: str; details: list[ErrorDetail] | None = None
class Error(BaseModel): error: ErrorBody
```
`core` = `from habits import core` (exports Frequency, Habit, HabitDraft, HabitPatch).

## Steps
1. `settings.py` (validate tz with `zoneinfo.ZoneInfo`, raise ValueError with the bad name).
2. `schemas.py` exactly as above; `api/__init__.py` is a docstring only.
3. Tests first in `tests/api/test_schemas.py` (use `monkeypatch.setenv/delenv`).

## Acceptance criteria
- [ ] env vars read, defaults when unset, bad timezone → ValueError — `test_settings_from_env`
- [ ] HabitCreate defaults and to_draft — `test_habit_create_to_draft`
- [ ] HabitUpdate.to_patch: absent→None, description null→"", archived passed through — `test_habit_update_to_patch`
- [ ] Habit.from_core keeps created_at tz-aware; JSON dump has an offset — `test_habit_from_core`
- [ ] target_per_week 0 / 8 and name "" fail Pydantic validation — `test_field_limits`

## Out of scope
- Routes, error handlers, check-in/stats schemas (M2).

## Log
- 2026-11-21 21:13 created from batch batch-M1.md (by architect)
- 2026-11-21 21:13 status draft -> ready (by architect): batch lint clean
