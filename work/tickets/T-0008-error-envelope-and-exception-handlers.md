---
id: T-0008
title: Error envelope and exception handlers
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: api  # from docs/ai/modules.yaml
depends_on: [T-0001, T-0007]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/api/errors.py, tests/api/test_errors.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 1
base: int/M1  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/api/test_errors.py -x -q", "uv run --frozen ruff check src/habits/api tests/api", "uv run --frozen pyright src/habits/api"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Map every domain error and every request validation error to the single error envelope of ADR-0004.

## Interface
```python
# habits/api/errors.py
STATUS_BY_CODE: dict[str, int] = {
    "habit_not_found": 404, "checkin_not_found": 404,
    "checkin_exists": 409, "habit_archived": 409,
    "invalid_habit": 422, "invalid_range": 422, "future_checkin": 422,
}
def install_error_handlers(app: FastAPI) -> None:
    """DomainError -> STATUS_BY_CODE[exc.code] (unknown code -> 400).
    Body {"error": {"code": exc.code, "message": str(exc), "details": None}}.
    RequestValidationError -> 422 {"error": {"code": "validation_error", "message": "Request validation failed",
    "details": [{"loc": [...], "msg": str}]}}."""
```
Exists: `habits.core.DomainError` (+ subclasses with class attr `code`), `habits.api.schemas.Error/ErrorBody/ErrorDetail`.

## Steps
1. Build the body with `schemas.Error(...).model_dump()` and return `JSONResponse`.
2. For validation details: `[{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]`.
3. Tests first in `tests/api/test_errors.py`: a tiny FastAPI app with routes that raise each core error, plus a route with a typed body/query for the validation case; use `fastapi.testclient.TestClient`.

## Acceptance criteria
- [ ] each of the 7 domain errors → its status and code, message preserved — `test_domain_error_mapping`
- [ ] bad body → 422 `validation_error` with non-empty details having loc and msg — `test_validation_error_envelope`

## Out of scope
- The real app and routes.

## Log
- 2026-11-21 21:13 created from batch batch-M1.md (by architect)
- 2026-11-21 21:13 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:22 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:23 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:23 status in_review -> changes_requested (by run_review): round 1
- 2026-11-21 21:23 status changes_requested -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:24 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:24 status in_review -> approved (by run_review): round 2
