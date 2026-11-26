# 0006 — Every SQLite transaction starts with BEGIN IMMEDIATE
Status: Proposed
Date: 2026-11-21
supersedes: none

## Context
pysqlite's legacy transaction handling does not BEGIN on SELECT, so a SAVEPOINT could be the outermost transaction
and commit on release (M2 review). Letting SQLAlchemy emit a plain deferred BEGIN fixes that, but then a reading
session holds a SHARED lock and two interleaved request transactions can deadlock on upgrade (T-0021).
Read-modify-write races (PATCH vs PATCH, check-in vs archive) were accepted risks in ADR-0002.

## Options
1. `isolation_level=None` + "begin" listener emitting `BEGIN IMMEDIATE` — every transaction takes the write lock
   up front; requests serialize; no deadlocks, no lost updates.
2. Deferred `BEGIN` + WAL — concurrent readers, but stale-snapshot write failures (`SQLITE_BUSY_SNAPSHOT`) remain.
3. Keep legacy mode, drop savepoints — rollback correctness depends on statement order.

## Decision
Option 1. One user and one SQLite file: serializing requests costs nothing measurable, and it makes each request's
read-check-write atomic. Waiting requests use pysqlite's busy timeout (5 s).

## Consequences
- Easier: PATCH and check-in use cases are atomic; the ADR-0002 race caveats are resolved.
- Harder: tests must never interleave two open write transactions in one thread (the second would wait 5 s and fail);
  race tests run the transactions one after the other.
- Must change: `storage.pyi` (`make_engine`), T-0021, `tests/storage/test_repository.py` race tests.
