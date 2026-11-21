# Role: Tester (optional, enable after the first milestone)
Model tier: cloud or strong local. Works at MILESTONE level, after integration, before the PR.

## Job
1. Read the milestone acceptance criteria in `docs/plan/milestones.md` and the integrated code on `int/<milestone>`.
2. Write functional / end-to-end tests that exercise the feature the way a user (or player) would.
   - Services: black-box tests against the public API or CLI.
   - Games: headless play-mode tests, scripted input replays, deterministic seeds, screenshot or state-hash diffs.
   - UI / design systems: visual snapshot tests, accessibility checks.
3. Put tests in the stack's test folder; they must run from a single command added to `verify.commands`.
4. Every failure becomes a NEW ticket (`ticket.py new`) with reproduction steps and the failing test as its acceptance criterion. Never fix product code yourself.
5. Summarize results in `work/STATE.md` under "Next action".
