---
covers: [docs/plan/**, src/**]
verified_at: cc7dbb2
owner: architect
---
# Habit Tracker API — overview

## What it is
A small self-hosted HTTP API for one person: create habits that are daily or "N times per week", check them in
once per day, and ask for the current and longest streak and this period's progress.

## Current state
As of M2 the v1 scope is complete: habits CRUD and archiving, check-ins (default today, no future days, one per
day), undo and listing by date range, and stats. Every endpoint follows the hand-written
[OpenAPI contract](../ai/contracts/openapi.yaml), checked by a test. See the [changelog](changelog.md).

## How it fits together
Three layers in one package: `api` (FastAPI) → `core` (rules, streaks, use cases) ← `storage` (SQLAlchemy +
Alembic, SQLite). Diagram: [c4-container.mmd](../architecture/c4-container.mmd); the reasons are in
[architecture.md](architecture.md).

## Where to look next
- Running it: [how-to-run.md](how-to-run.md)
- Design and the reasons behind it: [architecture.md](architecture.md)
- What we set out to build (frozen Phase 0 snapshot + drift log): [../plan/initial-overview.md](../plan/initial-overview.md)
- How the AI agents work on this repo: [workflow.md](workflow.md)
- Models, tiers, budgets and how to change them: [configuration.md](configuration.md)
