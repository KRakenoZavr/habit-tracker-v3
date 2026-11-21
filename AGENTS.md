# AGENTS.md
<!--
Human-owned. Agents may PROPOSE edits in a PR, flagged "AGENTS.md change", never rewrite it wholesale.
Hard limit: 150 lines. This is the ONLY file every agent loads on every turn; each line costs tokens forever.
Write only NON-OBVIOUS rules. No architecture tours, no generic advice ("write clean code").
-->

## Critical rules (read first)
1. If you are working on a ticket: edit ONLY files matching its `files_owned`. Need another file? Stop, set status `blocked`, write the reason.
2. Never edit protected paths listed in `.agents/config.json` → `protected_globs`. Hooks and `owned_diff.py` enforce this.
3. "Done" means `python scripts/agent/verify.py <ticket-id>` exits 0. Paste its final summary in your report.
4. Do not read `work/archive/**`, `docs/human/**` or `work/.pack/**` unless your role file tells you to.
5. Find your role in `.agents/roles/` and follow it. No role given → you are `architect`.

## Commands
<!-- Fill in when the stack is chosen. Keep the exact, copy-pasteable form. -->
- Build: `uv sync --frozen` (dependencies are architect-only; never `uv add`/`uv lock`)
- Test (all): `uv run --frozen pytest -q`
- Test (single): `uv run --frozen pytest -q <path>`
- Lint/format: `uv run --frozen ruff format . && uv run --frozen ruff check . && uv run --frozen pyright`
- Migrate / run: `uv run --frozen alembic upgrade head` · `uv run --frozen uvicorn habits.api.app:app`
- Agent gate: `python scripts/agent/verify.py <ticket-id>`

## Where things are
- Task routing for docs: `docs/ai/INDEX.md` — read only the rows matching your task.
- Module map, owners, public APIs: `docs/ai/modules.yaml`. Contracts: `docs/ai/contracts/`.
- Coordination bus: `work/STATE.md` (read first), `work/tickets/`, `work/reviews/`.
- Role prompts: `.agents/roles/`. Procedures: `.agents/skills/*/SKILL.md`.
- Ticket tooling: `python scripts/agent/ticket.py --help`.

## Shell and files (every stack)
- Never create files or folders inside the repo outside your owned paths (no temp/cache dirs); use an absolute temp path.
- Write multi-line files with your file-writing tool, not shell heredocs. On Windows set `PYTHONIOENCODING=utf-8` for scripts.

## Non-obvious conventions
<!-- Only what a competent engineer would get WRONG in this repo. Delete the examples. -->
- `habits.core` is pure: no I/O, no clock; `now`/`today` are parameters. Details: `docs/ai/conventions.md`.
- The HTTP contract is `docs/ai/contracts/openapi.yaml`; code follows it, never the other way round.

## Active stack profiles
<!-- Delete the ones you don't use. Read a profile only when touching that stack. -->
- `.agents/profiles/python.md`
