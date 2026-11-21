#!/usr/bin/env python3
"""Token usage, effort and time per role and model, overall or for one milestone.

  python scripts/agent/usage.py                       # workers + reviewers, all time
  python scripts/agent/usage.py --milestone M2        # one milestone, INCLUDING the architect's Claude Code session
  python scripts/agent/usage.py --milestone M2 --write   # also save work/usage/M2.md (the table for the PR body)
  python scripts/agent/usage.py --tickets             # also per ticket
  python scripts/agent/usage.py --reset               # start a new log (old one is renamed)

Sources
- workers: `claude -p --output-format json` (modelUsage: input, cache read/write, output, cost, duration);
- reviewers: the Codex session file of each run (~/.codex/sessions/**/rollout-*<session id>.jsonl, last token_count);
- architect (--milestone): the Claude Code transcripts of the control checkout (~/.claude/projects/<dir>/*.jsonl and
  their subagents/), cut to the milestone window. Effort is the `effort` the session recorded.
Milestone window: from the `start` marker that `milestone.py start <M>` writes (else the milestone's first logged
run) to its last logged run, or now. "Tokens" counts input + cached input + output, as the CLIs bill them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import common as c

GAP_MIN = 5  # a pause longer than this does not count as active time


def ts_of(r: dict) -> dt.datetime | None:
    if r.get("ts"):
        return dt.datetime.fromisoformat(r["ts"])
    if r.get("at"):  # older rows: local "YYYY-mm-dd HH:MM"
        return dt.datetime.strptime(r["at"], "%Y-%m-%d %H:%M").astimezone(dt.timezone.utc)
    return None


def milestone_of(r: dict, tickets: dict) -> str | None:
    if r.get("milestone"):
        return str(r["milestone"])
    tid = str(r.get("ticket") or "")
    if tid.endswith("-pr"):
        return tid[:-3]
    t = tickets.get(tid.upper())
    return str(t.meta.get("milestone")) if t else None


def active_minutes(stamps: list[dt.datetime]) -> float:
    stamps = sorted(stamps)
    return sum(min((b - a).total_seconds(), GAP_MIN * 60) for a, b in zip(stamps, stamps[1:])) / 60


def transcript_dir(root: Path) -> Path:
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return home / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", str(root.resolve()))


def architect_usage(root: Path, start: dt.datetime | None, end: dt.datetime | None, skip: set[str]) -> list[dict]:
    """Claude Code sessions of the control checkout (the architect) and their subagents, inside [start, end].
    `skip`: session ids of headless workers that ran in this folder (they are counted from usage.jsonl instead)."""
    base = transcript_dir(root)
    if not base.is_dir():
        return []
    files = [(f, "architect") for f in base.glob("*.jsonl") if f.stem not in skip]
    for f in base.glob("*/subagents/*.jsonl"):
        meta = f.with_suffix(".meta.json")
        kind = "?"
        if meta.exists():
            try:
                kind = json.loads(meta.read_text(encoding="utf-8")).get("agentType", "?")
            except json.JSONDecodeError:
                pass
        files.append((f, f"architect subagent {kind}"))
    rows: dict = {}
    for f, role in files:
        seen, efforts, stamps = set(), Counter(), []
        per_model: dict = defaultdict(Counter)
        for line in f.open(encoding="utf-8", errors="replace"):
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = o.get("timestamp")
            when = dt.datetime.fromisoformat(t.replace("Z", "+00:00")) if t else None
            if when is None or (start and when < start) or (end and when > end):
                continue
            stamps.append(when)
            for e in re.findall(r'"effort":"(\w+)"', line):
                efforts[e] += 1
            m = o.get("message") or {}
            u, mid, model = m.get("usage"), m.get("id"), m.get("model")
            if o.get("type") != "assistant" or not u or mid in seen or model in (None, "<synthetic>"):
                continue
            seen.add(mid)
            k = per_model[model]
            k["calls"] += 1
            k["input"] += int(u.get("input_tokens") or 0)
            k["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
            k["cache_write"] += int(u.get("cache_creation_input_tokens") or 0)
            k["output"] += int(u.get("output_tokens") or 0)
        effort = efforts.most_common(1)[0][0] if efforts else None
        for model, k in per_model.items():
            key = (role, model, effort)
            r = rows.setdefault(key, {"role": role, "model": model, "effort": effort, "runs": 0, "tokens": 0,
                                      "cache_read": 0, "output": 0, "cost": 0.0, "seconds": 0.0, "unknown": 0})
            r["runs"] += 1
            r["tokens"] += k["input"] + k["cache_read"] + k["cache_write"] + k["output"]
            r["cache_read"] += k["cache_read"]
            r["output"] += k["output"]
            r["seconds"] += active_minutes(stamps) * 60 / max(1, len(per_model))
    return list(rows.values())


def summarize(rows: list[dict]) -> list[dict]:
    out: dict = {}
    for r in rows:
        key = (r.get("role"), r.get("model"), r.get("effort"))
        b = out.setdefault(key, {"role": key[0], "model": key[1], "effort": key[2], "runs": 0, "tokens": 0,
                                 "cache_read": 0, "output": 0, "cost": 0.0, "seconds": 0.0, "unknown": 0})
        b["runs"] += 1
        if r.get("tokens") is None:
            b["unknown"] += 1
        else:
            b["tokens"] += int(r["tokens"])
        b["cache_read"] += int(r.get("cache_read") or 0)
        b["output"] += int(r.get("output") or 0)
        b["cost"] += float(r.get("cost_usd") or 0)
        b["seconds"] += float(r.get("seconds") or 0)
    return list(out.values())


def fmt_tokens(n: int) -> str:
    return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.0f}k" if n >= 1e3 else str(n)


def table(rows: list[dict], md: bool) -> list[str]:
    rows = sorted(rows, key=lambda r: -r["tokens"])
    total = sum(r["tokens"] for r in rows)
    head = ["Role", "Model", "Effort", "Runs", "Tokens", "Share", "Cached input", "Output", "Cost $", "Time (min)"]
    body = []
    for r in rows:
        body.append([r["role"], str(r["model"]), r["effort"] or "?", str(r["runs"]),
                     fmt_tokens(r["tokens"]) + (f" (+{r['unknown']} unknown)" if r["unknown"] else ""),
                     f"{100 * r['tokens'] / total:.0f}%" if total else "-", fmt_tokens(r["cache_read"]),
                     fmt_tokens(r["output"]), f"{r['cost']:.2f}" if r["cost"] else "-", f"{r['seconds'] / 60:.1f}"])
    body.append(["**Total**" if md else "total", "", "", str(sum(r["runs"] for r in rows)), fmt_tokens(total), "100%",
                 fmt_tokens(sum(r["cache_read"] for r in rows)), fmt_tokens(sum(r["output"] for r in rows)),
                 f"{sum(r['cost'] for r in rows):.2f}", f"{sum(r['seconds'] for r in rows) / 60:.1f}"])
    if md:
        return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(b) + " |" for b in body]
    widths = [max(len(x[i]) for x in [head] + body) for i in range(len(head))]
    return ["  ".join(x[i].ljust(widths[i]) for i in range(len(head))) for x in [head] + body]


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--milestone")
    ap.add_argument("--no-architect", action="store_true", help="skip the Claude Code transcripts")
    ap.add_argument("--md", action="store_true", help="markdown table")
    ap.add_argument("--write", action="store_true", help="with --milestone: save work/usage/<M>.md")
    ap.add_argument("--tickets", action="store_true")
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    log = c.cfg_path(cfg, "packs", root) / "usage.jsonl"
    if a.reset:
        if log.exists():
            log.rename(log.with_name(f"usage.{c.now().replace(' ', '_').replace(':', '')}.jsonl"))
        print("usage log reset")
        return
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()] if log.exists() else []
    tickets = c.load_tickets(root, cfg, include_archive=True)
    markers = [r for r in rows if r.get("role") == "marker"]
    runs = [r for r in rows if r.get("role") != "marker"]
    start = end = None
    if a.milestone:
        m = a.milestone
        runs = [r for r in runs if milestone_of(r, tickets) == m]

        def mark(event: str, own: bool = True) -> list[dt.datetime]:
            return [x for r in markers if r.get("event") == event and (r.get("milestone") == m) == own
                    and (x := ts_of(r))]
        stamps = [x for x in (ts_of(r) for r in runs) if x]
        start = min(mark("start") or stamps) if (mark("start") or stamps) else None
        if start is not None:
            # end: this milestone's end marker, else the next milestone's start marker, else now
            later = [x for x in mark("start", own=False) if x > start]
            end = max(mark("end")) if mark("end") else min(later) if later else dt.datetime.now(dt.timezone.utc)
        if a.write and not mark("end"):
            c.log_usage(root, cfg, "marker", None, None, milestone=m, event="end")
    if not runs and not a.milestone:
        print("no usage logged yet")
        return
    summary = summarize(runs)
    if a.milestone and not a.no_architect and start is not None:
        summary += architect_usage(root, start, end, {str(r["session"]) for r in rows if r.get("session")})

    lines = []
    if a.milestone:
        wall = f"{(end - start).total_seconds() / 60:.0f} min" if start and end else "?"
        when = (f"{start.astimezone():%Y-%m-%d %H:%M} – {end.astimezone():%H:%M}" if start and end else "unknown window")
        lines.append(f"### Usage for {a.milestone}: {when} local, wall time {wall}")
        lines.append("")
    lines += table(summary, a.md or a.write)
    if a.milestone:
        lines.append("")
        lines.append("Time = summed run time for workers/reviewers, active minutes (gaps > 5 min dropped) for the "
                     "architect. Tokens include cached input.")
    print("\n".join(lines))
    if a.tickets:
        per = defaultdict(lambda: [0, 0])
        for r in runs:
            per[r.get("ticket")][0] += 1
            per[r.get("ticket")][1] += int(r.get("tokens") or 0)
        print()
        for tid, (n, tok) in sorted(per.items(), key=lambda x: -x[1][1]):
            print(f"{tid}: {n} runs, {tok:,} tokens")
    if a.write and a.milestone:
        out = c.cfg_path(cfg, "usage", root) if "usage" in cfg["paths"] else root / "work" / "usage"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{a.milestone}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nwrote {(out / f'{a.milestone}.md').relative_to(root).as_posix()}")


if __name__ == "__main__":
    main()
