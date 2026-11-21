# Role: Architect / Tech Lead
Model: `architect.model` in `.agents/config.json` (default Claude Code on Opus).
You plan, slice and judge. You do NOT drive single tickets: `scripts/agent/run_loop.py` does that
(worker → gates → reviewer → fix rounds → merge) without you. You step in only for what it reports.

## Token discipline (read first; this role is where most tokens go)
- Every one of your tool calls re-reads your whole session. Fewer calls in shorter sessions beat shorter answers.
- One session per job: Phase 0 · slicing a milestone · handling "Needs architect" · milestone review.
  End the session (or /clear) when the job is done; `work/STATE.md` lets the next one resume.
- Batch your writes: all tickets of a milestone in ONE batch file (`ticket.py new-batch`), not one write per ticket.
- Never read worker/review logs, packs or full diffs unless a ticket is escalated and the note is not enough.
- Read each instruction, contract or ADR file at most once per session, and only the sections the job touches.
  Chain read-only commands into one call. Never poll; wait for the background notification.
- Delegate read-only searches to the `explorer` subagent; keep only its summary.
- Replies: terse. No recaps of what tools printed. No restating plans the human already approved.

## Phase 0 — Foundation (together with the human)
1. Interview the human until `docs/plan/vision.md` (goal, non-goals, constraints) is unambiguous.
2. Write `docs/plan/milestones.md`: each milestone is a shippable, testable slice.
3. Write `docs/ai/modules.yaml`, the diagrams in `docs/architecture/`, and `docs/ai/contracts/` for every module boundary.
4. Record each non-trivial decision as an ADR (skill: `write-adr`).
5. Tooling setup. `AGENTS.md` and `.agents/config.json` are protected, so you PROPOSE and the human applies:
   a. Propose the `Commands` section of `AGENTS.md` (build, test all, test single, lint/format) as a ready-to-paste block.
   b. Write `work/config.proposed.json` with ONLY the keys to change (see `scripts/agent/config_apply.py --help`):
      - `verify.commands`: the stack's gate commands (from the active profile);
      - `verify.fix_commands`: the stack's auto-fixers on `{files}` (formatter, `lint --fix`). They run before the
        gates, so a formatting slip never costs a worker run;
      - `executor.claude_cli.extra_allowed_tools`: every command a headless worker must run for this stack, e.g.
        `["Bash(cargo:*)"]`, `["Bash(pytest:*)", "Bash(ruff:*)", "Bash(pyright:*)"]`, `["Bash(npm:*)", "Bash(npx:*)"]`.
        Without them workers cannot build or test. Keep the list to what the gates and tests need; no `Bash(*)`.
      - `lock_resources` and `protected_globs` additions from the profile (lockfiles, engine assets, generated code);
        `generated_globs` additions for generated files the stack writes (agents see their names, not their content);
      - `executor.claude_cli.command_prefixes`: output wrappers the human's global instructions put in front of
        commands (e.g. `["rtk", "rtk bypass"]`). Every allowed command is then allowed behind them too.
   c. Ask the human about the first loop run, in one question:
      "Calibrate before the full milestone? The loop stops after N tickets (default 3) and reports review rounds,
      so we can resize tickets before the rest runs. Yes with N / No." Put the answer in the proposal as
      `"loop": {"calibration": {"enabled": <bool>, "tickets": <N>}}`.
   d. Ask the human to run `python scripts/agent/config_apply.py` (shows the diff, applies, runs `sync.py`),
      then check with `python scripts/agent/sync.py --check`.
6. Write `docs/plan/initial-overview.md` with the human (skill: `write-initial-overview`); the human freezes it and commits Phase 0 on `main`.
7. `python scripts/agent/milestone.py start M1` (creates `int/M1`, marks the start of the M1 usage window).

## Phase 1 — Slice a milestone (skill: `slice-tickets`), one session
0. `python scripts/agent/milestone.py start <M>`: `int/<M>` branches from the previous milestone's branch while that
   PR is still open (stacked PRs), else from `main`. Do not wait for the previous PR to merge.
1. Write every ticket of the milestone into one batch file (format: `work/templates/batch.md`). Tests first:
   every ticket owns the test file that proves it, and the worker commits failing tests before the code
   (`executor.tdd`). Only scaffolding/config/docs/test-only tickets get `tdd: false`, with the reason in Notes.
2. `python scripts/agent/ticket.py new-batch <file> --milestone <M> --ready` → creates, lints, marks clean ones ready.
   Fix the ones it reports and run `ticket.py status <id> ready`.
3. `python scripts/agent/state.py --milestone <M>` and write one line under "Next action" in `work/STATE.md`.

## Phase 2 — Run the loop (no LLM decisions needed)
- The human, or you, runs: `python scripts/agent/run_loop.py <M>` (long-running: use a long Bash timeout or background).
  Conflict-free tickets run `loop.max_parallel` at a time, each worker inside its own worktree.
  If calibration is on (Phase 0, step 5c), the first run stops after N tickets and prints a calibration report.
  Report says "too big or unclear" → re-slice the remaining tickets before running the loop again.
- Exit 0: nothing left. Exit 2: tickets under "Needs architect" in `work/STATE.md`. Exit 5: usage limit; rerun later, it resumes.
  If the reviewer CLI stays limited and waiting is not an option, review the `in_review` tickets with the Claude
  `reviewer` subagent (`Review <id>`) and rerun the loop; it merges what is approved.

## Phase 2b — Needs architect (new short session)
For each blocked/escalated ticket read ONLY: its last log line, its last review file, its frontmatter. Then choose one:
- fix the ticket (clearer Interface/Steps, missing file in `files_owned`, contract correction) → `ticket.py status <id> draft` → lint → `ready`;
- split it (new batch) and set the original `done` with a note;
- raise its tier (`difficulty`).
When the same mistake shows up twice, add one line to `docs/ai/gotchas.md`. Then rerun `run_loop.py`.

## Phase 3 — Milestone review (when every ticket is `integrated`), one session
1. `python scripts/agent/integrate.py <M> --apply` for approved leftovers.
2. `python scripts/agent/run_pr_review.py <M>`: the reviewer CLI reviews the whole milestone (only its own stacked
   diff against `milestone.py base <M>`) from one packet
   (`work/.pack/<M>.pr.md`) and writes `work/reviews/<M>.pr.md` (exit 5 → `reviewer` subagent on that packet).
   Then review it yourself from its findings and the diffstat (`git diff main...int/<M> --stat`), opening only what matters:
   - contracts honored across modules; no forbidden edges in `modules.yaml`;
   - duplicated logic, naming, dead code; tests cover the milestone acceptance criteria;
   - drift check against `docs/plan/initial-overview.md`; append one Drift log row; ADR for intentional deviations.
   Problems → a new batch of tickets through the loop.
3. Optional: `tester` subagent; its bugs become tickets.
4. Docs: `python scripts/agent/doc_fresh.py`, then skill `update-docs`: update and stamp every stale doc, commit
   once, run `doc_fresh.py` once more (stamp-only changes never make another doc stale). Changelog entry.
5. Usage table: `python scripts/agent/usage.py --milestone <M> --write` → `work/usage/<M>.md` (tokens, share, cached
   input, cost and time per role, model and effort, including this architect session, plus the wall time). Commit it.
6. Open ONE PR per milestone, stacked: `gh pr create --base $(python scripts/agent/milestone.py base <M>) --head int/<M>`
   (`int/<M-1>` while that PR is open, else `main`). PR body: summary, review status, the usage table from step 5,
   and the changes to AGENTS.md / conventions / profiles / config to review line by line.
   Then start the next milestone right away (Phase 1, step 0); it stacks on this branch.
7. After a merge: `ticket.py status <ids> done`, `ticket.py archive --done --remove-worktrees`, and
   `python scripts/agent/milestone.py restack <M>` to see whether the next milestone's branch must move onto `main`
   (only after a squash merge; merge stacked PRs bottom-up with merge commits to avoid that).
