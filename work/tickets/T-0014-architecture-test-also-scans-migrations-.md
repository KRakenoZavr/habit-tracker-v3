---
id: T-0014
title: Architecture test also scans migrations under storage rules
status: integrated  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: storage  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [tests/test_architecture.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: int/M1  # set by run_executor.py
tdd: false  # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/test_architecture.py -x -q", "uv run --frozen ruff check tests/test_architecture.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
`docs/ai/modules.yaml` assigns `migrations/**` to the storage module, so migration files must obey the storage import rules too (M1 review finding 9).

## Interface
```python
# violations(src_root) keeps its behaviour; add:
def migration_violations(migrations_root: Path) -> list[str]:
    """Every *.py under migrations_root (recursively) checked against FORBIDDEN["habits.storage"].
    Module name for relative-import resolution: "migrations.<relative.dotted.path>"."""
```

## Steps
1. Add `migration_violations` and `test_migrations_have_no_forbidden_imports` (REPO_ROOT / "migrations").
2. Add a helper test on an inline source: a file containing `from habits.api import app` is reported.

## Acceptance criteria
- [ ] the real `migrations/` tree has no violations — `test_migrations_have_no_forbidden_imports`
- [ ] a migration importing `habits.api` is reported — `test_migration_scanner_detects_api_import`

## Out of scope
- Changing the rules for core/storage packages.

## Notes from architect
- tdd: false — test-only ticket.

## Log
- 2026-11-21 21:36 created from batch batch-M1-fix.md (by architect)
- 2026-11-21 21:36 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:40 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:41 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:41 status in_review -> approved (by run_review): round 1
- 2026-11-21 21:41 status approved -> integrated (by integrate): merged into int/M1
