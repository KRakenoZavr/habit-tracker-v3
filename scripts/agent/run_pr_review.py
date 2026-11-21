#!/usr/bin/env python3
"""Holistic review of a milestone PR (<base>...int/<M>) by the reviewer CLI; writes work/reviews/<M>.pr.md.

PRs are stacked, one per milestone: main <- int/M1 <- int/M2 <- ... The base of int/<M> is the previous milestone's
integration branch while that one is not merged yet, else main (`python scripts/agent/milestone.py base <M>`),
so the packet holds only this milestone's changes. Lock/generated files are listed with line counts only.

  python scripts/agent/run_pr_review.py M2            # build the packet and run the reviewer
  python scripts/agent/run_pr_review.py M2 --dry-run  # build the packet only and print its size

The reviewer gets ONE packet (work/.pack/<M>.pr.md): the milestone's acceptance criteria, its tickets, the commit
list, the diffstat, the Drift log row and the diff itself (contracts and source first, then tests, then docs) up to
reviewer.pr_packet_tokens (default 60000). It is told not to re-run the gates: integrate.py already ran verify.py
after every merge. Without a packet, a whole-milestone review tends to re-read the repo and re-run the suite, which
costs many times more tokens and burns the reviewer's usage limit.

Like run_review.py, the packet goes in the prompt (stdin), the reviewer CLI runs read-only and only answers, and this
script writes the review file. Effort: reviewer.hard.effort or reviewer.effort.last_round (high); model: reviewer.hard
when reviewer.hard.milestone_pr is true. An earlier <M>.pr.md is kept as <M>.pr.rN.md.
Exit codes: 0 approved, 3 changes_requested, 5 reviewer unavailable (usage/rate limit), 1 error / no verdict.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time

import common as c
import pack as packmod
from run_review import parse_answer


def section(text: str, heading: str, contains: bool = False) -> str:
    out, on = [], False
    for ln in text.split("\n"):
        if ln.startswith("## "):
            title = ln[3:].strip()
            on = heading in title if contains else (title == heading or title.startswith(heading + " "))
        if on:
            out.append(ln)
    return "\n".join(out).strip()


def order_key(path: str) -> tuple[int, str]:
    if path.startswith("docs/ai/contracts/"):
        return 0, path
    if path.startswith("docs/") or path.endswith((".md", ".mmd")):
        return 3, path
    if "test" in path.lower():
        return 2, path
    return 1, path


def build_packet(m: str, root, cfg) -> tuple[str, int]:
    g = cfg["git"]
    base, head = c.milestone_base(m, root, cfg), g["integration_branch_prefix"] + m
    rng = f"{base}...{head}"
    budget = int(cfg.get("reviewer", {}).get("pr_packet_tokens", 60000))
    work = cfg["paths"]["tickets"].split("/")[0]

    ms_file = root / "docs/plan/milestones.md"
    acceptance = section(ms_file.read_text(encoding="utf-8"), m) if ms_file.exists() else "(no milestones.md)"
    ov = root / "docs/plan/initial-overview.md"
    drift_log = section(ov.read_text(encoding="utf-8"), "Drift log", contains=True) if ov.exists() else ""
    drift = [ln for ln in drift_log.split("\n") if re.search(rf"\b{re.escape(m)}\b", ln)]
    tickets = sorted((t for t in c.load_tickets(root, cfg, include_archive=True).values()
                      if str(t.meta.get("milestone")) == m), key=lambda t: t.id)
    log = c.git(["log", "--oneline", f"{base}..{head}"], cwd=root)
    hide = [f":(exclude,glob){x}" for x in c.generated_globs(cfg)]
    stat = c.git(["diff", "--stat", rng, "--", ".", f":!{work}", *hide], cwd=root)
    files = sorted((f for f in c.git(["diff", "--name-only", rng, "--", ".", f":!{work}", *hide],
                                     cwd=root).split("\n") if f), key=order_key)
    generated = packmod.generated_changes(rng, root, cfg)

    parts = [
        f"# Milestone PR review packet: {head} -> {base}",
        "## Gates\nverify.py passed after every merge (integrate.py stops on a failure). Do not re-run it or the full "
        "test suite.",
        f"## Acceptance criteria\n{acceptance}",
        "## Tickets\n" + "\n".join(f"- {t.id} [{t.status}] {t.meta.get('title')}" for t in tickets),
        "## Drift log row\n" + ("\n".join(drift) or "(none found)"),
        f"## Commits\n{log}",
        f"## Diffstat\n{stat}",
        *([generated] if generated else []),
        "## Diff",
    ]
    used = c.estimate_tokens("\n\n".join(parts), cfg)
    left_out = []
    for f in files:
        d = c.git(["diff", rng, "--", f], cwd=root)
        t = c.estimate_tokens(d, cfg)
        if used + t > budget:
            left_out.append(f)
            continue
        parts.append(f"```diff\n{d}\n```")
        used += t
    if left_out:
        parts.append("## Not inlined (budget); open only if a finding needs them\n"
                     + "\n".join(f"- {f}" for f in left_out))
    text = "\n\n".join(parts) + "\n"
    return text, c.estimate_tokens(text, cfg)


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("milestone")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    m = a.milestone
    root = c.control_root()
    cfg = c.load_config(root)
    rv = cfg.get("reviewer", {})
    packs = c.cfg_path(cfg, "packs", root)
    packs.mkdir(parents=True, exist_ok=True)
    pack_rel = f"{cfg['paths']['packs']}/{m}.pr.md"
    packet, tokens = build_packet(m, root, cfg)
    (packs / f"{m}.pr.md").write_text(packet, encoding="utf-8")
    out_path = c.cfg_path(cfg, "reviews", root) / f"{m}.pr.md"
    out_file = packs / f"{m}.pr.answer.md"

    prompt = f"""You are the reviewer for the milestone pull request of {m}. Review the WHOLE milestone, not single
tickets, from the packet below (acceptance criteria, tickets, commits, diff). Open a repository file only when one
finding needs a specific line that is not in the packet. Do NOT run the gates or the test suite: they already passed.

Check: every acceptance criterion is implemented AND proven by a test; contracts honored across modules; no forbidden
edges (docs/ai/modules.yaml); correctness and data-integrity bugs; concurrency (check-then-act races, shared state);
the app works through its real entry point and config (startup, logging, settings), not only in tests; inputs
validated exactly as the contract says (formats, bounds); duplicated logic; dead code; naming consistency;
docs match behavior. Only real problems; style is not a blocker. A claim that something is untested must name the
missing test or the change that would not be caught.

Reply with ONLY this document:
---
verdict: approved | changes_requested
---
## Findings (most severe first; each tagged [blocker] or [minor], with path:line and the required fix)
## Acceptance check (one line per criterion: PASS/FAIL + the proving test)
## Notes

Use changes_requested only if there is at least one [blocker].

{packet}"""
    effort = rv.get("effort", {})
    effort = effort.get("last_round", "high") if isinstance(effort, dict) else effort
    cmd, model, effort = c.reviewer_command(cfg, prompt, effort, str(out_file),
                                            hard=bool(rv.get("hard", {}).get("milestone_pr")))
    via_stdin = rv.get("prompt_via", "stdin") == "stdin"
    if a.dry_run:
        shown = [x if x != prompt else "<prompt>" for x in cmd]
        print(f"(dry run) packet {pack_rel} ~{tokens} tokens, model {model or '(default)'}, effort {effort}")
        print(subprocess.list2cmdline(shown) + ("   < prompt on stdin" if via_stdin else ""))
        return
    if not cmd or not (exe := shutil.which(cmd[0])):
        sys.exit(f"error: reviewer executable '{cmd[0] if cmd else ''}' not found (reviewer.command)")
    cmd[0] = exe
    out_file.unlink(missing_ok=True)

    print(f"PR review {m} model={model or 'default'} effort={effort} packet~{tokens}tok", flush=True)
    log = packs / f"{m}.pr.log"
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=root, input=prompt if via_stdin else None, text=True, capture_output=True,
                              encoding="utf-8", errors="replace", timeout=2 * int(rv.get("timeout_seconds", 600)))
        out, stdout = (proc.stdout or "") + "\n" + (proc.stderr or ""), proc.stdout or ""
    except subprocess.TimeoutExpired as e:
        out, stdout = f"TIMEOUT after {e.timeout}s", ""
    seconds = round(time.monotonic() - started)
    log.write_text(out, encoding="utf-8")
    answer = out_file.read_text(encoding="utf-8") if out_file.exists() and out_file.stat().st_size else stdout
    verdict, body = parse_answer(answer)
    c.log_usage(root, cfg, "reviewer", f"{m}-pr", f"{rv.get('command', ['?'])[0]}:{model or 'default'}", effort=effort,
                packet_tokens=tokens, milestone=m, tier="PR", seconds=seconds, **c.codex_usage(out))
    if verdict not in ("approved", "changes_requested"):
        if c.reviewer_unavailable(cfg, out):
            print(f"reviewer hit a usage/rate limit. Fallback: the `reviewer` subagent on {pack_rel}")
            sys.exit(5)
        print(c.tail(out, 20))
        sys.exit(f"error: no verdict in the reviewer's answer. Log: {log.relative_to(root).as_posix()}")

    if out_path.exists():  # never overwrite an earlier round
        n = 1
        while (out_path.parent / f"{m}.pr.r{n}.md").exists():
            n += 1
        out_path.rename(out_path.parent / f"{m}.pr.r{n}.md")
    reviewer = f"{rv.get('command', ['?'])[0]} {model or ''}".strip()
    out_path.write_text(f"---\nmilestone: {m}\nverdict: {verdict}\nreviewer: {json.dumps(reviewer)}\n---\n"
                        f"{body.strip()}\n", encoding="utf-8")
    print(f"{m} PR review: {verdict} -> {out_path.relative_to(root).as_posix()}")
    print(f"stacked PR: gh pr create --base {c.milestone_base(m, root, cfg)} "
          f"--head {cfg['git']['integration_branch_prefix']}{m}")
    sys.exit(0 if verdict == "approved" else 3)


if __name__ == "__main__":
    main()
