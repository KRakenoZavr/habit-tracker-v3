---
name: write-adr
description: Record an architecture decision as a short ADR in docs/adr. Use when choosing between technologies, changing a module boundary or contract, or reversing an earlier decision.
---

# Write an ADR

1. Next number: highest `docs/adr/NNNN-*.md` + 1. File name: `NNNN-kebab-title.md`.
2. Copy `docs/adr/0000-template.md`. Keep the whole ADR under ~40 lines.
3. Context: ≤5 lines of forces and constraints. Options: 2–4, one line of trade-offs each. Decision: one paragraph.
4. Consequences: what becomes easier, what becomes harder, what must change (contracts, modules.yaml, tickets).
5. If it replaces an earlier ADR: set `supersedes:` here and `Status: Superseded by NNNN` there.
6. Status starts as `Proposed`. The human sets `Accepted` during PR review.
