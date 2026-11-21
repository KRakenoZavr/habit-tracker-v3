---
covers: [src/**, tests/**]
verified_at: none
owner: architect
---
# Conventions (non-obvious only)

## Running anything
- Always through uv with the lock frozen: `uv run --frozen pytest ...`, `uv run --frozen ruff ...`, `uv run --frozen pyright ...`.
  Never `uv add`, `uv lock`, `pip install`: dependencies are architect-only (`pyproject.toml`, `uv.lock` are protected).

## Errors
- Domain failures are `habits.core.errors.DomainError` subclasses with a class-level `code`; never return `None` for failure.
- Only `habits.api.errors` turns them into HTTP responses; routes never build error JSON or raise `HTTPException`.

## Time
- Core never calls `datetime.now()`/`date.today()`; `now` (tz-aware UTC) and `today` (date) are parameters.
- In the API only `deps.get_now` / `deps.get_today` read the clock. Tests override them via `app.dependency_overrides`.
- DB stores naive UTC datetimes; storage converts both ways. API emits ISO 8601 with offset.

## Layers
- ORM rows (`*Row`) never leave `habits.storage`; repositories return core dataclasses.
- Repositories `flush()`, never `commit()`; `api.deps.get_session` owns commit/rollback.
- Route handlers are sync `def` and call `habits.core.services` functions only.

## Naming
- Pydantic classes in `api/schemas.py` are named exactly like the `openapi.yaml` components (`Habit`, `HabitCreate`, ...).
  Import core with `from habits import core` to avoid clashes.

## Testing
- Tests mirror `src/`: `tests/core`, `tests/storage`, `tests/api`. pytest runs with `--import-mode=importlib`; no `__init__.py` in tests.
- Core tests use an in-memory fake repository (`tests/core/fakes.py`), never SQLite.
- Storage/API tests build their DB with the real Alembic migrations on a `tmp_path` file (fixture `migrated_db_url` in `tests/conftest.py`).
- Deterministic: fixed `now`/`today`; no sleeps, no real clock.
