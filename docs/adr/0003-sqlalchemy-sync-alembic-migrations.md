# 0003 — SQLAlchemy 2 (sync) + Alembic, explicit migrations, drift test
Status: Proposed
Date: 2026-11-21
supersedes: none

## Context
The schema will evolve (habits in M1, check-ins in M2). SQLite cannot alter most constraints in place, parallel
tickets must never create two Alembic heads, and FastAPI runs sync handlers in a thread pool.

## Options
1. SQLAlchemy 2 sync ORM + Alembic (batch mode) — standard, autogenerate for checks, sync = simple tests.
2. stdlib `sqlite3` + numbered SQL files — fewer deps, hand-written mapping and runner.
3. SQLAlchemy async + aiosqlite — no real gain for SQLite with one user, harder tests.

## Decision
Option 1. Sync `Session` per request (commit on success, rollback on error). Engine: `check_same_thread=False`,
`PRAGMA foreign_keys=ON` on every connection. Alembic lives in `migrations/` with `render_as_batch=True`, linear
hand-numbered revision ids (`0001`, `0002`, ...), URL from `HABITS_DATABASE_URL`. The app never auto-migrates; the user
runs `uv run alembic upgrade head`. Tests build their DB by running the migrations, and a drift test asserts
`compare_metadata(upgraded_db, Base.metadata) == []`. Datetimes are stored naive UTC and returned tz-aware UTC.

## Consequences
- Easier: one schema source (ORM) checked against migrations on every gate run.
- Harder: every model change ships its migration in the same ticket.
- Must change: `migrations/**` and `alembic.ini` are `lock_resources` (one migration ticket at a time).
