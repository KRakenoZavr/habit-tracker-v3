#!/usr/bin/env python3
"""Integrate approved tickets of a milestone into int/<milestone>, in dependency order.

  python scripts/agent/integrate.py M2            # dry run: show order and what is not approved yet
  python scripts/agent/integrate.py M2 --apply    # squash-merge each t/<id>, commit, run global verify
  options: --partial (integrate approved tickets even if others in the milestone are not approved)

Run from the control checkout while it is on int/<milestone>. Only work/ may be dirty (it is committed first).
On a merge conflict the merge is undone and the ticket goes back to 'ready' for a rebase.
On a verify failure the run stops so the architect can inspect the last merge commit.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import common as c

HERE = Path(__file__).resolve().parent


def topo(tickets: list[c.Ticket]) -> list[c.Ticket]:
    by_id = {t.id: t for t in tickets}
    seen, order = set(), []

    def visit(t):
        if t.id in seen:
            return
        seen.add(t.id)
        for d in t.get_list("depends_on"):
            if d.upper() in by_id:
                visit(by_id[d.upper()])
        order.append(t)

    for t in sorted(tickets, key=lambda x: x.id):
        visit(t)
    return order


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("milestone")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--partial", action="store_true")
    a = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    g = cfg["git"]
    ms = [t for t in c.load_tickets(root, cfg).values() if str(t.meta.get("milestone")) == a.milestone]
    approved = [t for t in ms if t.status == "approved"]
    pending = [t for t in ms if t.status not in ("approved", "integrated", "done")]
    order = topo(approved)

    print(f"Milestone {a.milestone}: {len(approved)} approved, {len(pending)} not approved yet")
    for t in pending:
        print(f"  pending  {t.id} [{t.status}] {t.meta.get('title')}")
    print("Merge order:", " -> ".join(t.id for t in order) or "(nothing to merge)")
    if pending and not a.partial:
        print("Not all tickets are approved. Use --partial to integrate the approved ones anyway.")
        if a.apply:
            sys.exit(1)
    if not a.apply or not order:
        return

    int_branch = g["integration_branch_prefix"] + a.milestone
    if c.current_branch(root) != int_branch:
        sys.exit(f"error: control checkout must be on {int_branch}. "
                 f"Run: git switch {int_branch}   (or: git switch -c {int_branch})")
    dirty = [ln[3:] for ln in c.run(["git", "status", "--porcelain"], cwd=root).stdout.split("\n") if ln.strip()]
    work_prefix = "work/"
    if any(not c.norm(p).startswith(work_prefix) for p in dirty):
        sys.exit("error: uncommitted changes outside work/. Commit or stash them first.")
    if dirty:
        c.git(["add", "work"], cwd=root)
        c.git(["commit", "-m", f"chore(work): ticket state before integrating {a.milestone}"], cwd=root)

    py = sys.executable
    for t in order:
        branch = g["ticket_branch_prefix"] + t.id
        if not c.branch_exists(branch, root):
            print(f"skip {t.id}: branch {branch} not found")
            continue
        m = c.run(["git", "merge", "--squash", branch], cwd=root, check=False)
        if m.returncode != 0:
            c.run(["git", "reset", "--merge"], cwd=root, check=False)
            c.set_status(c.find_ticket(t.id, root, cfg), "ready", by="integrate", force=True,
                         note=f"merge conflict on {int_branch}; rebase t/{t.id} onto it and re-run executor")
            print(f"CONFLICT {t.id}: set back to ready")
            continue
        if not c.run(["git", "diff", "--cached", "--quiet"], cwd=root, check=False).returncode:
            print(f"skip {t.id}: no changes")
        else:
            c.git(["commit", "-m", f"{t.id}: {t.meta.get('title')}"], cwd=root)
        v = subprocess.run([py, str(HERE / "verify.py"), "--cwd", str(root)])
        if v.returncode != 0:
            sys.exit(f"verify failed after merging {t.id}. Inspect HEAD (git show), then fix via new tickets.")
        c.set_status(c.find_ticket(t.id, root, cfg), "integrated", by="integrate", note=f"merged into {int_branch}")
        print(f"integrated {t.id}")

    c.git(["add", "work"], cwd=root)
    c.run(["git", "commit", "-m", f"chore(work): integrated tickets into {int_branch}"], cwd=root, check=False)
    print("\nNext (architect): holistic review, doc_fresh.py, update-docs skill, changelog, open the PR.")


if __name__ == "__main__":
    main()
