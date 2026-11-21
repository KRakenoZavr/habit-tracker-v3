# 0002 — core / storage / api layering with ports in core; single user, no auth
Status: Proposed
Date: 2026-11-21
supersedes: none

## Context
Business rules (validation, streaks) must be testable without a DB or HTTP, and small executor models need narrow,
typed module boundaries. The product is single-user, so there is no identity to thread through calls.

## Options
1. Three layers, core owns the `HabitRepository` Protocol and the use-case functions — pure core, storage plugs in.
2. Fat route handlers calling SQLAlchemy directly — fewer files, rules untestable without a DB.
3. Core + ORM entities shared by all layers — less mapping, but SQLAlchemy leaks into core.

## Decision
Option 1. `habits.core` holds frozen dataclasses, domain errors, pure rules and use-case functions in `services.py`
that take a `HabitRepository` plus `now`/`today` as parameters. `habits.storage` implements the Protocol with
SQLAlchemy and maps rows to core dataclasses (ORM objects never leave storage). `habits.api` is wiring: settings,
session per request, Pydantic schemas, routes, error mapping. Edges: api → core, api → storage, storage → core.
No auth and no users table.

## Consequences
- Easier: core tests use an in-memory fake repository; each ticket stays inside one module.
- Accepted: two simultaneous PATCHes of the same habit can lose one update (read-modify-write, single user,
  SQLite). A PATCH racing a DELETE returns 404, never 500 (M1 review).
- Harder: row ↔ dataclass mapping code in storage; adding users later needs a new ADR and an `owner_id` migration.
- Must change: `docs/ai/modules.yaml` forbidden edges; `tests/test_architecture.py` enforces them.
