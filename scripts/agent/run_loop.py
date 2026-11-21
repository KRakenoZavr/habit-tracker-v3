#!/usr/bin/env python3
"""Run the whole ticket loop for a milestone WITHOUT the architect in the loop.

For every runnable ticket:  worker (headless) -> gates -> reviewer -> fix rounds -> approved -> merge into int/<M>.
Dependent tickets start as soon as their dependencies are integrated. The architect is needed only for what
this script reports under "Needs architect" (blocked / escalated tickets) and for the milestone review.

  python scripts/agent/run_loop.py M1                   # run until nothing is runnable
  python scripts/agent/run_loop.py M1 --max-tickets 3   # stop after 3 finished tickets
  python scripts/agent/run_loop.py M1 --no-calibration  # skip the automatic first-run calibration

Calibration (loop.calibration): on the first run of a milestone (no ticket integrated yet) the loop stops after
loop.calibration.tickets finished tickets and prints a report, so ticket sizing is checked before the rest runs.
  python scripts/agent/run_loop.py M1 --dry-run         # show what would run
  options: --max-parallel N (default loop.max_parallel: conflict-free tickets run side by side, each in its own
           worktree), --no-integrate. Tickets approved outside the loop are merged when it starts.

Output is deliberately short (one line per step) so an architect session that starts it stays small.
Full logs: work/.pack/<id>.loop.log, <id>.worker.log, <id>.review.log. Usage: scripts/agent/usage.py.

Exit codes: 0 nothing left to run · 2 some tickets need the architect · 5 stopped on a usage/rate limit.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import common as c
import conflicts
import state

HERE = Path(__file__).resolve().parent
RESUMABLE = ("in_progress", "changes_requested", "in_review")
LOCK = threading.Lock()
PRINT = threading.Lock()


def say(msg: str) -> None:
    with PRINT:
        print(msg, flush=True)


def step(tid: str, script: str, args: list[str], root: Path, cfg: dict, want: str | None = None) -> tuple[int, str]:
    """Run one helper script, append its output to the ticket's loop log, return (code, last line)."""
    proc = subprocess.run([sys.executable, str(HERE / script), *args], cwd=root, text=True,
                          capture_output=True, encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    log = c.cfg_path(cfg, "packs", root) / f"{tid}.loop.log"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n===== {c.now()} {script} {' '.join(args)} (exit {proc.returncode})\n{out}")
    lines = [ln for ln in out.strip().split("\n") if ln.strip()]
    if want:
        hits = [ln.strip() for ln in lines if any(w in ln for w in want.split("|"))]
        return proc.returncode, "; ".join(hits)[:200] or (lines[-1][:160] if lines else "")
    return proc.returncode, (lines[-1][:160] if lines else "")


def process(tid: str, root: Path, cfg: dict) -> str:
    """Drive one ticket until approved / escalated / blocked / limit / error."""
    gate_retries = int(cfg["executor"].get("gate_retries", 2))
    gate_fails = 0
    for _ in range(50):  # safety cap; real limits are max_review_rounds and gate_retries
        t = c.find_ticket(tid, root, cfg)
        if t.status in ("ready", "changes_requested", "in_progress"):
            code, last = step(tid, "run_executor.py", [tid], root, cfg)
            say(f"  {tid} worker: {last}")
            if code == 5:
                return "limit"
            if code == 2:
                return "blocked"
            if code == 1:
                gate_fails += 1
                if gate_fails > gate_retries:
                    c.set_status(c.find_ticket(tid, root, cfg), "blocked", by="run_loop",
                                 note=f"gates still failing after {gate_fails} worker runs")
                    return "blocked"
                continue
            if code != 0:
                return "error"
            gate_fails = 0
        t = c.find_ticket(tid, root, cfg)
        if t.status == "in_review":
            code, last = step(tid, "run_review.py", [tid], root, cfg)
            say(f"  {tid} review: {last}")
            if code == 0:
                return "approved"
            if code == 3:
                continue
            if code == 4:
                return "escalated"
            if code == 5:
                return "limit"
            return "error"
        if t.status in ("approved", "integrated", "done"):
            return "approved"
        if t.status in ("blocked", "escalated"):
            return t.status
        return "error"
    return "error"


def integrate(milestone: str, root: Path, cfg: dict) -> None:
    with LOCK:
        code, last = step("_integrate", "integrate.py", [milestone, "--apply", "--partial"], root, cfg,
                          want="integrated T-|CONFLICT|verify failed|error")
    say(f"  merge: {last}" + ("" if code == 0 else f" (exit {code}, see work/.pack/_integrate.loop.log)"))


def report(attempted: dict, root: Path, cfg: dict, milestone: str) -> None:
    """Calibration report: how hard the first tickets were, and what to do next."""
    rows, rounds = [], []
    for tid in attempted:
        t = c.find_ticket(tid, root, cfg)
        r = int(t.meta.get("review_round") or 0) + (1 if t.status in ("approved", "integrated", "done", "escalated") else 0)
        rounds.append(r)
        rows.append(f"  {tid} [{t.meta.get('difficulty')}] {t.status:<11} review rounds {r}  {t.meta.get('title')}")
    if not rows:
        return
    ok = sum(1 for tid in attempted if c.find_ticket(tid, root, cfg).status in ("approved", "integrated", "done")
             and int(c.find_ticket(tid, root, cfg).meta.get("review_round") or 0) <= 1)
    say("\nCalibration report")
    for r in rows:
        say(r)
    say(f"  {ok}/{len(rows)} approved within 2 review rounds")
    if ok * 10 >= len(rows) * 7:
        say(f"  Sizing looks right. Run the rest: python scripts/agent/run_loop.py {milestone}")
    else:
        say("  Tickets look too big or unclear. Ask the architect to re-slice the remaining tickets "
            "(smaller Steps, exact Interface, fewer files) before running the rest.")


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("milestone")
    ap.add_argument("--max-parallel", type=int)
    ap.add_argument("--max-tickets", type=int, default=0)
    ap.add_argument("--no-integrate", action="store_true")
    ap.add_argument("--no-calibration", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    loop_cfg = cfg.get("loop", {})
    par = max(1, a.max_parallel or int(loop_cfg.get("max_parallel", 1)))
    do_integrate = loop_cfg.get("integrate_after_approval", True) and not a.no_integrate
    int_branch = cfg["git"]["integration_branch_prefix"] + a.milestone
    if do_integrate and not a.dry_run and c.current_branch(root) != int_branch:
        sys.exit(f"error: switch the main checkout to {int_branch} first (git switch -c {int_branch}), "
                 f"or pass --no-integrate")

    cal = loop_cfg.get("calibration", {})
    ms_tickets = [t for t in c.load_tickets(root, cfg).values() if str(t.meta.get("milestone")) == a.milestone]
    calibrating = (cal.get("enabled") and not a.no_calibration and not a.max_tickets and ms_tickets
                   and not any(t.status in ("integrated", "done") for t in ms_tickets))
    if calibrating:
        a.max_tickets = int(cal.get("tickets", 3))

    usage_log = c.cfg_path(cfg, "packs", root) / "usage.jsonl"
    usage_start = len(usage_log.read_text(encoding="utf-8").splitlines()) if usage_log.exists() else 0
    attempted: dict[str, str] = {}
    stop = False
    finished = 0

    def runnable(running_ids: set[str] = frozenset()) -> list[str]:
        """Resumable tickets first, then the first conflict-free batch of ready ones. Every candidate is checked
        against the tickets already running AND the candidates picked before it: two tickets that share files or
        lock resources never run at the same time, whether they are resumed or fresh."""
        tickets = c.load_tickets(root, cfg)
        resume = [t.id for t in tickets.values() if t.status in RESUMABLE
                  and str(t.meta.get("milestone")) == a.milestone and t.id not in attempted]
        batches, _, _ = conflicts.plan(root, cfg, a.milestone, exclude_active=set(resume))
        fresh = [t.id for t in (batches[0] if batches else []) if t.id not in attempted]
        picked: list[str] = []
        taken = [tickets[x] for x in running_ids if x in tickets]
        for tid in resume + [x for x in fresh if x not in resume]:
            if tid in running_ids:
                continue
            if any(conflicts.conflict(tickets[tid], o, cfg) for o in taken):
                continue
            picked.append(tid)
            taken.append(tickets[tid])
        return picked

    if a.dry_run:
        todo = runnable()
        print(f"would run (max {par} at a time): {', '.join(todo) or 'nothing'}")
        return

    say(f"run_loop {a.milestone}: max_parallel={par}, integrate={'on' if do_integrate else 'off'}"
        + (f", CALIBRATION run: stops after {a.max_tickets} tickets" if calibrating else ""))
    if do_integrate and any(t.status == "approved" for t in ms_tickets):
        integrate(a.milestone, root, cfg)  # tickets approved outside the loop (e.g. by the reviewer subagent)
    running: dict = {}
    with ThreadPoolExecutor(max_workers=par) as pool:
        while True:
            if not stop and not (a.max_tickets and finished + len(running) >= a.max_tickets):
                busy = set(running.values())
                for tid in runnable(busy):
                    if len(running) >= par:
                        break
                    say(f"> {tid}")
                    attempted[tid] = "running"
                    running[pool.submit(process, tid, root, cfg)] = tid
                    busy.add(tid)
            if not running:
                break
            done, _ = wait(list(running), return_when=FIRST_COMPLETED)
            for fut in done:
                tid = running.pop(fut)
                try:
                    outcome = fut.result()
                except Exception as e:  # noqa: BLE001
                    outcome = f"error: {e}"
                attempted[tid] = outcome
                finished += 1
                say(f"< {tid}: {outcome}")
                if outcome == "approved" and do_integrate:
                    integrate(a.milestone, root, cfg)
                if outcome == "limit":
                    stop = True
                    say("! usage/rate limit hit: not starting new tickets; finishing running ones")
                state.write(root, cfg, a.milestone)

    state.write(root, cfg, a.milestone)
    tickets = {t.id: t for t in c.load_tickets(root, cfg).values() if str(t.meta.get("milestone")) == a.milestone}
    need = [t for t in tickets.values() if t.status in ("blocked", "escalated")]
    left = [t for t in tickets.values() if t.status not in ("integrated", "done", "approved", "blocked", "escalated")]
    say("\nSummary: " + ", ".join(f"{k} {v}" for k, v in sorted(
        {s: sum(1 for t in tickets.values() if t.status == s) for s in {t.status for t in tickets.values()}}.items())))
    if need:
        say("Needs architect: " + "; ".join(f"{t.id} {t.status} ({state.last_note(t) or 'see log'})" for t in need))
    if left and not stop:
        capped = bool(a.max_tickets) and finished >= a.max_tickets
        say(("Remaining (stopped at --max-tickets/calibration; run again): " if capped else "Not runnable yet: ")
            + ", ".join(f"{t.id}[{t.status}]" for t in left))
    rows = usage_log.read_text(encoding="utf-8").splitlines()[usage_start:] if usage_log.exists() else []
    if rows:
        import json
        recs = [json.loads(r) for r in rows if '"marker"' not in r]
        tok = sum(int(r.get("tokens") or 0) for r in recs)
        mins = sum(float(r.get("seconds") or 0) for r in recs) / 60
        say(f"Usage this run: {len(recs)} agent runs, ~{tok:,} tokens, {mins:.0f} min of agent time "
            f"(milestone table: python scripts/agent/usage.py --milestone {a.milestone})")
    if calibrating:
        report(attempted, root, cfg, a.milestone)
    if stop:
        sys.exit(5)
    sys.exit(2 if need else 0)


if __name__ == "__main__":
    main()
