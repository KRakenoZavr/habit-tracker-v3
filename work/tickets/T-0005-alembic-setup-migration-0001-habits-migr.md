---
id: T-0005
title: Alembic setup, migration 0001 habits, migrated DB fixture and drift test
status: integrated  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: storage  # from docs/ai/modules.yaml
depends_on: [T-0004]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [alembic.ini, migrations/env.py, migrations/script.py.mako, migrations/versions/0001_create_habits.py, tests/conftest.py, tests/storage/test_migrations.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: [migrations/**, alembic.ini, tests/conftest.py]  # lock files this ticket must touch (see .agents/config.json)
difficulty: M  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: int/M1  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/storage/test_migrations.py -x -q", "uv run --frozen ruff check migrations tests/conftest.py tests/storage", "uv run --frozen pyright migrations tests/conftest.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Explicit, linear Alembic migrations for SQLite whose result equals the ORM schema, and a shared pytest fixture that gives storage/API tests a migrated DB file (ADR-0003).

## Interface
```python
# alembic.ini (repo root): [alembic] script_location = %(here)s/migrations ; sqlalchemy.url = sqlite:///./habits.db
#   plus the standard [loggers]/[handlers]/[formatters] sections.
# migrations/env.py: url = os.environ.get("HABITS_DATABASE_URL") or config.get_main_option("sqlalchemy.url");
#   target_metadata = habits.storage.models.Base.metadata; context.configure(..., render_as_batch=True);
#   offline and online modes; fileConfig(config.config_file_name, disable_existing_loggers=False) if set.
# migrations/versions/0001_create_habits.py: revision = "0001", down_revision = None; upgrade() creates
#   table "habits" exactly like HabitRow (below); downgrade() drops it.
# tests/conftest.py
REPO_ROOT: Path   # parent of tests/
def alembic_config(url: str) -> Config: ...          # Config(str(REPO_ROOT / "alembic.ini")) with sqlalchemy.url = url
@pytest.fixture
def migrated_db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """sqlite:///<tmp_path>/test.db (as_posix) upgraded to "head"; sets HABITS_DATABASE_URL to it."""
```
HabitRow (already exists in `habits.storage.models`): habits(id Integer PK autoincrement, name String(100) not null,
description String(500) null, frequency String(10) not null with CheckConstraint "frequency IN ('daily','weekly')"
name "ck_habits_frequency", target_per_week Integer null, archived Boolean not null server_default sa.false(),
created_at DateTime not null).

## Steps
1. `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako` (standard template).
2. `0001_create_habits.py` with `op.create_table` matching HabitRow column for column.
3. `tests/conftest.py`: `alembic_config` and `migrated_db_url` (`alembic.command.upgrade(cfg, "head")`).
4. Tests first in `tests/storage/test_migrations.py`.

## Acceptance criteria
- [ ] after upgrade, `alembic_version` equals `ScriptDirectory.from_config(cfg).get_current_head()` and table `habits` exists — `test_upgrade_head`
- [ ] drift: `compare_metadata(MigrationContext.configure(conn), Base.metadata) == []` on the upgraded DB — `test_no_drift`
- [ ] `downgrade(cfg, "base")` removes `habits` — `test_downgrade_base`
- [ ] the real entry point works: `uv run --frozen alembic -x dummy=1 heads` exits 0 (run it once; a test may call `subprocess` with `sys.executable -m alembic heads`) — `test_cli_heads`

## Out of scope
- `checkins` table (M2 adds migration 0002); repository code.

## Notes from architect
- Do not hard-code "0001" in tests as the head: M2 adds 0002 and these tests must stay green.
- Dispose every engine you create (`engine.dispose()`), or Windows keeps the tmp DB file locked.
- Never use autogenerate output blindly; the drift test is the judge.

## Log
- 2026-11-21 21:13 created from batch batch-M1.md (by architect)
- 2026-11-21 21:13 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:20 status ready -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 21:21 status in_progress -> blocked (by executor): BLOCKED: verify cannot pass here because the pytest temp root `C:\Users\KRaken\AppData\Local\Temp\pytest-of-KRaken` is not accessible.
- 2026-11-21 21:25 status blocked -> draft (by architect): blocked by inaccessible system pytest temp root; fixed with --basetemp=.pytest_tmp on int/M1
- 2026-11-21 21:25 status draft -> ready (by architect)
- 2026-11-21 21:25 status ready -> in_progress (by architect)
- 2026-11-21 21:26 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:26 status in_review -> approved (by run_review): round 1
- 2026-11-21 21:26 status approved -> integrated (by integrate): merged into int/M1
