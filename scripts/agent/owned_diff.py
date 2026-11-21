#!/usr/bin/env python3
"""Fail if a ticket's changes touch files outside its files_owned, or any protected path.

  python scripts/agent/owned_diff.py T-0007 [--cwd .worktrees/T-0007] [--base int/M2]

Checks committed changes (base...HEAD) and uncommitted/untracked changes in --cwd.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import common as c


def changed_files(cwd: Path, base: str) -> set[str]:
    files = set()
    out = c.git(["diff", "--name-only", f"{base}...HEAD"], cwd=cwd, check=False)
    files.update(x for x in out.split("\n") if x)
    status = c.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=cwd, check=False).stdout
    for line in status.split("\n"):
        if not line.strip():
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.add(path.strip().strip('"'))
    return {c.norm(f) for f in files}


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id")
    ap.add_argument("--cwd", type=Path)
    ap.add_argument("--base")
    a = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    t = c.find_ticket(a.id, root, cfg)
    cwd = (a.cwd or Path.cwd()).resolve()
    base = a.base or t.meta.get("base") or cfg["git"]["default_base"]

    owned = t.get_list("files_owned")
    protected = cfg.get("protected_globs", [])
    ignore = [cfg["paths"]["packs"] + "/**"]
    problems = []
    changed = changed_files(cwd, str(base))
    for f in sorted(changed):
        if c.matches(f, ignore):
            continue
        if c.matches(f, protected):
            problems.append(f"protected path changed: {f}")
        elif not c.matches(f, owned):
            problems.append(f"not in files_owned: {f}")

    detail = "\n".join(problems)
    if problems:
        print("owned_diff: FAIL")
        print(detail)
        print("Revert these changes, or set the ticket to blocked and ask the architect to widen files_owned.")
    else:
        print(f"owned_diff: PASS ({len(changed)} changed file(s), all owned)")
    c.update_gate(t.id, root, cfg, "owned_diff", not problems, detail)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
