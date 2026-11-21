---
id: T-0009
title: App factory, request dependencies and habit routes
status: integrated  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: api  # from docs/ai/modules.yaml
depends_on: [T-0006, T-0008]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/api/deps.py, src/habits/api/app.py, src/habits/api/routes/__init__.py, src/habits/api/routes/habits.py, tests/api/conftest.py, tests/api/test_habits.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: [docs/ai/contracts/openapi.yaml]  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: M  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 1
base: int/M1  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/api/test_habits.py -x -q", "uv run --frozen ruff check src/habits/api tests/api", "uv run --frozen pyright src/habits/api"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Wire FastAPI to core services and storage: `/health` and the five habit operations of `openapi.yaml`, runnable with `uvicorn habits.api.app:app`.

## Interface
```python
# deps.py   (app.state.settings, app.state.engine, app.state.session_factory are set by create_app)
def get_session(request: Request) -> Iterator[Session]: ...   # yield; commit on success, rollback on exception, always close
def get_repo(session: Session = Depends(get_session, scope="function")) -> HabitRepository: ...  # SqlHabitRepository(session)
def get_now() -> datetime: ...                                 # datetime.now(UTC)
def get_today(request: Request) -> date: ...                   # datetime.now(ZoneInfo(settings.timezone)).date()
# app.py
def create_app(settings: Settings | None = None) -> FastAPI:
    """settings or Settings.from_env(); make_engine + make_session_factory into app.state; install_error_handlers;
    include routes.habits.router; GET /health -> schemas.Health. Never runs migrations."""
app: FastAPI   # = create_app()
# routes/habits.py: router = APIRouter(); sync `def` handlers calling habits.core.services only:
# GET /habits (include_archived: bool = False) -> list[schemas.Habit]
# POST /habits status_code=201 -> schemas.Habit          GET /habits/{habit_id} -> schemas.Habit
# PATCH /habits/{habit_id} -> schemas.Habit              DELETE /habits/{habit_id} status_code=204
# every route: responses={404: {"model": schemas.Error}, 422: {"model": schemas.Error}} as applicable
```
Exists: `services.create_habit(repo, draft, now)`, `get_habit`, `list_habits(repo, include_archived)`, `update_habit(repo, id, patch)`, `delete_habit`; `schemas.HabitCreate.to_draft()`, `HabitUpdate.to_patch()`, `Habit.from_core()`; `install_error_handlers(app)`; `SqlHabitRepository(session)`, `make_engine`, `make_session_factory`; `Settings`.

## Steps
1. `deps.py`; use `Depends(get_session, scope="function")` so the commit happens BEFORE the response is sent.
2. `routes/habits.py` (`routes/__init__.py` empty docstring) and `app.py`.
3. `tests/api/conftest.py`: fixture `client(migrated_db_url)` → `create_app(Settings(database_url=url))`, override `get_now` with `FIXED_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)` and `get_today` with `date(2026, 1, 15)`, yield `TestClient(app)` in a `with` block, then `app.state.engine.dispose()`.
4. Tests first in `tests/api/test_habits.py`.

## Acceptance criteria
- [ ] `/health` → 200 `{"status": "ok"}` — `test_health`
- [ ] POST 201 body matches `Habit`, created_at == FIXED_NOW with offset; blank name → 422 `invalid_habit`; weekly without target → 422 `invalid_habit`; 101-char name → 422 `validation_error` — `test_create_habit*`
- [ ] list hides archived unless `include_archived=true`, ordered by id — `test_list_habits`
- [ ] PATCH archive + switch to weekly with target; missing id → 404 `habit_not_found` — `test_update_habit*`
- [ ] DELETE → 204, then GET → 404; DELETE missing → 404 — `test_delete_habit`
- [ ] a write is visible to the very next request (committed before response) — `test_write_committed_before_response`
- [ ] real entry point: `from habits.api.app import app` is a FastAPI with route `/health` — `test_module_app_importable`

## Out of scope
- Check-ins and stats routes (M2), OpenAPI contract test (M2), running migrations at startup.

## Notes from architect
- Handlers never touch sqlalchemy or raise HTTPException: raise/propagate DomainError and let errors.py map it.
- FastAPI 0.165: `Depends(..., scope="function")` exists; keep handlers plain `def`.

## Log
- 2026-11-21 21:13 created from batch batch-M1.md (by architect)
- 2026-11-21 21:13 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:29 status ready -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 21:31 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:31 status in_review -> changes_requested (by run_review): round 1
- 2026-11-21 21:31 status changes_requested -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 21:32 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:32 status in_review -> approved (by run_review): round 2
- 2026-11-21 21:32 status approved -> integrated (by integrate): merged into int/M1
