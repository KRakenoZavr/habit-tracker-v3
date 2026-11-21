---
name: update-docs
description: Refresh AI docs and regenerate human docs after a milestone is integrated, using doc_fresh.py to find stale files. Use at milestone end, before opening the PR.
---

# Update docs (one fact, one home)

## Rules
- Facts live in exactly one place: contracts and module graph in `docs/ai/`, diagrams in `docs/architecture/`, decisions in `docs/adr/`.
- `docs/human/*` is narrative that links to or embeds those sources. Never copy a contract or a table into human docs.
- Executors never edit docs. Only the architect runs this skill.

## Procedure
1. `python scripts/agent/doc_fresh.py` → list of stale docs (their `covers:` paths changed since `verified_at:`).
2. For each stale AI doc / diagram: read the diff of the covered paths (`git diff <verified_at>..HEAD -- <paths>`), update the doc, then set `verified_at:` to the current commit (`python scripts/agent/doc_fresh.py --stamp <file>`).
3. `docs/ai/gotchas.md`: add repeated review findings from this milestone; delete entries that no longer apply. Keep it under ~60 lines.
4. Human docs, in this order:
   - `docs/human/changelog.md`: one entry per milestone, generated from `done`/`approved` ticket titles plus ADRs added.
   - `docs/human/architecture.md`: narrative over the Mermaid diagrams (embed them with links), why the design looks like this, link the ADRs.
   - `docs/human/overview.md` and `docs/human/how-to-run.md`: only if behavior or commands changed.
5. Write for a human who has not read any ticket: short paragraphs, the "why" first, diagrams over prose.
6. Append one row to the Drift log in `docs/plan/initial-overview.md` (deviation + ADR link, or "none").
   Never edit its other sections: it is the frozen Phase 0 baseline.
7. Commit, then run `python scripts/agent/doc_fresh.py` once more; it must report nothing stale. A doc changed only
   by a `verified_at:` stamp never makes the docs covering it stale, so there is no stamp-commit-stamp loop.
