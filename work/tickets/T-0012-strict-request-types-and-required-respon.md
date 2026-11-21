---
id: T-0012
title: Strict request types and required response fields
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: api  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/api/schemas.py, src/habits/api/app.py, tests/api/test_schemas.py, tests/api/test_habits.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: int/M1  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/api/test_schemas.py tests/api/test_habits.py -x -q", "uv run --frozen ruff check src/habits/api tests/api", "uv run --frozen pyright src/habits/api tests/api/test_schemas.py tests/api/test_habits.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Request bodies must not coerce JSON types (`true` / `"3"` → int, `"false"` → bool), and contract-required response fields must have no defaults (M1 review findings 3 and 8).

## Interface
```python
# schemas.py
class HabitCreate(BaseModel):
    name: StrictStr = Field(min_length=1, max_length=100)
    description: StrictStr | None = Field(default=None, max_length=500)
    frequency: core.Frequency = core.Frequency.DAILY
    target_per_week: StrictInt | None = Field(default=None, ge=1, le=7)
class HabitUpdate(BaseModel):   # same fields optional; archived: StrictBool | None = None
class Health(BaseModel): status: Literal["ok"]            # required, no default
class ErrorBody(BaseModel): code: str; message: str; details: list[ErrorDetail] | None   # required, may be null
# app.py /health returns schemas.Health(status="ok")
```

## Steps
1. Switch request fields to `StrictStr` / `StrictInt` / `StrictBool` (from pydantic); keep limits and converters.
2. Remove the defaults on `Health.status` and `ErrorBody.details`; update every constructor call you own.
3. Tests first: HTTP tests in `tests/api/test_habits.py` (fixture `client` from `tests/api/conftest.py`), model tests in `tests/api/test_schemas.py`.

## Acceptance criteria
- [ ] POST `target_per_week: true` and `"3"` → 422 `validation_error`, nothing stored — `test_create_rejects_coerced_types`
- [ ] PATCH `archived: "false"` and `target_per_week: true` → 422 `validation_error`, habit unchanged — `test_update_rejects_coerced_types`
- [ ] `Health()` and `ErrorBody(code="x", message="y")` raise ValidationError; `/health` still 200 — `test_required_response_fields`
- [ ] in `app.openapi()`, `Health` requires `status` and `ErrorBody` requires `details` — `test_openapi_required_fields`

## Out of scope
- Error handlers (`errors.py`), check-in schemas (M2).

## Notes from architect
- `errors.py` builds `ErrorBody(..., details=None)` already or via dict — if it calls `ErrorBody` without `details`, that is a different ticket's file: check `uv run --frozen pytest tests/api -x -q` stays green; if it does not, set blocked with the reason.

## Log
- 2026-11-21 21:36 created from batch batch-M1-fix.md (by architect)
- 2026-11-21 21:36 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:38 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:39 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:40 status in_review -> approved (by run_review): round 1
