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
- Build: `<cmd>`
- Test (all): `<cmd>`
- Test (single): `<cmd> <path>`
- Lint/format: `<cmd>`
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
- <example: All public functions in src/core are pure; side effects live in src/io.>
- <example: Time is always UTC, passed in as a parameter, never read from the clock inside logic.>

## Active stack profiles
<!-- Delete the ones you don't use. Read a profile only when touching that stack. -->
- `.agents/profiles/python.md`
- `.agents/profiles/rust.md`
- `.agents/profiles/unity.md`
- `.agents/profiles/unreal.md`
- `.agents/profiles/web-design-system.md`
