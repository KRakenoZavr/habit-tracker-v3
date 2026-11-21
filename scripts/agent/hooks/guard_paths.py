#!/usr/bin/env python3
"""Claude Code PreToolUse hook.

  guard_paths.py write  — block edits to protected_globs; if AGENT_TICKET=T-xxxx is set,
                          also block edits outside that ticket's files_owned.
  guard_paths.py read   — block every Read of lock/generated files (generated_globs in config: agents see
                          their names, not their content), and whole-file reads of huge files in read_guard
                          (reads with offset/limit are allowed there).

Bypass for one session (human-approved edits to AGENTS.md etc.): set AGENT_ALLOW_PROTECTED=1;
to read generated files: AGENT_ALLOW_GENERATED=1.
Exit code 2 = block; the message on stderr is shown to the agent.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as c  # noqa: E402


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "write"
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    ti = event.get("tool_input") or {}
    raw = ti.get("file_path") or ti.get("notebook_path")
    if not raw:
        sys.exit(0)
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()).resolve()
    path = Path(raw)
    path = path if path.is_absolute() else (project / path)
    try:
        rel = path.resolve().relative_to(project).as_posix()
    except ValueError:
        sys.exit(0)  # outside the project: not our business
    root = c.control_root()
    cfg = c.load_config(root)

    if mode == "read":
        rg = cfg.get("read_guard") or {}
        wt_prefix = c.norm(cfg["git"]["worktree_dir"]).rstrip("/") + "/"
        inner = rel.split("/", 2)[-1] if rel.startswith(wt_prefix) and rel.count("/") >= 2 else rel
        if c.is_generated(inner, cfg) and os.environ.get("AGENT_ALLOW_GENERATED") != "1":
            size = f"{path.stat().st_size} bytes" if path.is_file() else "missing"
            print(f"Blocked: {inner} is a lock/generated file ({size}; .agents/config.json generated_globs). "
                  f"Agents see its name, not its content: change it only with its tool (see AGENTS.md Commands). "
                  f"Need one fact from it? Grep for that line.", file=sys.stderr)
            sys.exit(2)
        if ti.get("limit") or ti.get("offset"):
            sys.exit(0)
        if c.matches(rel, rg.get("globs", [])) and path.is_file() and path.stat().st_size > rg.get("max_bytes", 32768):
            print(f"Blocked: {rel} is {path.stat().st_size} bytes of generated data. "
                  f"Use Grep to find the lines you need, then Read with offset/limit.", file=sys.stderr)
            sys.exit(2)
        sys.exit(0)

    # Edits inside a ticket worktree (.worktrees/<id>/...) are checked against THAT ticket.
    tid = os.environ.get("AGENT_TICKET")
    wt_prefix = c.norm(cfg["git"]["worktree_dir"]).rstrip("/") + "/"
    if rel.startswith(wt_prefix):
        parts = rel[len(wt_prefix):].split("/", 1)
        tid, rel = parts[0], (parts[1] if len(parts) > 1 else "")

    if os.environ.get("AGENT_ALLOW_PROTECTED") == "1":
        sys.exit(0)
    if c.matches(rel, cfg.get("protected_globs", [])):
        print(f"Blocked: {rel} is protected (.agents/config.json protected_globs). "
              f"Propose the change in your report instead.", file=sys.stderr)
        sys.exit(2)
    if tid:
        try:
            t = c.find_ticket(tid, root, cfg)
        except SystemExit:
            print(f"Blocked: no ticket {tid} for this worktree path.", file=sys.stderr)
            sys.exit(2)
        if not c.matches(rel, t.get_list("files_owned")):
            print(f"Blocked: {rel} is not in {t.id} files_owned. Set the ticket to blocked if you need it.",
                  file=sys.stderr)
            sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
