---
covers: [docs/plan/**]
verified_at: none
owner: human
---
# Vision

## Goal
A small, self-hosted HTTP API for tracking personal habits. The user creates habits (daily, or "N times per week"),
records check-ins per day, and asks for streaks and progress. The code base demonstrates a clean
core / storage / API split with an OpenAPI contract, a dependency lock file and Alembic migrations.

## Users
- One person running the API locally (or on a private box) and calling it from a script, a phone shortcut or a future UI.
  They want: "did I do it today?", "how long is my streak?", "how far am I this week?".

## Non-goals
- Authentication, multiple users, sharing (single-user API; see ADR-0002).
- A UI (web or mobile), notifications/reminders, data import/export.
- Habits scheduled on specific weekdays, or with several check-ins per day.
- Horizontal scaling, other databases than SQLite, async DB drivers.

## Constraints
- Stack: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (sync), Alembic, SQLite. Dependencies and lock via `uv` (`uv.lock`).
- Platforms: Windows, Linux, macOS (dev machine is Windows).
- "Today" is computed in one configured time zone (`HABITS_TIMEZONE`, default `UTC`); the domain never reads the clock.

## Quality bar
- `ruff format --check`, `ruff check`, `pyright` (strict on `src/`) and `pytest` all green; no warnings.
- Every endpoint in `docs/ai/contracts/openapi.yaml` exists in the app with the same status codes (contract test).
- `alembic upgrade head` on an empty file produces exactly the ORM schema (migration drift test).
- Import boundaries between modules are enforced by a test.

## Open questions
- none (resolved in Phase 0: single user, daily + weekly-target habits, SQLAlchemy + Alembic).
