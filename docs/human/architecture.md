---
covers: [docs/ai/modules.yaml, docs/architecture/**, docs/adr/**]
verified_at: none
owner: architect
---
# Architecture

## The big picture
One person talks JSON to one FastAPI process, which keeps everything in one SQLite file
([context](../architecture/c4-context.mmd)). Inside, the code is split so the interesting part — habit rules and
streak math — can be tested without a database or HTTP, and so each AI ticket stays inside one small, typed module
([container diagram](../architecture/c4-container.mmd), [ADR-0002](../adr/0002-core-storage-api-layering.md)).

## Modules
- **core** (`src/habits/core`) — frozen dataclasses, domain errors, validation, streaks, and the use cases. It owns
  the `HabitRepository` *port* (a Protocol) and never does I/O or reads the clock: `now`/`today` come in as arguments.
- **storage** (`src/habits/storage`, `migrations/`) — SQLAlchemy 2 rows and `SqlHabitRepository`, which implements
  the port and hands back core dataclasses only. Alembic migrations (`0001` habits, `0002` check-ins) define the schema.
- **api** (`src/habits/api`) — wiring: settings from env, one DB session per request (committed before the
  response leaves), Pydantic schemas named like the OpenAPI components, thin routes, and one error envelope.

Arrows only point inward to core; `tests/test_architecture.py` fails the build on a forbidden import
(source: [modules.yaml](../ai/modules.yaml)).

## Key flows
A check-in ([dataflow](../architecture/dataflow.mmd)): the route parses the body, picks `today` in
`HABITS_TIMEZONE`, and calls `core.services.check_in`, which checks *habit exists → not archived → not in the
future*, then asks the repository to insert. The database's `UNIQUE(habit_id, day)` is the backstop if two
requests race; either way the client gets `409 checkin_exists`. Any `DomainError` becomes the
`{"error": {code, message, details}}` envelope in `api/errors.py` — so do validation errors, unknown routes and 405s.

Data model: [data-model.mmd](../architecture/data-model.mmd).

## Decisions
- [ADR-0001](../adr/0001-python-fastapi-sqlite-uv.md) Python + FastAPI + SQLite, locked with uv — typed, zero-ops, reproducible per worktree.
- [ADR-0002](../adr/0002-core-storage-api-layering.md) core / storage / api with the port in core; single user — pure domain tests.
- [ADR-0003](../adr/0003-sqlalchemy-sync-alembic-migrations.md) SQLAlchemy sync + Alembic, explicit migrations, drift test — one schema, checked every gate.
- [ADR-0004](../adr/0004-contract-first-openapi-error-envelope.md) hand-written OpenAPI + conformance test + one error envelope.
- [ADR-0005](../adr/0005-habit-frequency-and-streak-rules.md) daily / N-per-week habits, ISO-week streaks with grace for the current period.
- [ADR-0006](../adr/0006-sqlite-begin-immediate.md) every SQLite transaction is `BEGIN IMMEDIATE` — correct rollbacks and atomic read-check-write.

## Known limits and next steps
- Single user, no auth. Every DB transaction starts with `BEGIN IMMEDIATE`, so requests run one at a time:
  no lost updates or check-in/archive races, at the cost of no parallel requests ([ADR-0006](../adr/0006-sqlite-begin-immediate.md)).
- The app does not run migrations on start; run `alembic upgrade head` after every upgrade.
- The contract test compares paths, status codes and schema names, not every field constraint.
- Natural next steps: auth + `owner_id` (new ADR + migration), per-weekday schedules, reminders.
