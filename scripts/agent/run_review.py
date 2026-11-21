#!/usr/bin/env python3
"""Review one ticket with the configured reviewer CLI (default: Codex, headless, read-only).

  python scripts/agent/run_review.py T-0007            # review a ticket in status in_review
  python scripts/agent/run_review.py T-0007 --dry-run  # show packet size, effort and command

Token-saving design:
- The whole review packet (ticket, gate results, diff, contracts, previous findings) is sent IN the prompt.
  The reviewer runs read-only and only answers, so it has no reason to explore the repo.
- Re-reviews send only the changes since the previous review plus the previous findings.
- Lock/generated files (generated_globs) are listed with their line counts but their content is not sent;
  the diff is capped (reviewer.max_diff_lines).
- Effort: reviewer.effort.default (medium); high on the last round or after an escalation.
- Model: reviewer.model for normal tickets (default: the fast model, for S/M); tickets whose difficulty is in
  reviewer.hard.difficulties (default L) use reviewer.hard.model (the strongest) and reviewer.hard.effort if set.
  An empty model means the CLI's own default (~/.codex/config.toml), i.e. every review on one model.
- Usage (tokens incl. cached input, time) is read from the Codex session file and logged to work/.pack/usage.jsonl.
- Optional auto-approve policy for tiny diffs (reviewer.auto_approve, off by default).

The script writes work/reviews/<id>.r<N>.md and applies the verdict.
Exit codes: 0 approved · 3 changes_requested · 4 escalated · 5 usage/rate limit (nothing changed) · 1 error.
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

EXIT = {"approved": 0, "changes_requested": 3, "escalated": 4}
LIMIT_EXIT = 5


def parse_answer(answer: str) -> tuple[str | None, str]:
    """Return (verdict, body) from the reviewer's reply."""
    m = re.search(r"^---\s*\n(.*?)\n---\s*\n?", answer, flags=re.S | re.M)
    verdict, body = None, answer.strip()
    if m:
        meta = c.parse_frontmatter(m.group(1) + "\n")
        verdict = meta.get("verdict")
        body = answer[m.end():].strip()
    if verdict not in EXIT:
        m2 = re.search(r"verdict\s*[:=]\s*\**\s*(approved|changes_requested|escalated)", answer, flags=re.I)
        verdict = m2.group(1).lower() if m2 else None
    return verdict, body


def gates_passed(tid: str, root, cfg) -> bool:
    gf = c.gate_file(tid, root, cfg)
    if not gf.exists():
        return False
    data = json.loads(gf.read_text(encoding="utf-8"))
    return all(data.get(k, {}).get("result") == "pass" for k in ("verify", "owned_diff"))


def write_review(path, tid, rnd, verdict, reviewer, commit, gates_ok, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"ticket: {tid}\nround: {rnd}\nverdict: {verdict}\nreviewer: {json.dumps(reviewer)}\n"
        f"reviewed_commit: {commit or 'none'}\ngates: {'pass' if gates_ok else 'fail'}\n"
        "---\n" + body.strip() + "\n", encoding="utf-8")


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    rv = cfg.get("reviewer", {})
    t = c.find_ticket(a.id, root, cfg)
    if t.status != "in_review" and not a.force:
        sys.exit(f"error: {t.id} is '{t.status}'; only in_review tickets are reviewed")

    rnd = int(t.meta.get("review_round") or 0) + 1
    max_r = c.max_rounds(t, cfg)
    review_path = c.cfg_path(cfg, "reviews", root) / f"{t.id}.r{rnd}.md"
    meta = packmod.review_meta(t, root, cfg)
    gates_ok = gates_passed(t.id, root, cfg)
    tier_name, _ = c.tier_of(t, cfg)

    # 1. auto-approve policy (no LLM call)
    aa = rv.get("auto_approve", {})
    if (aa.get("enabled") and rnd == 1 and gates_ok and tier_name in aa.get("tiers", [])
            and meta["changed_lines"] <= int(aa.get("max_changed_lines", 0))):
        if a.dry_run:
            print(f"(dry run) would auto-approve: {meta['changed_lines']} changed lines, gates passed")
            return
        write_review(review_path, t.id, rnd, "approved", "auto-approve policy", meta["head"], gates_ok,
                     f"Auto-approved: {meta['changed_lines']} changed lines, all gates passed (reviewer.auto_approve).")
        c.set_status(t, "approved", by="run_review", note="auto-approve policy")
        print(f"{t.id}: approved (auto, {meta['changed_lines']} lines)")
        sys.exit(0)

    # 2. effort
    eff = rv.get("effort", {})
    effort = eff.get("default", "medium")
    if rnd >= max_r:
        effort = eff.get("last_round", effort)
    elif "-> escalated" in t.raw:
        effort = eff.get("escalated_before", effort)

    # 3. prompt + command
    packet, tokens, pack_path = packmod.build(t.id, review=True, out=not a.dry_run)
    last = ("\nThis is the LAST allowed round: your verdict must be approved or escalated.\n" if rnd >= max_r else "")
    prompt = (f"You are the code reviewer for ticket {t.id}. Everything you need is below. Do not open files or run "
              f"commands; answer only from this packet.{last}\n\n{packet}")
    out_file = c.cfg_path(cfg, "packs", root) / f"{t.id}.review.answer.md"
    hard = c.is_hard_ticket(t, cfg)
    cmd, model, effort = c.reviewer_command(cfg, prompt, effort, str(out_file), hard=hard)
    via_stdin = rv.get("prompt_via", "stdin") == "stdin"
    if not cmd:
        sys.exit("error: reviewer.command is empty in .agents/config.json")
    if a.dry_run:
        shown = [x if x != prompt else "<prompt>" for x in cmd]
        print(f"(dry run) round {rnd}/{max_r}, model {model or '(default)'}{' (hard)' if hard else ''}, effort {effort}, packet ~{tokens} tokens, diff {meta['changed_lines']} lines")
        print(subprocess.list2cmdline(shown) + ("   < prompt on stdin" if via_stdin else ""))
        return
    exe = shutil.which(cmd[0])
    if exe is None:
        sys.exit(f"error: reviewer executable '{cmd[0]}' not found on PATH (reviewer.command in .agents/config.json)")
    cmd[0] = exe
    if out_file.exists():
        out_file.unlink()

    print(f"review {t.id} r{rnd}/{max_r} model={model or 'default'} effort={effort} packet~{tokens}tok", flush=True)
    log = c.cfg_path(cfg, "packs", root) / f"{t.id}.review.log"
    started = time.monotonic()
    stdout = ""
    try:
        proc = subprocess.run(cmd, cwd=root, input=prompt if via_stdin else None, text=True, capture_output=True,
                              encoding="utf-8", errors="replace", timeout=int(rv.get("timeout_seconds", 600)))
        out, code, stdout = (proc.stdout or "") + "\n" + (proc.stderr or ""), proc.returncode, proc.stdout or ""
    except subprocess.TimeoutExpired as e:
        out, code = f"TIMEOUT after {e.timeout}s", 124
    seconds = round(time.monotonic() - started)
    log.write_text(out, encoding="utf-8")
    answer = out_file.read_text(encoding="utf-8") if out_file.exists() and out_file.stat().st_size else stdout
    verdict, body = parse_answer(answer or "")
    usage = c.codex_usage(out)
    used = usage.get("tokens")
    c.log_usage(root, cfg, "reviewer", t.id, f"{rv.get('command', ['?'])[0]}:{model or 'default'}", effort=effort,
                packet_tokens=tokens, round=rnd, milestone=t.meta.get("milestone"), tier=tier_name,
                seconds=seconds, **usage)

    # 4. limits / failures: change nothing, let the loop pause
    if verdict is None:
        if c.reviewer_unavailable(cfg, out):
            print(f"{t.id}: reviewer hit a usage/rate limit; nothing changed. Log: {log.relative_to(root).as_posix()}")
            sys.exit(LIMIT_EXIT)
        print(c.tail(out, 20))
        sys.exit(f"error: no verdict in the reviewer's answer for {t.id} (exit {code}). Log: {log.relative_to(root).as_posix()}")

    note = ""
    if verdict == "changes_requested" and rnd >= max_r:
        verdict, note = "escalated", "last round: changes_requested turned into escalated"
    write_review(review_path, t.id, rnd, verdict, f"{rv['command'][0]} {model or 'default'} ({effort})", meta["head"], gates_ok,
                 body + (f"\n\n> {note}" if note else ""))
    c.set_status(c.find_ticket(t.id, root, cfg), verdict, by="run_review", note=note or f"round {rnd}")
    print(f"{t.id}: {verdict} (r{rnd}/{max_r}{', ~' + str(used) + ' tok' if used else ''}) -> {review_path.relative_to(root).as_posix()}")
    sys.exit(EXIT[verdict])


if __name__ == "__main__":
    main()
