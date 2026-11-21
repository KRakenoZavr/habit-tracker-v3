---
name: write-initial-overview
description: Write the frozen Phase 0 snapshot docs/plan/initial-overview.md with the human once vision, milestones, modules, contracts and first ADRs exist. Use at the end of Phase 0, or when the human asks to record the project's starting picture.
---

# Write the initial overview (Phase 0 snapshot)

## Preconditions
`docs/plan/vision.md`, `docs/plan/milestones.md`, `docs/ai/modules.yaml`, `docs/architecture/c4-container.mmd`
and the first ADRs exist. If any is missing, finish Phase 0 first.

## Procedure
1. Fill `docs/plan/initial-overview.md` from those sources. Keep it to 1–2 screens.
   Summarize and link; never copy contracts or long tables.
2. Copy the current container diagram into section 5 so the snapshot still shows the original shape after the diagram evolves.
3. Section 8 (risks): list every unknown that could change the architecture. For each, plan a spike ticket in M1 or say "accept".
4. Read the whole file to the human and ask exactly: "Is this the project we are building? What is wrong or missing?"
   Apply their corrections. Repeat until they say it is right.
5. Ask the human to set `status: frozen`, `date:` and, after the Phase 0 commit on `main`, `frozen_at: <sha>`.
6. From then on: never edit sections 1–9. At each milestone end append one Drift log row (skill `update-docs` reminds you).
7. A real pivot (different product, stack or architecture) gets an ADR. If the human wants a new baseline, copy the
   file to `docs/plan/initial-overview.v1.md` (frozen history) and write a fresh one. Do not rewrite the old one.
