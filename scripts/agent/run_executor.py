#!/usr/bin/env python3
"""Prepare and run the executor for one ticket inside its own git worktree (.worktrees/<id>).

The ticket's difficulty picks a tier in .agents/config.json -> executor.tiers; the tier's runner decides:
  runner "claude-cli":      prepare, run headless `claude -p` INSIDE the ticket worktree with the pack on stdin,
                            then finish (gates). Default.
  runner "aider":           prepare, run Aider with the tier's model, then finish automatically.
  runner "claude-subagent": prepare only; the architect spawns subagent executor-<tier>,
                            which ends with:  run_executor.py <id> --finish

Tests first (executor.tdd, on by default; a ticket opts out with `tdd: false`):
  the worker writes only the tests, runs  run_executor.py <id> --red  (commits them and checks they FAIL
  without the implementation), and only then implements. --finish runs the same check itself if the worker
  skipped --red, and records that the order was wrong, so the reviewer sees it.

Exit codes: 0 in_review (or red step passed) · 1 gates failed (stays in_progress) · 2 blocked · 5 usage/rate limit.

  python scripts/agent/run_executor.py T-0007            # prepare (and run the worker unless claude-subagent)
  python scripts/agent/run_executor.py T-0007 --red      # TDD: commit the new tests and prove they fail
  python scripts/agent/run_executor.py T-0007 --finish   # auto-fix, commit leftovers, run gates, -> in_review
  python scripts/agent/run_executor.py T-0007 --dry-run  # show what would happen
  options: --model <override>  --prepare-only  --force

Local models via Aider: start the server with a big enough window, e.g.
  OLLAMA_CONTEXT_LENGTH=16384 ollama serve        (Ollama's default on <24 GB VRAM is only 4k)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import common as c
import pack as packmod

HERE = Path(__file__).resolve().parent


def worktree_of(t: c.Ticket, root: Path, cfg: dict) -> Path:
    return (root / cfg["git"]["worktree_dir"] / t.id).resolve()


def ensure_worktree(t: c.Ticket, root: Path, cfg: dict, dry: bool) -> tuple[Path, str]:
    g = cfg["git"]
    base = t.meta.get("base")
    if not base:
        ib = g["integration_branch_prefix"] + str(t.meta.get("milestone"))
        base = ib if c.branch_exists(ib, root) else c.current_branch(root)
    wt = worktree_of(t, root, cfg)
    branch = g["ticket_branch_prefix"] + t.id
    if dry:
        return wt, str(base)
    if not wt.exists():
        wt.parent.mkdir(parents=True, exist_ok=True)
        if c.branch_exists(branch, root):
            c.git(["worktree", "add", str(wt), branch], cwd=root)
        else:
            c.git(["worktree", "add", str(wt), "-b", branch, str(base)], cwd=root)
        print(f"worktree: {wt} (branch {branch} from {base})")
    else:
        print(f"worktree: {wt} (exists)")
        if t.status == "ready":  # e.g. sent back by integrate.py after a merge conflict
            r = c.run(["git", "rebase", str(base)], cwd=wt, check=False)
            if r.returncode != 0:
                c.run(["git", "rebase", "--abort"], cwd=wt, check=False)
                c.set_status(t, "blocked", by="run_executor", note=f"rebase onto {base} failed; architect must resolve")
                sys.exit(f"error: rebase of {branch} onto {base} failed. Ticket set to blocked.\n{c.tail(r.stdout + r.stderr, 15)}")
            print(f"rebased {branch} onto {base}")
    return wt, str(base)


# --------------------------------------------------------------------------- helpers

def changed_files(wt: Path, base: str) -> list[str]:
    """Files changed in the worktree since base: committed, staged, unstaged and untracked."""
    out = set(c.git(["diff", "--name-only", f"{base}...HEAD"], cwd=wt, check=False).split("\n"))
    for ln in c.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=wt).stdout.split("\n"):
        if ln.strip():
            p = ln[3:].strip().strip('"')
            out.add(p.split(" -> ")[-1])
    return sorted(c.norm(p) for p in out if p.strip())


def run_fixers(t: c.Ticket, wt: Path, base: str, cfg: dict) -> None:
    """verify.fix_commands (formatters, lint --fix) on the ticket's changed files, before any gate runs.
    A formatting slip then never costs a whole worker run. Fixer failures are ignored: the gates report them."""
    cmds = [x for x in cfg.get("verify", {}).get("fix_commands", []) if x]
    if not cmds:
        return
    owned = t.get_list("files_owned")
    files = [f for f in changed_files(wt, base)
             if c.matches(f, owned) and not c.is_generated(f, cfg) and (wt / f).is_file()]
    quoted = " ".join(subprocess.list2cmdline([f]) for f in files)
    for cmd in cmds:
        if "{files}" in cmd:
            if not files:
                continue
            cmd = cmd.replace("{files}", quoted)
        r = subprocess.run(cmd, shell=True, cwd=wt, text=True, capture_output=True, encoding="utf-8", errors="replace")
        print(f"fix  {cmd[:100]}{'' if r.returncode == 0 else f'  (exit {r.returncode}, ignored)'}", flush=True)


def ticket_verify(t: c.Ticket, wt: Path) -> tuple[bool, str]:
    """Run only the ticket's own verify commands. Returns [(command, passed, output tail)]."""
    results = []
    for cmd in t.get_list("verify"):
        r = subprocess.run(cmd, shell=True, cwd=wt, text=True, capture_output=True, encoding="utf-8", errors="replace")
        out = f"$ {cmd}  (exit {r.returncode})\n{c.tail((r.stdout or '') + (r.stderr or ''), 25)}"
        results.append((cmd, r.returncode == 0, out))
    return results


def is_test_command(cmd: str, tests: list[str], cfg: dict) -> bool:
    """A verify command counts for the red step only if it runs tests: it matches executor.tdd.test_command_patterns
    (pytest, unittest, cargo test, npm test, ...), or it runs one of the ticket's test files directly with an
    interpreter (`python tests/test_x.py`). A lint or format check failing never counts as a red test, even when it
    names a test file (`ruff check tests/test_x.py`)."""
    pats = cfg.get("executor", {}).get("tdd", {}).get("test_command_patterns", [])
    if any(re.search(p, cmd) for p in pats):
        return True
    norm = cmd.replace("\\", "/")
    return any(re.search(rf"\b(python3?|node|deno|bun|ruby)\s+(\S+/)?{re.escape(f)}\b", norm) for f in tests)


@contextmanager
def without(files: list[str], wt: Path, base: str):
    """Temporarily put `files` back to their content at `base` (deleting files that are new), then restore them.
    Every file is backed up BEFORE anything in the worktree changes, and only files that were actually changed are
    restored, so a failed backup can never delete uncommitted work.
    No git stash: the stash stack is shared by every worktree, so parallel workers would collide."""
    tmp = Path(tempfile.mkdtemp(prefix="agent-red-"))
    existed: set[str] = set()
    touched: list[str] = []
    try:
        for f in files:  # 1. back up everything first; an error here leaves the worktree untouched
            p = wt / f
            if p.is_file():
                (tmp / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, tmp / f)
                existed.add(f)
        for f in files:  # 2. only now change the worktree
            p = wt / f
            r = subprocess.run(["git", "show", f"{base}:{f}"], cwd=wt, capture_output=True)
            touched.append(f)
            if r.returncode == 0:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(r.stdout)
            elif p.exists():
                p.unlink()
        yield
    finally:
        for f in touched:
            p = wt / f
            if f in existed:
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(tmp / f, p)
            elif p.exists():
                p.unlink()
        if len(touched) == len(files):
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print(f"warning: red-step backups kept in {tmp}", file=sys.stderr)


def red_check(t: c.Ticket, root: Path, cfg: dict, wt: Path, base: str, by: str) -> bool:
    """TDD red step: commit the ticket's test changes, then run its verify commands with every NON-test change
    reverted to base. At least one must fail, otherwise the tests do not test the new behavior."""
    changed = [f for f in changed_files(wt, base) if not c.is_generated(f, cfg)]
    tests = [f for f in changed if c.is_test_file(f, cfg)]
    impl = [f for f in changed if not c.is_test_file(f, cfg)]
    if not tests:
        msg = ("TDD red step: no test file changed yet. Write the tests first (test files in files_owned that match "
               f"executor.tdd.test_globs), then run: python scripts/agent/run_executor.py {t.id} --red")
        c.update_gate(t.id, root, cfg, "red", False, msg)
        print(msg)
        return False
    run_fixers(t, wt, base, cfg)
    c.git(["add", "--", *tests], cwd=wt)
    if c.run(["git", "diff", "--cached", "--quiet"], cwd=wt, check=False).returncode != 0:
        c.git(["commit", "-m", f"{t.id}: tests first (red)"], cwd=wt)
    commit = c.head_sha(wt, short=False)
    test_cmds = [x for x in t.get_list("verify") if is_test_command(x, tests, cfg)]
    if not test_cmds:
        msg = ("TDD red step: none of the ticket's verify commands runs tests (it must name a test file or match "
               "executor.tdd.test_command_patterns), so a red test cannot be proven. The architect must add a test "
               "command to the ticket's verify list.")
        c.update_gate(t.id, root, cfg, "red", False, msg, commit=commit)
        print(msg)
        return False
    with without(impl, wt, base):
        results = ticket_verify(t, wt)
    failing = [out for cmd, ok, out in results if not ok and cmd in test_cmds]
    fail_out = "\n\n".join(failing)
    order = "first" if not impl else "late"
    if not failing:
        others = [cmd for cmd, ok, _ in results if not ok]
        msg = ("TDD red step failed: the ticket's TEST commands PASS without the implementation, so the tests do "
               "not test the new behavior"
               + (f" (only non-test checks failed: {', '.join(others)})" if others else "")
               + ". Make them assert what the Acceptance criteria require, then run --red again.")
        c.update_gate(t.id, root, cfg, "red", False, msg, commit=commit)
        print(msg)
        return False
    note = "" if order == "first" else (f" Order: late ({by}) — implementation files were already changed: "
                                         + ", ".join(impl[:5]))
    c.update_gate(t.id, root, cfg, "red", True, c.tail(fail_out, 15), commit=commit, order=order, tests=tests)
    print(f"red OK: tests committed at {commit[:9]} and failing without the implementation.{note}")
    print(c.tail(fail_out, 8))
    return True


def finish(t: c.Ticket, root: Path, cfg: dict, base_hint) -> None:
    """Auto-fix, TDD check, commit leftovers in the ticket worktree, run gates, move to in_review on success."""
    wt = worktree_of(t, root, cfg)
    if not wt.exists():
        sys.exit(f"error: worktree {wt} does not exist; run without --finish first")
    base = str(base_hint or t.meta.get("base") or cfg["git"]["default_base"])
    if c.tdd_on(t, cfg) and packmod._gate(t.id, root, cfg).get("red", {}).get("result") != "pass":
        print("TDD: no red step recorded; checking that the tests fail without the implementation")
        if not red_check(t, root, cfg, wt, base, by="checked by --finish"):
            sys.exit(1)
    run_fixers(t, wt, base, cfg)
    if c.run(["git", "status", "--porcelain"], cwd=wt).stdout.strip():
        c.git(["add", "-A"], cwd=wt)
        c.git(["commit", "-m", f"{t.id}: executor changes"], cwd=wt, check=False)
    py = sys.executable
    v = subprocess.run([py, str(HERE / "verify.py"), t.id, "--cwd", str(wt)])
    o = subprocess.run([py, str(HERE / "owned_diff.py"), t.id, "--cwd", str(wt), "--base", base])
    if v.returncode == 0 and o.returncode == 0:
        cur = c.find_ticket(t.id, root, cfg)
        if cur.status != "in_review":
            c.set_status(cur, "in_review", by="run_executor", note="gates passed")
        print(f"\n{t.id} -> in_review. Next: python scripts/agent/run_review.py {t.id}")
    else:
        print(f"\n{t.id} gates failed; status stays in_progress. Fix and run --finish again "
              f"(the failure is in the next pack), or set it blocked.")
        sys.exit(1)


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id")
    ap.add_argument("--model")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prepare-only", action="store_true")
    ap.add_argument("--finish", action="store_true",
                    help="after a subagent/manual executor: auto-fix, commit, run gates, set in_review")
    ap.add_argument("--red", action="store_true", help="TDD: commit the new tests and check that they fail")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    tickets = c.load_tickets(root, cfg, include_archive=True)
    t = c.find_ticket(a.id, root, cfg)

    if a.red:
        wt = worktree_of(t, root, cfg)
        if not c.tdd_on(t, cfg):
            sys.exit(f"{t.id}: tests-first is off for this ticket (executor.tdd / ticket tdd: false); just implement")
        if not wt.exists():
            sys.exit(f"error: worktree {wt} does not exist; run without --red first")
        base = str(t.meta.get("base") or cfg["git"]["default_base"])
        sys.exit(0 if red_check(t, root, cfg, wt, base, by="--red after implementation") else 1)

    if t.status not in ("ready", "changes_requested", "in_progress") and not a.force:
        sys.exit(f"error: {t.id} is '{t.status}'; executor needs ready, changes_requested or in_progress")
    ok, missing = c.deps_satisfied(t, tickets)
    if not ok and not a.force:
        sys.exit(f"error: {t.id} waits on {', '.join(missing)}")
    tier_name, tier = c.tier_of(t, cfg)
    runner = tier.get("runner", "claude-subagent")
    model = a.model or tier.get("model")
    prepare_only = a.prepare_only or runner == "claude-subagent"
    if a.finish:
        finish(t, root, cfg, base_hint=t.meta.get("base"))
        return

    wt, base = ensure_worktree(t, root, cfg, a.dry_run)
    harness_adds_owned = not prepare_only and runner == "aider"
    # budget check first, so an oversized ticket is rejected before its status changes
    _, tokens, _ = packmod.build(t.id, cwd=wt if wt.exists() else root,
                                 include_owned=not harness_adds_owned, out=False, force=a.force)
    if not a.dry_run:
        updates = {"base": base} if not t.meta.get("base") else {}
        if updates:
            t = c.save_ticket(t, updates)
        if t.status != "in_progress":
            t = c.set_status(t, "in_progress", by="run_executor", note=f"tier {tier_name}, {runner} {model}")
    _, tokens, pack_path = packmod.build(t.id, cwd=wt if wt.exists() else root,
                                         include_owned=not harness_adds_owned, out=not a.dry_run, force=True)
    print(f"pack: {pack_path or '(dry run)'} ~{tokens} tokens (budget {packmod.budget_for(t, cfg)})")
    if prepare_only:
        rel_wt = wt.relative_to(root).as_posix() if wt.is_relative_to(root) else str(wt)
        rel_pack = pack_path.relative_to(root).as_posix() if pack_path else f"work/.pack/{t.id}.md"
        print(f"\nPrepared {t.id} (tier {tier_name}: {runner}, model {model}).")
        print(f"  worktree: {rel_wt}")
        print(f"  pack:     {rel_pack}")
        if runner == "claude-subagent":
            print(f"  spawn subagent: executor-{tier_name.lower()}  with prompt: \"Implement {t.id}\"")
        if c.tdd_on(t, cfg):
            print(f"  tests first: python scripts/agent/run_executor.py {t.id} --red")
        print(f"  finish:   python scripts/agent/run_executor.py {t.id} --finish")
        return

    if runner == "claude-cli":
        run_claude_cli(t, root, cfg, wt, base, tier, model, pack_path, a.dry_run)
        return

    owned = [f for f in t.get_list("files_owned") if "*" not in f and not c.is_generated(f, cfg)]
    py = sys.executable
    test_cmd = f'"{py}" "{HERE / "verify.py"}" {t.id} --cwd "{wt}" --ticket-only'
    ex = cfg["executor"].get("aider", {})
    cmd = ["aider", "--model", str(model), "--map-tokens", str(ex.get("map_tokens", 512)),
           "--read", str(pack_path or "work/.pack/" + t.id + ".md")]
    for f in owned:
        cmd += ["--file", f]
    cmd += ["--test-cmd", test_cmd, "--auto-test", "--yes-always",
            "--message", f"Implement ticket {t.id} exactly as described in the context pack. "
                         f"Edit only the files you own. If blocked, reply with 'BLOCKED: <reason>'."]
    cmd += list(ex.get("extra_args", []))

    if a.dry_run:
        print("\n(dry run) would run in", wt)
        print(subprocess.list2cmdline(cmd))
        return
    if shutil.which("aider") is None:
        sys.exit("error: aider not found on PATH (pip install aider-chat, or set the tier runner to claude-subagent)")

    for f in owned:  # make sure new files exist so the harness can add them
        p = wt / f
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()

    hist = wt / ".aider.chat.history.md"
    hist_before = hist.stat().st_size if hist.exists() else 0
    started = time.monotonic()
    subprocess.run(cmd, cwd=wt)  # streams aider's output to the terminal
    c.log_usage(root, cfg, "executor", t.id, str(model), milestone=t.meta.get("milestone"), runner="aider",
                seconds=round(time.monotonic() - started))
    new_hist = ""
    if hist.exists():
        with hist.open(encoding="utf-8", errors="replace") as fh:
            fh.seek(hist_before)
            new_hist = fh.read()
    blocked = next((ln.strip() for ln in new_hist.split("\n") if ln.strip().startswith("BLOCKED:")), None)

    if blocked:
        c.set_status(c.find_ticket(t.id, root, cfg), "blocked", by="executor", note=blocked)
        print(f"{t.id} blocked: {blocked}")
        sys.exit(2)
    finish(t, root, cfg, base_hint=base)


WORKER_PROMPT = """You are the executor for ticket {id}. Your complete context pack is below: your rules, the ticket,
the contracts, the CURRENT content of the files you own, and any review findings or gate failures to fix.
- Your working directory is the ticket's own git worktree. Every path in the pack is relative to it: use plain
  relative paths, never `cd`, and run each command on its own (no `&&` chains).
- Do not re-read the owned files and do not explore the repo; the pack is the context.
- Edit only the ticket's files_owned. Lock/generated files are listed by name only: never read or hand-edit them.
{tdd}- Check your work with: python scripts/agent/verify.py {id} --ticket-only
  (formatters run automatically before the final gates; you do not need to run them).
- Need another file, or the contract is wrong? Run
  python scripts/agent/ticket.py status {id} blocked --by executor --note "<reason>"   and stop.
- Do not commit. When verify passes, stop and reply with one line: DONE.

{pack}
"""

TDD_LINE = """- Tests first: write ONLY the tests, then run  python scripts/agent/run_executor.py {id} --red
  It commits them and must report them failing. Only after that write the implementation.
"""


def allowed_tools(cc: dict) -> str | None:
    """--allowedTools value: the command's list + extra_allowed_tools; for every Bash(<cmd>:*) the same command behind
    each command_prefixes entry (e.g. Bash(rtk uv:*)), never a bare Bash(rtk:*), which would allow anything; and every
    Bash rule again for each shell tool in mirror_shells (e.g. PowerShell(uv:*), which Windows workers reach for)."""
    cmd = cc.get("command", [])
    if "--allowedTools" not in cmd or cmd.index("--allowedTools") + 1 >= len(cmd):
        return None
    items = [x for x in cmd[cmd.index("--allowedTools") + 1].split(",") if x]
    items += [x for x in cc.get("extra_allowed_tools", []) if x and x not in items]
    out = list(items)
    for pre in [p.strip() for p in cc.get("command_prefixes", []) if p and p.strip()]:
        for it in items:
            m = re.fullmatch(r"Bash\((.+)\)", it)
            if m and not m.group(1).startswith(pre + " "):
                v = f"Bash({pre} {m.group(1)})"
                if v not in out:
                    out.append(v)
    for shell in [s.strip() for s in cc.get("mirror_shells", []) if s and s.strip()]:
        for it in list(out):
            m = re.fullmatch(r"Bash\((.+)\)", it)
            if m and f"{shell}({m.group(1)})" not in out:
                out.append(f"{shell}({m.group(1)})")
    return ",".join(out)


def run_claude_cli(t, root, cfg, wt, base, tier, model, pack_path, dry):
    """Headless worker: `claude -p` started INSIDE the ticket worktree, pack on stdin, then the deterministic gates."""
    cc = cfg["executor"].get("claude_cli", {})
    pack_text = pack_path.read_text(encoding="utf-8") if pack_path else "(dry run: pack not written)"
    tdd = TDD_LINE.format(id=t.id) if c.tdd_on(t, cfg) and \
        packmod._gate(t.id, root, cfg).get("red", {}).get("result") != "pass" else ""
    prompt = WORKER_PROMPT.format(id=t.id, tdd=tdd, pack=pack_text)
    effort = str(tier.get("effort") or "")
    subst = {"{model}": str(model), "{max_turns}": str(tier.get("max_turns", 30)), "{effort}": effort}
    cmd, via_stdin = [], True
    for part in cc.get("command", []):
        if part == "{prompt}":
            cmd.append(prompt)
            via_stdin = False
            continue
        if any(k in part and not v for k, v in subst.items()):  # empty value: drop it and its flag
            if cmd and cmd[-1].startswith("-"):
                cmd.pop()
            continue
        for k, v in subst.items():
            part = part.replace(k, v)
        cmd.append(part)
    tools = allowed_tools(cc)
    if tools and "--allowedTools" in cmd:
        cmd[cmd.index("--allowedTools") + 1] = tools
    if cc.get("prompt_via") == "stdin" and not via_stdin:
        cmd = [x for x in cmd if x != prompt]
        via_stdin = True
    if dry:
        print("(dry run) would run in", wt)
        print(subprocess.list2cmdline([x if x != prompt else "<prompt>" for x in cmd])
              + ("   < prompt on stdin" if via_stdin else ""))
        return
    exe = shutil.which(cmd[0]) if cmd else None
    if exe is None:
        sys.exit(f"error: worker executable '{cmd[0] if cmd else '?'}' not found (executor.claude_cli.command)")
    cmd[0] = exe
    print(f"worker {t.id}: {Path(cmd[0]).name} model={model} effort={effort or 'default'} "
          f"max_turns={tier.get('max_turns')} cwd={wt.name}", flush=True)
    log = c.cfg_path(cfg, "packs", root) / f"{t.id}.worker.log"
    env = {**os.environ, "AGENT_TICKET": t.id, "AGENT_CONTROL_ROOT": str(root)}
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=wt, env=env, input=prompt if via_stdin else None, text=True,
                              capture_output=True, encoding="utf-8", errors="replace",
                              timeout=int(cc.get("timeout_seconds", 1800)))
        out, code = proc.stdout or "", proc.returncode
        err = proc.stderr or ""
    except subprocess.TimeoutExpired as e:
        out, code, err = "", 124, f"TIMEOUT after {e.timeout}s"
    seconds = round(time.monotonic() - started)
    log.write_text(out + "\n--- stderr ---\n" + err, encoding="utf-8")

    usage: dict = {}
    cost = turns = None
    result_text = out
    try:
        data = json.loads(out)
        usage = c.claude_usage(data)
        cost, turns = data.get("total_cost_usd"), data.get("num_turns")
        result_text = str(data.get("result") or "")
        usage["session"] = data.get("session_id")
        denied = data.get("permission_denials") or []
        if denied:
            usage["denied"] = len(denied)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    models = usage.pop("models", None)
    c.log_usage(root, cfg, "executor", t.id, ",".join(models) if models else str(model), cost_usd=cost, turns=turns,
                milestone=t.meta.get("milestone"), tier=t.meta.get("difficulty"), effort=effort or None,
                seconds=seconds, **usage)

    low = (result_text + err).lower()
    if code != 0 and any(p in low for p in cfg.get("reviewer", {}).get("limit_patterns", [])):
        print(f"{t.id}: worker hit a usage/rate limit; ticket stays in_progress. Log: {log.relative_to(root).as_posix()}")
        sys.exit(5)
    cur = c.find_ticket(t.id, root, cfg)
    if cur.status == "blocked":
        sys.exit(2)
    blocked = next((ln.strip() for ln in result_text.split("\n") if ln.strip().startswith("BLOCKED:")), None)
    if blocked:
        c.set_status(cur, "blocked", by="executor", note=blocked)
        sys.exit(2)
    finish(cur, root, cfg, base_hint=base)


if __name__ == "__main__":
    main()
