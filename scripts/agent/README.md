# scripts/agent — deterministic helpers (Python ≥3.10, stdlib only)

Run any of them with `--help`. They work from the main checkout or from a ticket worktree
(tickets are always read/written in the main checkout, the "control root").
To make another checkout the control root (e.g. the architect runs in a Claude Code worktree), create an empty
`.agent-control-root` file in it (gitignored) or set `AGENT_CONTROL_ROOT=<path>`.

| Script | Used by | Does |
|---|---|---|
| `run_loop.py` | you / architect | **the loop**: worker → gates → review → fix → merge for every runnable ticket; architect only for what it reports |
| `ticket.py` | all | `new`, `new-batch` (many tickets from one file), `status` (state machine + round limit), `list`, `archive --done` |
| `state.py` | loop, architect | regenerates the automatic part of `work/STATE.md` |
| `usage.py` | you, architect | tokens, cached input, cost and time per role/model/effort; `--milestone <M> --write` adds the architect's Claude Code session and saves `work/usage/<M>.md` |
| `milestone.py` | architect | `start <M>` (stacked `int/<M>` from the previous milestone branch, usage window start), `base <M>` (PR base), `restack <M>` |
| `ticket_lint.py` | architect | schema, owned-file limit, protected/lock paths, test file for TDD tickets, verify present, deps/cycles, budget |
| `conflicts.py` | architect | parallel-safe batches of ready tickets |
| `pack.py` | executor, reviewer | builds the context pack (`--review` for the reviewer packet), enforces the budget |
| `run_executor.py` | loop | worktree + pack; runs the tier's worker (`claude -p` started inside the worktree, or Aider); `--red` = commit the tests first and prove they fail; `--finish` = auto-fix (formatters) + commit + gates → `in_review` |
| `verify.py` | all | runs ticket + global gate commands, records results for the next pack |
| `owned_diff.py` | gates | fails on changes outside `files_owned` or in protected paths |
| `integrate.py` | architect | squash-merges approved tickets into `int/<M>` in dependency order |
| `doc_fresh.py` | architect | lists docs whose `covers:` paths changed since `verified_at:`; `--stamp` |
| `run_review.py` | loop | reviewer CLI (Codex) read-only, packet on stdin, incremental re-reviews; exit 0/3/4/5 = approved/changes/escalated/limit |
| `run_pr_review.py` | architect | milestone PR review of the stacked diff (`milestone.py base <M>`...`int/<M>`) from one packet (`work/.pack/<M>.pr.md`), read-only → `work/reviews/<M>.pr.md` |
| `config_apply.py` | you | applies the architect's `work/config.proposed.json` to the protected config (diff, confirm, sync) |
| `sync.py` | you, after config edits | writes `.claude/settings.json` model and the `rtk`-style prefixed allow entries, generates `executor-<tier>` subagents, copies skills |
| `hooks/guard_paths.py` | Claude Code hook | blocks protected edits, off-ticket edits (`AGENT_TICKET`), any Read of lock/generated files (`generated_globs`), whole reads of huge files (`read_guard`) |

Frontmatter in tickets uses a restricted YAML subset: `key: value` lines and inline lists
(`[a, "b c"]`). Don't use nested YAML blocks in tickets.
