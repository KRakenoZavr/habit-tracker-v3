---
id: T-0013
title: Error envelope for framework HTTP errors (404 route, 405)
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: api  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/api/errors.py, tests/api/test_errors.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: int/M1  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/api/test_errors.py -x -q", "uv run --frozen ruff check src/habits/api tests/api", "uv run --frozen pyright src/habits/api tests/api/test_errors.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Unknown routes and wrong methods must answer with the same error envelope as everything else, keeping protocol headers (M1 review finding 6).

## Interface
```python
# errors.py, inside install_error_handlers(app):
@app.exception_handler(starlette.exceptions.HTTPException)
# -> JSONResponse(status_code=exc.status_code, headers=exc.headers,
#    content={"error": {"code": CODE, "message": str(exc.detail), "details": None}})
# CODE: 404 -> "not_found", 405 -> "method_not_allowed", any other -> f"http_{exc.status_code}"
```

## Steps
1. Add the handler (register for `starlette.exceptions.HTTPException`, which also covers FastAPI's subclass).
2. Always pass `details=None` explicitly when building the body.
3. Tests first in `tests/api/test_errors.py`: real-app tests use the `client` fixture from `tests/api/conftest.py`.

## Acceptance criteria
- [ ] `PUT /habits` → 405, code `method_not_allowed`, `Allow` header present — `test_405_envelope`
- [ ] `GET /nope` → 404, code `not_found` — `test_unknown_route_envelope`
- [ ] existing domain/validation mapping tests still pass — `test_domain_error_mapping`, `test_validation_error_envelope`

## Out of scope
- Schemas, routes.

## Log
- 2026-11-21 21:36 created from batch batch-M1-fix.md (by architect)
- 2026-11-21 21:36 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:39 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:40 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:40 status in_review -> approved (by run_review): round 1
