---
id: T-0021
title: Real SQLite transactions and correct check-in conflict mapping
status: ready  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M2
module: storage  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/storage/db.py, src/habits/storage/repository.py, tests/storage/test_transactions.py, tests/storage/test_repository.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: M  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: int/M2  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/storage -x -q", "uv run --frozen ruff check src/habits/storage tests/storage", "uv run --frozen pyright src/habits/storage tests/storage/test_transactions.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Fix M2 review blockers 1 and 2: (1) with pysqlite's legacy transaction handling a SAVEPOINT can be the outermost
transaction, so `begin_nested()` in `add_checkin` commits the insert even if the caller rolls back;
(2) a foreign-key violation (habit deleted meanwhile) is reported as `CheckInExists` instead of `HabitNotFound`.

## Interface
```python
# db.py — SQLAlchemy's documented pysqlite recipe, only for sqlite engines (keep check_same_thread and PRAGMA):
@event.listens_for(engine, "connect")
def _on_connect(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None          # stop pysqlite's own BEGIN handling
    # existing: PRAGMA foreign_keys=ON
@event.listens_for(engine, "begin")
def _on_begin(conn):
    conn.exec_driver_sql("BEGIN IMMEDIATE")          # ADR-0006: SQLAlchemy owns BEGIN; write lock taken up front
# repository.py add_checkin, on IntegrityError from the savepoint:
#   if self.get_habit(habit_id) is None: raise HabitNotFound(f"habit {habit_id} not found")
#   else: raise CheckInExists(message)
```
`HabitNotFound`, `CheckInExists` are in `habits.core`.

## Steps
1. Update `make_engine` with both listeners (type the callbacks: `Any` params, `-> None`).
2. Map IntegrityError as above in `add_checkin`.
3. Tests first in `tests/storage/test_transactions.py` on the `migrated_db_url` fixture (file DB, two sessions from one factory, dispose engine at the end).

## Acceptance criteria
- [ ] session A creates and commits a habit; session B adds a check-in then rolls back; session C sees no check-in — `test_checkin_rolled_back_with_caller`
- [ ] PRAGMA foreign_keys is still 1 and a plain commit still persists — `test_engine_still_enforces_fk_and_commits`
- [ ] repository B passes `get_habit` check, habit is deleted+committed by A, then B's `add_checkin` → HabitNotFound (simulate by deleting via A before calling B's add, with B's existence SELECT skipped: call `add_checkin` directly) — `test_checkin_for_deleted_habit_is_not_found`
- [ ] duplicate day still → CheckInExists — `test_duplicate_still_conflicts`
- [ ] all existing storage tests pass, including the drift test — `uv run --frozen pytest tests/storage -x -q`

## Out of scope
- Archive-vs-check-in race (accepted, ADR-0002). Migrations.

## Notes from architect
- Architect decision on your BLOCKED report (ADR-0006): use `BEGIN IMMEDIATE`, not plain BEGIN, and no WAL.
  You now own `tests/storage/test_repository.py`: rewrite `test_racing_deletes` and `test_update_vanished_row` so the
  two sessions' transactions run one after the other (A deletes + commits, THEN B acts in a fresh transaction).
  Never keep two write transactions open at once in one thread: the second waits 5 s and fails.
- Extra criterion: two sessions, A begins (any SELECT) and stays open; B's first statement must fail with
  OperationalError "database is locked" after a short timeout — build that engine with
  `create_engine(url, connect_args={"timeout": 0.2, "check_same_thread": False})` plus the same listeners, or skip
  this check if it needs a second factory API; do not change `make_engine`'s signature.
- SQLite allows one writer: in two-session tests commit or roll back A before B writes, or B waits on the lock.

## Log
- 2026-11-21 21:59 created from batch batch-M2-fix.md (by architect)
- 2026-11-21 21:59 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:59 status ready -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 22:01 status in_progress -> blocked (by executor): Interface recipe (isolation_level=None + explicit BEGIN) makes B's get_habit SELECT hold a real read transaction, so A's commit of a delete fails with 'database is locked' in existing tests/storage/test_repository.py::test_racing_deletes and ::test_update_vanished_row (not in files_owned). Fix needs either those tests to end B's read txn (rollback) before A commits, or WAL journal mode (PRAGMA journal_mode=WAL in db.py connect listener) - architect decision. New tests in test_transactions.py pass; impl in db.py/repository.py is done.
- 2026-11-21 22:04 status blocked -> draft (by architect): ADR-0006: BEGIN IMMEDIATE; owns test_repository.py now
- 2026-11-21 22:04 status draft -> ready (by architect)
- 2026-11-21 22:04 status ready -> blocked (by run_executor): rebase onto int/M2 failed; architect must resolve
- 2026-11-21 22:05 status blocked -> draft (by architect): committed previous worker WIP and rebased onto int/M2
- 2026-11-21 22:05 status draft -> ready (by architect)
