---
covers: [docs/ai/**, docs/architecture/**]
verified_at: cc7dbb2
owner: architect
---
# AI doc index — read ONLY the rows that match your task

| If your task touches… | Read | Budget |
|---|---|---|
| module boundaries, imports, ownership | `docs/ai/modules.yaml` (your module + its direct deps only) | ≤500 tok |
| a public API / IPC / file format | `docs/ai/contracts/<module>.*` (only the relevant part) | ≤1.5k tok |
| persistence / data model | `docs/architecture/data-model.mmd` | ≤600 tok |
| a multi-step flow between components | `docs/architecture/sequences/<flow>.mmd` | ≤500 tok |
| anything with modes or lifecycle | `docs/architecture/states/<system>.mmd` | ≤400 tok |
| gameplay loop / tick order | `docs/architecture/game/loop.mmd` | ≤400 tok |
| ECS components and systems | `docs/architecture/game/ecs.yaml` (relevant systems) | ≤600 tok |
| naming, error handling, logging | `docs/ai/conventions.md` | ≤600 tok |
| unfamiliar domain words | `docs/ai/glossary.md` | ≤300 tok |
| any code change | `docs/ai/gotchas.md` (section for your module) | ≤400 tok |
| why something is designed this way | `docs/adr/` (titles first, open one) | ≤800 tok |

Rules
- Executors normally need nothing from here: the pack already inlines what the ticket lists in `files_read`.
- Every doc here carries frontmatter (`covers`, `verified_at`, `owner`); `scripts/agent/doc_fresh.py` flags stale ones.
- Mermaid files carry the same fields as `%% covers: [...]` / `%% verified_at: <sha>` comment lines.
