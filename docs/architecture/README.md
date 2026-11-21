---
covers: [docs/architecture/**]
verified_at: none
owner: architect
---
# Diagrams — single source for both doc sets

Mermaid (`.mmd`) renders natively in GitHub/GitLab PR views and is compact for agents.
Anything a script must validate (module graph, ECS tables) is YAML, not a diagram.

| File | Required? | What it answers |
|---|---|---|
| `c4-context.mmd` | always | Who/what talks to the system |
| `c4-container.mmd` | always | Deployable/runtime parts and how they talk (derived from `docs/ai/modules.yaml`) |
| `dataflow.mmd` | when data moves through stages | Where data comes from, how it is transformed, where it ends |
| `data-model.mmd` | when anything is persisted | Entities, fields, relations (`erDiagram`) |
| `sequences/<flow>.mmd` | non-trivial flows only | Order of calls/messages in one flow |
| `states/<system>.mmd` | anything with modes | Allowed states and transitions (`stateDiagram-v2`) |
| `game/loop.mmd` | games | Frame/tick order: input → simulation → render, fixed vs variable step |
| `game/scene-graph.md` | games | Scene/prefab composition as an indented outline |
| `game/ecs.yaml` | ECS games (Bevy, DOTS) | Components, systems, their reads/writes and ordering |
| `game/input-map.md` | games | Device input → action → handler |

Keep each diagram under ~40 lines. Split by flow or subsystem instead of growing one diagram.
Every file starts with `%% covers: [...]` and `%% verified_at: <sha>` lines (YAML files use `#`).
