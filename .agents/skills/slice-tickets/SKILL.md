---
name: slice-tickets
description: Split a milestone into small, self-contained tickets that the tier executor (Sonnet subagent or a local model) can execute from its pack alone. Use when the architect starts a milestone or re-slices a blocked/escalated ticket.
---

# Slice a milestone into tickets

## Inputs
`docs/plan/milestones.md` (the milestone section), `docs/ai/modules.yaml`, relevant `docs/ai/contracts/*`, `work/STATE.md`.

## Procedure
1. List the deliverables of the milestone. For each, name the module it lives in (from `modules.yaml`).
2. Order work contracts-first: interface/stub tickets → implementation tickets → integration/wiring tickets.
   Tests first (`executor.tdd`): there are no separate "write the tests later" tickets. Each ticket owns the test file
   that proves its acceptance criteria; the worker commits those tests failing (`run_executor.py <id> --red`) before
   writing code. `tdd: false` (reason in Notes) only for scaffolding, config, docs or test-only tickets.
3. Write ALL tickets of the milestone into ONE batch file (format and example: `work/templates/batch.md`,
   `depends_on: ["@1"]` refers to the first ticket of the batch). Per ticket:
   - `files_owned`: exact paths, within the tier's `max_files_owned`. Implementation + its test file is the usual pair
     (required for TDD tickets). Lock/generated files (`generated_globs`) reach the worker by name only: if a ticket
     must change one, a Step names the command that regenerates it.
   - `files_read`: only contracts/stubs the executor must see. They are inlined into the pack.
   - `lock_resources`: any file from `.agents/config.json → lock_resources` the ticket must touch.
   - `difficulty`: a tier from `.agents/config.json → executor.tiers` (default S/M on Sonnet, L on Opus). When unsure, choose the higher tier.
   - `verify`: commands that prove the acceptance criteria; prefer single-test-file commands (fast feedback). For a
     TDD ticket at least one of them must FAIL before the implementation exists (that is the red check).
   - Body: Goal ≤3 sentences; Interface copied verbatim (never "see file X"); ≤7 imperative Steps;
     Acceptance criteria each naming a test or command; Out of scope; ticket-specific gotchas.
4. Self-check each ticket with the "fresh junior" test: could someone with ONLY this file and the listed contracts finish it? If not, inline the missing fact or split.
   Then the pre-dispatch checks. Each one prevents a blocked ticket, a worker re-run and an architect session:
   - **Against the source, not memory:** open the contract and ADR text the ticket relies on. The Interface is copied
     from it verbatim, and no Step or acceptance criterion contradicts it (error codes, nullability, ordering, limits).
   - **Every implementer is owned:** when a ticket adds or changes a method on an interface/Protocol/trait/abstract
     class, grep for ALL implementers, test doubles and fakes included (`grep -rn "<Interface>" src tests`), and
     put them in `files_owned` or in an earlier ticket.
   - **Every caller is owned:** a changed signature or error type → every call site is in `files_owned` or another ticket.
   - **Schema/lock files:** a schema change ships its migration in the same ticket; lock resources are listed.
   - **Later tickets keep it green:** every test must still pass after each LATER ticket of the batch lands. Never
     assert an exact set or count of things later tickets add (e.g. "the unimplemented operations are exactly {...}");
     assert a subset, a lower bound, or only what this ticket adds. Walk the batch in order once and check this.
   - **Count from the source:** numbers in Steps and criteria (operations, fields, error codes) are counted in the
     contract file, never from memory.
   - **Real launch and concurrency:** if the ticket touches startup, settings, logging or a write path, one criterion
     proves it through the real entry point, and one names the race it must survive (unique constraint, transaction).
5. Create them in one call: `python scripts/agent/ticket.py new-batch <file> --milestone <M> --ready`
   (lints every ticket and sets the clean ones ready). Fix the reported ones and set them ready.
6. `python scripts/agent/state.py --milestone <M>`. Then the loop runs: `python scripts/agent/run_loop.py <M>`.

## Sizing heuristics
- One ticket ≈ one function/class/component plus its tests, or one bug fix.
- A diff that will exceed ~200 changed lines is too big for the S tier.
- Generated or engine-owned files (scenes, prefabs, .uasset) are never in `files_owned` for S/M tickets.
