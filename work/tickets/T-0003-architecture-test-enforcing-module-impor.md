---
id: T-0003
title: Architecture test enforcing module import boundaries
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: core  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [tests/test_architecture.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 2
base: int/M1  # set by run_executor.py
tdd: false  # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/test_architecture.py -x -q", "uv run --frozen ruff check tests/test_architecture.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
A test that fails when a module imports across a forbidden edge from `docs/ai/modules.yaml` (ADR-0002).

## Interface
```python
# tests/test_architecture.py
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "habits.core": ("habits.storage", "habits.api", "sqlalchemy", "fastapi", "pydantic", "alembic", "starlette"),
    "habits.storage": ("habits.api", "fastapi", "pydantic", "starlette"),
}
def imported_modules(source: str, module: str) -> set[str]:
    """Absolute dotted names imported by `source` (Import and ImportFrom). Relative imports are resolved
    against `module` (the dotted name of the file, e.g. "habits.core.rules")."""
def violations(src_root: Path) -> list[str]:
    """One "<file>: <imported>" string per forbidden import in src_root/habits/{core,storage}/**/*.py.
    A name is forbidden when it equals a FORBIDDEN prefix or starts with prefix + "."."""
```

## Steps
1. Implement both helpers with `ast` (no imports of the code under test).
2. `test_no_forbidden_imports`: `violations(REPO_ROOT / "src") == []` (REPO_ROOT = parent of `tests/`).
3. Unit tests of the helpers on inline source strings: absolute import, `from x import y`, relative `from ..storage import a` resolved from `habits.core.rules` to `habits.storage`, and `sqlalchemy.orm` matches prefix `sqlalchemy` while `sqlalchemyx` does not.

## Acceptance criteria
- [ ] relative imports resolved — `test_imported_modules_relative`
- [ ] prefix match is dotted, not textual — `test_prefix_match`
- [ ] the real tree has no violations — `test_no_forbidden_imports`

## Out of scope
- Checking `habits.api` (it may import everything) and `migrations/`.

## Notes from architect
- tdd: false because this ticket is test-only; the tree is (almost) empty when it runs, the helper tests carry it.
- Missing directories (storage may not exist yet) must not fail the test.

## Log
- 2026-11-21 21:13 created from batch batch-M1.md (by architect)
- 2026-11-21 21:13 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:13 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:14 status in_progress -> blocked (by run_loop): gates still failing after 3 worker runs
- 2026-11-21 21:17 status blocked -> in_progress (by architect): gate failure was global (ruff linted docs/*.pyi); fixed on int/M1 and merged
- 2026-11-21 21:17 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:18 status in_review -> changes_requested (by run_review): round 1
- 2026-11-21 21:18 status changes_requested -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:18 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:18 status in_review -> changes_requested (by run_review): round 2
- 2026-11-21 21:18 status changes_requested -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:19 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:19 status in_review -> approved (by run_review): round 3
