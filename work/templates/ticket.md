---
id: T-0000
title: <imperative title>
status: draft            # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M1
module: core             # from docs/ai/modules.yaml
depends_on: []           # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: []          # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []           # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S            # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: none               # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: []               # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
<1–3 sentences: what changes and why.>

## Interface
<Exact signatures / types / message shapes, copied verbatim. Never "see file X".>

## Steps
1. <imperative, ≤7 steps>

## Acceptance criteria
- [ ] <criterion> — proven by `<test name or command>`

## Out of scope
- <what NOT to do>

## Notes from architect
- <gotchas for THIS ticket only>

## Log
<!-- Appended by scripts: status changes, BLOCKED reasons. -->
