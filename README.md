# Habit Tracker API

A small self-hosted HTTP API for one person: habits that are **daily** or **N times per week**, one check-in per
day, and streak/progress stats. Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · SQLite · uv.

```bash
uv sync --frozen
uv run --frozen alembic upgrade head          # creates ./habits.db
uv run --frozen uvicorn habits.api.app:app    # docs at http://127.0.0.1:8000/docs
```

| Endpoint | What it does |
|---|---|
| `GET /health` | liveness |
| `GET/POST /habits`, `GET/PATCH/DELETE /habits/{id}` | habits CRUD, archive via `PATCH {"archived": true}` |
| `POST/GET /habits/{id}/checkins`, `DELETE /habits/{id}/checkins/{day}` | check in (default today), list by range, undo |
| `GET /habits/{id}/stats` | current/longest streak (days or ISO weeks), this period's progress |

The source of truth for the HTTP API is [docs/ai/contracts/openapi.yaml](docs/ai/contracts/openapi.yaml); a test
checks the app against it. All errors look like `{"error": {"code", "message", "details"}}`.

## Layout
```
src/habits/core      pure domain: dataclasses, rules, streaks, use cases, HabitRepository port
src/habits/storage   SQLAlchemy rows + SqlHabitRepository
src/habits/api       FastAPI app factory, settings, schemas, routes, error envelope
migrations/          Alembic revisions 0001 (habits), 0002 (checkins)
tests/               mirrors src/, plus architecture, migration-drift and contract tests
```

## Docs
- [Overview](docs/human/overview.md) · [Architecture](docs/human/architecture.md) · [How to run](docs/human/how-to-run.md) · [Changelog](docs/human/changelog.md)
- Plan: [vision](docs/plan/vision.md), [milestones](docs/plan/milestones.md), [frozen initial overview + drift log](docs/plan/initial-overview.md), [ADRs](docs/adr/)
- How the AI agents build this repo: [workflow](docs/human/workflow.md) · [configuration](docs/human/configuration.md) · [AGENTS.md](AGENTS.md)
