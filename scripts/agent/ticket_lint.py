#!/usr/bin/env python3
"""Lint tickets so the tier's executor can execute them from their pack alone.

  python scripts/agent/ticket_lint.py              # all draft/ready tickets
  python scripts/agent/ticket_lint.py T-0007 T-0008
  python scripts/agent/ticket_lint.py --all        # every non-archived ticket

Exit 1 if any ERROR. Warnings need a justification in "Notes from architect".
"""
from __future__ import annotations

import argparse
import re
import sys

import common as c


def strip_noise(body: str) -> str:
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    return re.sub(r"```.*?```", "", body, flags=re.S)


def find_cycles(tickets: dict[str, c.Ticket]) -> list[list[str]]:
    graph = {tid: [d.upper() for d in t.get_list("depends_on")] for tid, t in tickets.items()}
    cycles, state, stack = [], {}, []

    def visit(n):
        state[n] = 1
        stack.append(n)
        for m in graph.get(n, []):
            if m not in graph:
                continue
            if state.get(m) == 1:
                cycles.append(stack[stack.index(m):] + [m])
            elif state.get(m) is None:
                visit(m)
        stack.pop()
        state[n] = 2

    for n in graph:
        if state.get(n) is None:
            visit(n)
    return cycles


def lint(t: c.Ticket, tickets: dict, root, cfg) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    b = cfg["budgets"]
    m = t.meta
    for k in c.REQUIRED_KEYS:
        if k not in m:
            errs.append(f"missing frontmatter key '{k}'")
    if not t.path.name.startswith(f"{t.id}-") and t.path.name != f"{t.id}.md":
        errs.append(f"file name {t.path.name} does not start with id {t.id}")
    if t.status not in c.STATUSES:
        errs.append(f"invalid status '{t.status}'")
    tiers = cfg["executor"]["tiers"]
    if str(m.get("difficulty")) not in tiers:
        errs.append(f"difficulty must be one of the tiers in .agents/config.json: {', '.join(tiers)}")
        return errs, warns
    tier_name, tier = c.tier_of(t, cfg)
    max_files = int(tier.get("max_files_owned", 3))

    owned = t.get_list("files_owned")
    if not owned:
        errs.append("files_owned is empty")
    if len(owned) > max_files:
        errs.append(f"files_owned has {len(owned)} entries (tier {tier_name} max {max_files}): split the ticket")
    for f in owned:
        if c.matches(f, cfg.get("protected_globs", [])):
            errs.append(f"files_owned contains protected path {f}")
    cfg_locks = [x for x in cfg.get("lock_resources", []) if x]
    declared = t.get_list("lock_resources")
    for f in owned:
        if c.matches(f, cfg_locks) and not any(c.globs_overlap(f, d) for d in declared):
            errs.append(f"{f} is a lock resource: list it in lock_resources")
    if not t.get_list("verify"):
        errs.append("verify is empty: every ticket needs commands that prove it")
    if c.tdd_on(t, cfg) and not any(c.is_test_file(f, cfg) for f in owned):
        errs.append("tests first (executor.tdd): files_owned needs a test file matching executor.tdd.test_globs, "
                    "or set `tdd: false` and give the reason in Notes from architect")
    gen = [f for f in owned if c.is_generated(f, cfg)]
    if gen:
        warns.append(f"owns generated file(s) {', '.join(gen)}: the worker sees only their names; "
                     f"say which tool regenerates them in Steps")

    for d in t.get_list("depends_on"):
        if d.upper() not in tickets:
            errs.append(f"depends_on {d} does not exist")
    for f in t.get_list("files_read"):
        if not (root / f).exists():
            errs.append(f"files_read {f} does not exist")

    secs = c.sections(t.body)
    if m.get("tdd") is False and "tdd" not in secs.get("Notes from architect", "").lower()             and "test" not in secs.get("Notes from architect", "").lower():
        warns.append("tdd: false without a reason in Notes from architect")
    for s in c.REQUIRED_SECTIONS:
        if not secs.get(s, "").strip() or not strip_noise(secs.get(s, "")).strip():
            if s == "Interface" and secs.get(s, "").strip():
                continue  # interface may be entirely a code block
            errs.append(f"section '## {s}' is missing or empty")
    steps = [ln for ln in secs.get("Steps", "").split("\n") if re.match(r"^\s*\d+\.\s+\S", ln)]
    if len(steps) > b["max_steps"]:
        warns.append(f"{len(steps)} steps (max {b['max_steps']}): consider splitting")
    acc = [ln for ln in secs.get("Acceptance criteria", "").split("\n") if ln.strip().startswith("- ")]
    for ln in acc:
        if "`" not in ln:
            warns.append(f"acceptance criterion has no test/command in backticks: {ln.strip()[:70]}")

    body_wo_log = t.body.split("\n## Log")[0]
    tok = c.estimate_tokens(body_wo_log, cfg)
    if tok > b["ticket_body_max_tokens"]:
        warns.append(f"ticket body ~{tok} tokens (max {b['ticket_body_max_tokens']})")
    placeholders = re.findall(r"<[^<>\n]*\s[^<>\n]*>", strip_noise(body_wo_log))
    if placeholders:
        warns.append(f"template placeholders left: {', '.join(placeholders[:3])}")

    # rough pack estimate
    pack_text = t.raw
    for f in t.get_list("files_read") + owned:
        p = root / f
        if p.is_file() and not c.is_generated(f, cfg):
            pack_text += p.read_text(encoding="utf-8", errors="replace")
    budget = c.pack_budget(t, cfg)
    est = c.estimate_tokens(pack_text, cfg)
    if est > budget:
        warns.append(f"estimated pack ~{est} tokens > budget {budget}: shrink files_read or split")
    return errs, warns


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    tickets = c.load_tickets(root, cfg, include_archive=True)
    active = c.load_tickets(root, cfg)
    if args.ids:
        targets = [c.find_ticket(i, root, cfg) for i in args.ids]
    elif args.all:
        targets = list(active.values())
    else:
        targets = [t for t in active.values() if t.status in ("draft", "ready")]

    total_err = 0
    for cyc in find_cycles(active):
        print(f"ERROR dependency cycle: {' -> '.join(cyc)}")
        total_err += 1
    for t in targets:
        errs, warns = lint(t, tickets, root, cfg)
        total_err += len(errs)
        mark = "OK  " if not errs else "FAIL"
        print(f"{mark} {t.id} {t.meta.get('title')}")
        for e in errs:
            print(f"     ERROR {e}")
        for w in warns:
            print(f"     warn  {w}")
    if not targets:
        print("no tickets to lint")
    sys.exit(1 if total_err else 0)


if __name__ == "__main__":
    main()
