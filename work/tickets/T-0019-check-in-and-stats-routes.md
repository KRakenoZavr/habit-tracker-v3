---
id: T-0019
title: Check-in and stats routes
status: ready  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M2
module: api  # from docs/ai/modules.yaml
depends_on: [T-0017, T-0018]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/api/routes/checkins.py, src/habits/api/app.py, tests/api/test_checkins.py, tests/api/test_stats.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: M  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: none               # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/api -x -q", "uv run --frozen ruff check src/habits/api tests/api", "uv run --frozen pyright src/habits/api tests/api/test_checkins.py tests/api/test_stats.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Expose check-ins and stats over HTTP as in `openapi.yaml`, using the existing app factory, dependencies and error envelope.

## Interface
```python
# routes/checkins.py: router = APIRouter(); sync `def` handlers calling habits.core.services only
# POST   /habits/{habit_id}/checkins          body: schemas.CheckInCreate | None = None; status_code=201 -> schemas.CheckIn
#        day = body.day if body and body.day else today (deps.get_today); now from deps.get_now
#        responses={404: Error, 409: Error, 422: Error}
# GET    /habits/{habit_id}/checkins?start=&end=   (date | None) -> list[schemas.CheckIn]; responses={404, 422}
# DELETE /habits/{habit_id}/checkins/{day}     (day: date) status_code=204; responses={404, 422}
# GET    /habits/{habit_id}/stats              -> schemas.Stats (today from deps.get_today); responses={404, 422}
# app.py: create_app also includes routes.checkins.router
```
Exists: `services.check_in(repo, habit_id, day, today, now)`, `undo_check_in(repo, habit_id, day)`, `list_check_ins(repo, habit_id, start, end)`, `get_stats(repo, habit_id, today)`; `schemas.CheckIn/CheckInCreate/Stats` with `from_core`; `deps.get_repo`, `deps.get_today`, `deps.get_now`; `schemas.Error`. Look at `routes/habits.py` and copy its dependency style exactly. `tests/api/conftest.py` gives `client` with `get_today` = date(2026, 1, 15) and `get_now` fixed.

## Steps
1. `routes/checkins.py`, include the router in `app.py`.
2. Tests first in `tests/api/test_checkins.py` and `tests/api/test_stats.py` with the `client` fixture.

## Acceptance criteria
- [ ] POST without body and with `{}` checks in today (2026-01-15) → 201; explicit past day works — `test_checkin_defaults_to_today`
- [ ] future day → 422 `future_checkin`; duplicate → 409 `checkin_exists`; archived habit → 409 `habit_archived`; missing habit → 404 `habit_not_found` — `test_checkin_errors`
- [ ] list with start/end inclusive and ordered; start > end → 422 `invalid_range` — `test_list_checkins`
- [ ] DELETE → 204 then 404 `checkin_not_found` — `test_delete_checkin`
- [ ] deleting the habit removes its check-ins (re-create habit, list is empty) — `test_delete_habit_cascades_over_http`
- [ ] stats for a daily habit with check-ins on 13, 14 → current 2, period 0/1; weekly target 2 → streak_unit "week" — `test_stats_daily`, `test_stats_weekly`
- [ ] race backstop over HTTP: two POSTs for the same day → exactly one 201 and one 409 `checkin_exists` — `test_duplicate_checkin_conflict`

## Out of scope
- OpenAPI contract test (next ticket).

## Log
- 2026-11-21 21:42 created from batch batch-M2.md (by architect)
- 2026-11-21 21:42 status draft -> ready (by architect): batch lint clean
