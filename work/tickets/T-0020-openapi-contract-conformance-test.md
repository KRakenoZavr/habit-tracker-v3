---
id: T-0020
title: OpenAPI contract conformance test
status: integrated  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M2
module: api  # from docs/ai/modules.yaml
depends_on: [T-0019]  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [tests/api/test_contract.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: [docs/ai/contracts/openapi.yaml]  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: S  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 0
base: int/M2  # set by run_executor.py
tdd: false  # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/api/test_contract.py -x -q", "uv run --frozen ruff check tests/api/test_contract.py", "uv run --frozen pyright tests/api/test_contract.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Prove the running app matches the hand-written contract `docs/ai/contracts/openapi.yaml` (ADR-0004).

## Interface
```python
CONTRACT: dict  # yaml.safe_load of REPO_ROOT / "docs/ai/contracts/openapi.yaml"; REPO_ROOT = parents[2] of this file
def ref_name(schema: dict) -> str | None:
    """Component name of a $ref (last path part); looks inside "items" (arrays) and "anyOf" (optional bodies)."""
# app = create_app(Settings(database_url="sqlite://")).openapi()   (no DB access needed)
```

## Steps
1. Parametrize over every (path, method) in the contract (skip the path-level "parameters" key).
2. For each: the path + method exist in the app; every contract status code is in the app's responses.
3. For each 2xx with JSON content in the contract: `ref_name` of the app's schema == the contract's.
4. For each requestBody in the contract: `ref_name` of the app's request schema == the contract's.
5. Every component the contract references for responses/bodies exists in the app's `components.schemas`.

## Acceptance criteria
- [ ] all contract operations present with their status codes — `test_operation_exists`, `test_status_codes`
- [ ] response and request schema names match — `test_response_schema_names`, `test_request_schema_names`

## Out of scope
- Comparing field-level JSON schemas (FastAPI and the YAML differ in shape there).

## Notes from architect
- Review r1 (escalated, resolved): the app DOES publish `Error` in `components.schemas` and references it from every 404/409/422 (architect verified with `create_app(...).openapi()`). Remove `names.discard("Error")`; `Error` must be part of the component-membership assertion. Also assert 4xx responses reference `Error`.
- tdd: false: test-only ticket over code that already exists.
- The app may declare MORE status codes than the contract (FastAPI adds 422); check contract ⊆ app.
- Do not edit the contract; if it and the app disagree, set the ticket blocked with the difference.

## Log
- 2026-11-21 21:42 created from batch batch-M2.md (by architect)
- 2026-11-21 21:42 status draft -> ready (by architect): batch lint clean
- 2026-11-21 21:53 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:54 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:54 status in_review -> escalated (by run_review): round 1
- 2026-11-21 21:55 status escalated -> draft (by architect): Error is published; remove discard
- 2026-11-21 21:55 status draft -> ready (by architect)
- 2026-11-21 21:55 status ready -> in_progress (by run_executor): tier S, claude-cli sonnet
- 2026-11-21 21:55 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:55 status in_review -> approved (by run_review): round 1
- 2026-11-21 21:56 status approved -> integrated (by integrate): merged into int/M2
