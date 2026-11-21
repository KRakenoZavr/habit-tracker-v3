---
covers: [AGENTS.md, .agents/config.json, pyproject.toml, alembic.ini]
verified_at: none
owner: architect
---
# How to run
## Prerequisites
- [uv](https://docs.astral.sh/uv/) ≥ 0.5 (it installs Python 3.12 and every dependency from `uv.lock`).

## Build and run
```bash
uv sync --frozen
uv run --frozen alembic upgrade head          # creates/updates ./habits.db
uv run --frozen uvicorn habits.api.app:app    # http://127.0.0.1:8000/docs
```
Settings (environment): `HABITS_DATABASE_URL` (default `sqlite:///./habits.db`),
`HABITS_TIMEZONE` (IANA name used for "today", default `UTC`).

Try it:
```bash
curl -X POST localhost:8000/habits -H "Content-Type: application/json" -d '{"name": "Read", "frequency": "weekly", "target_per_week": 3}'
curl -X POST localhost:8000/habits/1/checkins          # checks in today
curl localhost:8000/habits/1/stats
```

## Test
```bash
uv run --frozen pytest -q
uv run --frozen ruff format --check . && uv run --frozen ruff check . && uv run --frozen pyright
python scripts/agent/verify.py   # the same gate the agents use
```

## Troubleshooting
- `no such table: habits` → run `uv run --frozen alembic upgrade head` (the app never migrates by itself).
- pytest `PermissionError` on `%TEMP%\pytest-of-<user>` → already avoided: tests use `.pytest_tmp/` in the checkout.
- `ValueError` about the time zone at start → `HABITS_TIMEZONE` is not a valid IANA name (e.g. `Europe/Berlin`).
