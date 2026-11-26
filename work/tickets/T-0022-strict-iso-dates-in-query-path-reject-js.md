---
id: T-0022
title: Strict ISO dates in query/path, reject JSON null body, one clock read per request
status: integrated  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M2
module: api  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/api/schemas.py, src/habits/api/routes/checkins.py, src/habits/api/deps.py, tests/api/test_checkin_strict.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: M  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 1
base: int/M2  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/api -x -q", "uv run --frozen ruff check src/habits/api tests/api", "uv run --frozen pyright src/habits/api tests/api/test_checkin_strict.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Fix M2 review findings 3–5: `start`/`end`/`{day}` accept Unix timestamps and datetimes, a literal JSON `null` body creates a check-in, and `today` and `created_at` come from two separate clock reads.

## Interface
```python
# schemas.py
def _iso_date(value: object) -> object: ...   # str matching r"^\d{4}-\d{2}-\d{2}$" -> pass on; date (not datetime) -> pass on; else ValueError("expected YYYY-MM-DD")
IsoDate = Annotated[date, BeforeValidator(_iso_date)]
class CheckInCreate(BaseModel):
    day: IsoDate | None = None     # replaces the existing field validator; same behaviour for bodies
# routes/checkins.py
#   POST body:   body: schemas.CheckInCreate = Body(default_factory=schemas.CheckInCreate)
#                -> absent body = default; JSON null -> 422 validation_error (not Optional any more)
#   GET  start: IsoDate | None = Query(default=None), end: same
#   DELETE path day: IsoDate = Path()
# deps.py
def get_now() -> datetime: ...                                          # unchanged: datetime.now(UTC)
def get_today(request: Request, now: datetime = Depends(get_now)) -> date: ...
#   = now.astimezone(ZoneInfo(settings.timezone)).date()   (FastAPI caches get_now per request: one read)
```

## Steps
1. `IsoDate` in schemas.py, used by `CheckInCreate`.
2. Routes use `IsoDate` for query and path dates and the non-optional body with `default_factory`.
3. `get_today` derived from `get_now`.
4. Tests first in `tests/api/test_checkin_strict.py` (fixture `client` from `tests/api/conftest.py`; for the clock test build your own app with `create_app(Settings(database_url=migrated_db_url, timezone="Asia/Tokyo"))` and override ONLY `get_now`).

## Acceptance criteria
- [ ] `DELETE /habits/1/checkins/1768435200` and `.../2026-01-15T00:00:00` → 422 `validation_error` and the check-in still exists — `test_delete_rejects_timestamp_day`
- [ ] `GET ...?start=1768435200` and `?end=2026-01-15T00:00` → 422 `validation_error` — `test_list_rejects_non_iso_dates`
- [ ] POST with body `null` (`content="null"`, JSON content type) → 422 `validation_error`, no row; no body and `{}` still → 201 today — `test_null_body_rejected`
- [ ] now = 2026-01-14T15:30Z with timezone Asia/Tokyo: default check-in day is 2026-01-15 and stats `as_of` is 2026-01-15 — `test_today_derived_from_now`
- [ ] the whole api suite stays green, including the contract test — `uv run --frozen pytest tests/api -x -q`

## Out of scope
- Storage, core.

## Notes from architect
- `tests/api/conftest.py` overrides both `get_now` and `get_today`; keep it as is.
- If `Body(default_factory=...)` changes the OpenAPI `requestBody` so the contract test fails, set blocked with the diff instead of editing the test.

## Log
- 2026-11-21 21:59 created from batch batch-M2-fix.md (by architect)
- 2026-11-21 21:59 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:59 status ready -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 22:02 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 22:02 status in_review -> changes_requested (by run_review): round 1
- 2026-11-21 22:02 status changes_requested -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 22:03 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 22:03 status in_review -> approved (by run_review): round 2
- 2026-11-21 22:04 status approved -> integrated (by integrate): merged into int/M2
