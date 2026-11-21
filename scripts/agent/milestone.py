#!/usr/bin/env python3
"""Milestone branches for stacked PRs: main <- int/M1 <- int/M2 <- int/M3 ...

Each milestone gets its own integration branch and its own PR. The next milestone starts from the previous
milestone's branch right away, without waiting for that PR to merge, so review and work overlap.

  python scripts/agent/milestone.py start M2     # create/switch int/M2 from its base, mark the usage window start
  python scripts/agent/milestone.py base M2      # print the PR base of int/M2 (int/M1 until merged, then main)
  python scripts/agent/milestone.py restack M1   # after int/M1's PR merged: print how to move int/M2 onto main

Base rule (common.milestone_base): int/M<n-1> while it exists and is not merged into git.default_base, else
git.default_base. Merge stacked PRs bottom-up with a MERGE commit (not squash) and GitHub retargets the next PR to
main by itself when the merged branch is deleted. After a squash merge, run `restack` and follow its commands.
"""
from __future__ import annotations

import argparse
import re
import sys

import common as c


def next_milestone(m: str) -> str | None:
    mt = re.match(r"^(.*?)(\d+)$", m)
    return f"{mt.group(1)}{int(mt.group(2)) + 1}" if mt else None


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["start", "base", "restack"])
    ap.add_argument("milestone")
    a = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    g = cfg["git"]
    m = a.milestone
    branch = g["integration_branch_prefix"] + m
    base = c.milestone_base(m, root, cfg)

    if a.action == "base":
        print(base)
        return

    if a.action == "start":
        dirty = [ln[3:] for ln in c.run(["git", "status", "--porcelain"], cwd=root).stdout.split("\n") if ln.strip()]
        if any(not c.norm(p).startswith("work/") for p in dirty):
            sys.exit("error: uncommitted changes outside work/. Commit them first.")
        if c.branch_exists(branch, root):
            if c.current_branch(root) != branch:
                c.git(["switch", branch], cwd=root)
            print(f"{branch} exists; checked out")
        else:
            c.git(["switch", "-c", branch, base], cwd=root)
            print(f"created {branch} from {base}")
        log = c.cfg_path(cfg, "packs", root) / "usage.jsonl"
        has_start = log.exists() and any('"marker"' in ln and f'"milestone": "{m}"' in ln and '"start"' in ln
                                         for ln in log.read_text(encoding="utf-8").splitlines())
        if not has_start:
            c.log_usage(root, cfg, "marker", None, None, milestone=m, event="start")
        print(f"PR base for {branch}: {base}   (open it with: gh pr create --base {base} --head {branch})")
        return

    # restack
    nxt = next_milestone(m)
    nb = g["integration_branch_prefix"] + nxt if nxt else None
    default = g.get("default_base", "main")
    if not nb or not c.branch_exists(nb, root):
        print(f"no {nb or 'next milestone'} branch: nothing to restack")
        return
    merged = c.run(["git", "merge-base", "--is-ancestor", branch, default], cwd=root, check=False).returncode == 0
    if merged:
        print(f"{branch} is an ancestor of {default} (merge commit): nothing to rebase.")
        print(f"  gh pr edit {nb} --base {default}     # only if GitHub did not retarget it already")
        return
    print(f"{branch} was squash-merged (its commits are not in {default}). Move {nb} onto {default}:")
    print(f"  git fetch origin && git switch {nb}")
    print(f"  git rebase --onto origin/{default} {branch} {nb}")
    print(f"  git push --force-with-lease origin {nb}")
    print(f"  gh pr edit {nb} --base {default}")


if __name__ == "__main__":
    main()
