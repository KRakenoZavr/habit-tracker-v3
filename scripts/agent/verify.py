#!/usr/bin/env python3
"""Deterministic gate: run the ticket's verify commands plus the global ones from .agents/config.json.

  python scripts/agent/verify.py                 # global commands only (milestone / integration check)
  python scripts/agent/verify.py T-0007          # ticket commands + global commands
  python scripts/agent/verify.py T-0007 --cwd .worktrees/T-0007 [--ticket-only]

Prints PASS/FAIL per command and the tail of failing output. Exit 1 on any failure.
The result is recorded in work/.pack/<id>.gate.json for the reviewer and the next executor round.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import common as c


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id", nargs="?")
    ap.add_argument("--cwd", type=Path)
    ap.add_argument("--ticket-only", action="store_true", help="skip global commands (fast inner loop)")
    a = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    cwd = (a.cwd or Path.cwd()).resolve()
    n_tail = cfg["budgets"]["verify_tail_lines"]

    cmds: list[str] = []
    t = None
    if a.id:
        t = c.find_ticket(a.id, root, cfg)
        cmds += t.get_list("verify")
    if not a.ticket_only:
        cmds += [x for x in cfg.get("verify", {}).get("commands", []) if x and x not in cmds]

    if not cmds:
        msg = "no verify commands configured (ticket verify list and .agents/config.json verify.commands are empty)"
        print(f"FAIL {msg}" if t else f"WARN {msg}")
        if t:
            c.update_gate(t.id, root, cfg, "verify", False, msg)
        sys.exit(1 if t else 0)

    failures = []
    for cmd in cmds:
        proc = subprocess.run(cmd, shell=True, cwd=cwd, text=True, capture_output=True,
                              encoding="utf-8", errors="replace")
        ok = proc.returncode == 0
        print(f"{'PASS' if ok else 'FAIL'} {cmd}")
        if not ok:
            out = (proc.stdout or "") + (proc.stderr or "")
            failures.append(f"$ {cmd}  (exit {proc.returncode})\n{c.tail(out, n_tail)}")

    detail = "\n\n".join(failures)
    if failures:
        print("\n---- failing output (tail) ----")
        print(detail)
    print(f"\nverify: {'FAIL' if failures else 'PASS'} ({len(cmds) - len(failures)}/{len(cmds)} commands passed)")
    if t:
        c.update_gate(t.id, root, cfg, "verify", not failures, detail)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
