---
id: T-0010
title: Repository - atomic delete, vanished-row update, out-of-range ids
status: ready  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: storage  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/storage/repository.py, tests/storage/test_repository.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: none               # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/storage/test_repository.py -x -q", "uv run --frozen ruff check src/habits/storage tests/storage", "uv run --frozen pyright src/habits/storage tests/storage/test_repository.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Fix three M1 review blockers in `SqlHabitRepository`: racing deletes both succeed, an update of a vanished row raises `LookupError` (500), and ids beyond SQLite's int64 crash on bind (500).

## Interface
```python
INT64_MIN = -(2**63); INT64_MAX = 2**63 - 1
def _in_range(habit_id: int) -> bool: ...   # INT64_MIN <= habit_id <= INT64_MAX
# get_habit: out of range -> None (no SQL)
# delete_habit: out of range -> False; else ONE statement
#   result = session.execute(sa.delete(HabitRow).where(HabitRow.id == habit_id)); return result.rowcount == 1
# update_habit: out of range or row missing -> raise habits.core.HabitNotFound(f"habit {habit.id} not found")
```

## Steps
1. Add the range guard and use it in `get_habit`, `update_habit`, `delete_habit`.
2. Replace the `LookupError` in `update_habit` with `HabitNotFound`.
3. Replace the get-then-delete in `delete_habit` with a single DELETE statement + rowcount.
4. Tests first; for races use two sessions from the same factory on the `migrated_db_url` file DB.

## Acceptance criteria
- [ ] two sessions both delete the same habit (first commits, then second runs): results True and False — `test_racing_deletes`
- [ ] session B updates a habit that session A deleted and committed → HabitNotFound — `test_update_vanished_row`
- [ ] ids 2**63 and -(2**63)-1: get → None, delete → False, update → HabitNotFound; 2**63-1 → None (valid, missing) — `test_out_of_range_ids`
- [ ] existing tests in the file still pass — `uv run --frozen pytest tests/storage/test_repository.py -x -q`

## Out of scope
- Check-in methods (M2), services, API.

## Log
- 2026-11-21 21:36 created from batch batch-M1-fix.md (by architect)
- 2026-11-21 21:36 status draft -> ready (by architect): batch lint clean
