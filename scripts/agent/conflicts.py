#!/usr/bin/env python3
"""Compute which ready tickets can run in parallel.

Two tickets conflict if their files_owned overlap or their lock resources overlap.
Tickets that are active or approved-but-not-integrated occupy their files until they are merged
into int/<milestone> (integrate.py --partial), so a new ticket never branches from stale code.

  python scripts/agent/conflicts.py [--milestone M2] [--json]
"""
from __future__ import annotations

import argparse
import json

import common as c

ACTIVE = {"in_progress", "in_review", "changes_requested", "approved"}


def conflict(a: c.Ticket, b: c.Ticket, cfg: dict) -> list[str]:
    reasons = [f"owned {x} ~ {y}" for x, y in c.sets_overlap(a.get_list("files_owned"), b.get_list("files_owned"))]
    reasons += [f"lock {x} ~ {y}" for x, y in c.sets_overlap(a.lock_set(cfg), b.lock_set(cfg))]
    return reasons


def plan(root, cfg: dict, milestone: str | None = None, exclude_active: set[str] | None = None):
    """Return (batches, waiting_on_deps, conflicts_with_active) for ready tickets.

    exclude_active: ticket ids to NOT treat as occupying files (e.g. the ones run_loop is about to resume).
    """
    tickets = c.load_tickets(root, cfg, include_archive=True)
    active = [t for t in tickets.values() if t.status in ACTIVE and t.id not in (exclude_active or set())]
    ready = [t for t in tickets.values() if t.status == "ready"
             and (not milestone or str(t.meta.get("milestone")) == milestone)]
    waiting, blocked_by_active, candidates = {}, {}, []
    for t in ready:
        ok, missing = c.deps_satisfied(t, tickets)
        if not ok:
            waiting[t.id] = missing
            continue
        hits = {a.id: r for a in active if (r := conflict(t, a, cfg))}
        if hits:
            blocked_by_active[t.id] = hits
            continue
        candidates.append(t)
    batches: list[list[c.Ticket]] = []
    for t in sorted(candidates, key=lambda x: x.id):
        for batch in batches:
            if not any(conflict(t, o, cfg) for o in batch):
                batch.append(t)
                break
        else:
            batches.append([t])
    return batches, waiting, blocked_by_active


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--milestone")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    batches, waiting, blocked_by_active = plan(root, cfg, args.milestone)

    if args.json:
        print(json.dumps({
            "batches": [[t.id for t in b] for b in batches],
            "waiting_on_deps": waiting,
            "conflicts_with_active": blocked_by_active,
        }, indent=2))
        return

    if not batches:
        print("No ready tickets can start now.")
    for i, b in enumerate(batches, 1):
        print(f"Batch {i}: " + ", ".join(f"{t.id}[{t.meta.get('difficulty')}]" for t in b))
    if batches:
        print("  Batch 1 can start now; later batches after batch 1 is approved (they conflict with it).")
        print("  One GPU = one local executor at a time: run S/M tickets of a batch one by one,")
        print("  and overlap them with cloud work (L tickets, reviews).")
    for tid, miss in waiting.items():
        print(f"waiting  {tid}: depends on {', '.join(miss)}")
    for tid, hits in blocked_by_active.items():
        print(f"busy     {tid}: conflicts with active " + "; ".join(f"{k} ({', '.join(v)})" for k, v in hits.items()))


if __name__ == "__main__":
    main()
