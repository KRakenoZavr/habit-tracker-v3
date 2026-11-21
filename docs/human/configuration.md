# Configuration: what you can change and how
<!-- Human documentation. Stable; update when config keys change. -->

**One rule:** every model, tier and budget lives in **`.agents/config.json`**. After editing it, run:

```bash
python scripts/agent/sync.py          # applies the config to .claude/ (settings, executor subagents, skills)
python scripts/agent/sync.py --check  # just shows the current setup and whether the reviewer CLI is found
```

`.agents/config.json` is protected: agents cannot edit it (a hook blocks Claude Code; `owned_diff.py` blocks executors).
Agents propose changes in `work/config.proposed.json` (only the keys that change). You review and apply them with:

```bash
python scripts/agent/config_apply.py          # shows the diff, asks y/N, applies, runs sync.py
```

## 1. Models

| What | Key | Default | Notes |
|---|---|---|---|
| Architect (your main session) | `architect.model` | `opus` | `sync.py` writes it to `.claude/settings.json`. Set effort (e.g. high) inside Claude Code. |
| Executor per tier | `executor.tiers.<T>.model` | S/M `sonnet`, L `opus` | Claude runners: `sonnet`, `opus`, `haiku` or a full model id. `aider`: a LiteLLM name, e.g. `ollama_chat/qwen3.5:9b`. |
| Executor tool per tier | `executor.tiers.<T>.runner` | `claude-cli` | `claude-cli` = headless `claude -p`, started by `run_loop.py` (default). `claude-subagent` = the architect spawns `executor-<t>` in its own session (costs architect tokens). `aider` = local or any model via Aider. |
| Worker turn cap | `executor.tiers.<T>.max_turns` | 25 / 35 / 50 | hard stop for a runaway worker |
| Worker effort | `executor.tiers.<T>.effort` | S `medium`, M/L `high` | passed as `claude --effort`; empty = your Claude Code default. Logged in the usage table |
| Worker command | `executor.claude_cli.command` | `claude -p --model {model} --max-turns {max_turns} --output-format json --permission-mode acceptEdits --allowedTools …` | Prompt goes on stdin. Normally you don't edit this. |
| Worker stack tools | `executor.claude_cli.extra_allowed_tools` | `[]` | Commands headless workers may run, appended to `--allowedTools`, e.g. `["Bash(cargo:*)"]`. **The architect proposes these in Phase 0.** |
| Command wrappers | `executor.claude_cli.command_prefixes` | `["rtk", "rtk bypass"]` | for every allowed `Bash(<cmd>:*)` the same command behind each prefix is allowed too (`Bash(rtk uv:*)`), for workers and, via `sync.py`, in `.claude/settings.json`. Never a bare `Bash(rtk:*)` |
| Shell mirrors | `executor.claude_cli.mirror_shells` | `["PowerShell"]` | every allowed `Bash(<cmd>:*)` rule is also allowed as `PowerShell(<cmd>:*)`; Claude Code on Windows often tries PowerShell first |
| Tests first | `executor.tdd.enabled` / `test_globs` / `test_command_patterns` | `true` / common test paths / pytest, unittest, cargo test, npm test, … | the worker commits the tests first and `run_executor.py <id> --red` proves that a TEST command (one matching `test_command_patterns`, or `python <test file>`) fails without the implementation; a failing lint/format check never counts. A ticket opts out with `tdd: false` (reason in Notes) |
| Worker retries on failing gates | `executor.gate_retries` | 2 | then the ticket is set `blocked` |
| Reviewer | `reviewer.command` | `codex exec -m {model} --sandbox read-only -c model_reasoning_effort={effort} --output-last-message {out_file} -` | Packet goes on stdin (`-`). `{model}`: `reviewer.model` for S/M tickets (`gpt-6.2-sol`), `reviewer.hard.model` for L tickets and milestone PRs (`gpt-6.2-astra`). An empty model drops `-m`, so the CLI's own default (`~/.codex/config.toml`) reviews everything. Any CLI that reads stdin and answers works. |

Keep the reviewer a **different model family** from the executors.

## 2. Tiers
A ticket's `difficulty` field names a tier. The architect picks it while slicing.

| Key | Meaning |
|---|---|
| `executor.default_tier` | tier for new tickets (`ticket.py new`) |
| `executor.tiers.<T>.pack_tokens` | max size of the context pack for that tier (`pack.py` refuses bigger) |
| `executor.tiers.<T>.max_files_owned` | max files one ticket may own (`ticket_lint.py`) |

You can rename tiers or add more (e.g. `XS`, `LOCAL`). Run `sync.py` afterwards. To switch a tier to a local model, copy `executor._local_tier_example` over it.

Example: everything on Sonnet except hard tickets on Opus, plus a local tier for boilerplate:
```json
"tiers": {
  "LOCAL": { "runner": "aider",      "model": "ollama_chat/qwen3.5:9b", "pack_tokens": 6000,  "max_files_owned": 3 },
  "S":     { "runner": "claude-cli", "model": "sonnet", "max_turns": 25, "pack_tokens": 24000, "max_files_owned": 5 },
  "L":     { "runner": "claude-cli", "model": "opus",   "max_turns": 50, "pack_tokens": 60000, "max_files_owned": 8 }
}
```

## 2b. Reviewer cost controls (`reviewer`)

| Key | Default | Effect |
|---|---|---|
| `effort.default` | `medium` | Codex reasoning effort for normal reviews |
| `effort.last_round` / `effort.escalated_before` | `high` | stronger review only when it matters |
| `incremental_rereview` | `true` | rounds 2+ get only the changes since the last review + previous findings |
| `max_diff_lines` | 600 | diff is cut above this (the reviewer is told) |
| (top-level) `generated_globs` | lockfiles, `*.min.js`, source maps, snapshots | listed with their changed-line counts, content never sent (the reviewer is told they are part of the change). The older `reviewer.diff_exclude` still works and is merged in |
| `auto_approve.enabled` | `false` | skip the LLM review for tiny diffs (`max_changed_lines`, `tiers`) that passed all gates |
| `limit_patterns` | "usage limit", "429", … | if the CLI fails with one of these, nothing changes and the loop stops (exit 5) |
| `timeout_seconds` | 600 | milestone PR reviews get twice this |
| `model` | `gpt-6.2-sol` | reviewer model for normal (S/M) tickets; empty = CLI default |
| `hard.model` / `hard.effort` | `gpt-6.2-astra` / `high` | stronger model (and optional effort) for `hard.difficulties` tickets (default `["L"]`) and, if `hard.milestone_pr`, the milestone PR review |
| `pr_packet_tokens` | 60000 | cap for the milestone PR packet built by `run_pr_review.py` |

### Keep the architect session lean
The architect session is where most tokens go: every call re-sends the whole conversation plus every tool definition
and skill description loaded in it.
- Disable plugins and MCP servers this project does not use (`enabledPlugins` in `.claude/settings.json`, `/mcp`).
- One architect session per job (see `.agents/roles/architect.md`); `work/STATE.md` is the handoff.

## 2c. Loop (`loop`)

| Key | Default | Effect |
|---|---|---|
| `max_parallel` | 2 | tickets worked on at the same time: only conflict-free ones (no shared `files_owned` or lock resources), each worker in its own worktree. 1 for a single-GPU local tier |
| `integrate_after_approval` | `true` | merge each approved ticket into `int/<M>` immediately, so dependents can start |
| `calibration.enabled` / `calibration.tickets` | `true` / 3 | first run of a milestone stops after N tickets with a sizing report. **The architect asks you in Phase 0.** `--no-calibration` skips it once. |

## 3. Budgets (`budgets`)

| Key | Default | Effect |
|---|---|---|
| `ticket_body_max_tokens` | 1500 | lint warning above this |
| `max_steps` | 7 | lint warning above this many Steps |
| `max_review_rounds` | 3 | reviews per ticket before escalation is forced |
| `verify_tail_lines` | 40 | lines of failing output fed back to agents |
| `chars_per_token` | 3.5 | token estimate used by all scripts |

A single ticket can override its tier: `context_budget_tokens: 30000` or `max_review_rounds: 5` in its frontmatter.

## 4. Gates, protected and lock paths

| Key | What to put there |
|---|---|
| `verify.commands` | build / lint / test commands run for every ticket and after every merge (see your stack profile) |
| `verify.fix_commands` | auto-fixers run in the ticket worktree before the gates, e.g. `["uv run --frozen ruff format {files}", "uv run --frozen ruff check --fix-only {files}"]`; `{files}` = the ticket's changed, owned, non-generated files |
| `generated_globs` | lock files and other generated files: agents see their names, never their content (packs, review packets, the Read hook). Change them with their tool |
| `protected_globs` | files no agent may edit (add engine files: `**/*.unity`, `**/*.uasset`, generated code) |
| `lock_resources` | files two parallel tickets must never both touch (`Cargo.lock`, `pyproject.toml`, `migrations/**`, scenes) |
| `read_guard` | huge files Claude Code may only read in slices (Unity scenes and similar) |

## 5. Git

| Key | Default | Notes |
|---|---|---|
| `git.worktree_dir` | `.worktrees` | each ticket is a real `git worktree` checked out at `.worktrees/<id>/` (gitignored); git keeps its metadata in `.git/worktrees/` |
| `git.integration_branch_prefix` | `int/` | one integration branch and one PR per milestone, stacked: `int/M2` starts from `int/M1` while M1's PR is open (`milestone.py start/base`) |
| `git.ticket_branch_prefix` | `t/` | one branch per ticket |
| `git.default_base` | `main` | |

## 6. Text files you may edit by hand
| File | When |
|---|---|
| `AGENTS.md` | rules every agent loads every turn. Keep ≤150 lines and only non-obvious rules |
| `.agents/roles/*.md` | change how a role behaves (`executor-local.md` is the executor's rule block in every pack) |
| `.agents/skills/*/SKILL.md` | change a procedure; run `sync.py` |
| `.agents/profiles/*.md` | stack-specific rules |
| `.claude/agents/executor-*.md` | **don't**: they are generated; edit the config and run `sync.py` |
