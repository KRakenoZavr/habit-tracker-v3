---
id: T-0011
title: Alembic env uses a supplied connection; stronger drift checks
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: storage  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [migrations/env.py, tests/storage/test_migrations.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: [migrations/**]  # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: int/M1  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/storage/test_migrations.py -x -q", "uv run --frozen ruff check migrations tests/storage", "uv run --frozen pyright migrations tests/storage/test_migrations.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
`migrations/env.py` must migrate the connection a caller passes in (contract `storage.pyi`), and the drift test must also catch a missing server default or check constraint.

## Interface
```python
# migrations/env.py, online mode:
connection = config.attributes.get("connection")
# if connection is not None: context.configure(connection=connection, target_metadata=..., render_as_batch=True,
#     compare_server_default=True); run migrations in context.begin_transaction(); do NOT close or dispose it.
# else: current behaviour (engine from HABITS_DATABASE_URL or sqlalchemy.url), also compare_server_default=True.
```
Fixture available from `tests/conftest.py`: `alembic_config(url) -> Config`, `migrated_db_url` (sqlite file URL at head).

## Steps
1. Implement the connection branch in `run_migrations_online`.
2. Tests first in `tests/storage/test_migrations.py` (keep existing tests).

## Acceptance criteria
- [ ] cfg URL points to DB A, `cfg.attributes["connection"]` is a connection to DB B: after `upgrade(cfg, "head")` B has `habits`, A does not — `test_upgrade_uses_supplied_connection`
- [ ] drift check runs with `compare_server_default=True` (`MigrationContext.configure(conn, opts={"compare_server_default": True, "compare_type": True})`) and returns `[]` — `test_no_drift`
- [ ] on the migrated DB, inserting frequency "monthly" raises IntegrityError and an insert without `archived` stores False — `test_migrated_constraints`

## Out of scope
- New revisions; repository code.

## Notes from architect
- Do not hard-code the head revision. Dispose engines you create (Windows file locks).

## Log
- 2026-11-21 21:36 created from batch batch-M1-fix.md (by architect)
- 2026-11-21 21:36 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:37 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:38 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:38 status in_review -> approved (by run_review): round 1
