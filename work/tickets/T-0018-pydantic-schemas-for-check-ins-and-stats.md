---
id: T-0018
title: Pydantic schemas for check-ins and stats
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M2
module: api  # from docs/ai/modules.yaml
depends_on: [T-0015]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/api/schemas.py, tests/api/test_checkin_schemas.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 1
base: int/M2  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/api/test_checkin_schemas.py tests/api/test_schemas.py -x -q", "uv run --frozen ruff check src/habits/api tests/api", "uv run --frozen pyright src/habits/api tests/api/test_checkin_schemas.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Add the request/response models for check-ins and stats to `habits.api.schemas`; class names equal the openapi component names.

## Interface
```python
class CheckInCreate(BaseModel):
    day: date | None = None          # null/absent -> today (decided by the route, not here)
class CheckIn(BaseModel):
    habit_id: int; day: date; created_at: datetime
    @classmethod
    def from_core(cls, c: core.CheckIn) -> "CheckIn": ...
class Stats(BaseModel):
    habit_id: int
    streak_unit: Literal["day", "week"]
    current_streak: int = Field(ge=0); longest_streak: int = Field(ge=0); total_checkins: int = Field(ge=0)
    period_count: int = Field(ge=0); period_target: int = Field(ge=1); period_done: bool; as_of: date
    @classmethod
    def from_core(cls, s: core.HabitStats) -> "Stats": ...
```
Exists: `core.CheckIn(habit_id, day, created_at)`, `core.HabitStats(...)` with the same field names; `schemas.py` already imports `from habits import core`.

## Steps
1. Add the three models; keep every existing model unchanged.
2. Tests first in `tests/api/test_checkin_schemas.py`.

## Acceptance criteria
- [ ] CheckIn.from_core keeps fields; JSON `day` is "YYYY-MM-DD", created_at has an offset — `test_checkin_from_core`
- [ ] Stats.from_core copies all 9 fields — `test_stats_from_core`
- [ ] CheckInCreate accepts `{}` and `{"day": null}` (day None) and rejects `{"day": "nope"}` and `{"day": 20260115}` — `test_checkin_create`
- [ ] response models have no defaults: `CheckIn()` / `Stats()` missing any field raise ValidationError — `test_response_fields_required`

## Out of scope
- Routes.

## Notes from architect
- Follow the existing style in schemas.py: request fields strict (no int/str coercion), response fields required, no defaults.

## Log
- 2026-11-21 21:42 created from batch batch-M2.md (by architect)
- 2026-11-21 21:42 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:45 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:46 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:46 status in_review -> changes_requested (by run_review): round 1
- 2026-11-21 21:46 status changes_requested -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:47 status in_progress -> in_review (by run_executor): gates passed
-