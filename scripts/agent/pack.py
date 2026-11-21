#!/usr/bin/env python3
"""Build a context pack: everything one agent needs for one ticket, within a token budget.

Executor pack (default):  role prompt + ticket + files_read + owned files + last review + last gate failure
Review pack (--review):   reviewer role + ticket + gate results + diff vs base + files_read + previous review

  python scripts/agent/pack.py T-0007                 > stdout
  python scripts/agent/pack.py T-0007 --out           writes work/.pack/T-0007.md
  python scripts/agent/pack.py T-0007 --review --out  writes work/.pack/T-0007.review.md
  options: --cwd <worktree> (read owned files from there), --no-owned (harness adds them itself), --force
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import common as c

LANG = {".py": "python", ".pyi": "python", ".rs": "rust", ".cs": "csharp", ".ts": "ts", ".tsx": "tsx",
        ".js": "js", ".h": "cpp", ".hpp": "cpp", ".cpp": "cpp", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".mmd": "mermaid", ".md": "markdown", ".toml": "toml"}


def fence(path: str, text: str) -> str:
    lang = LANG.get(Path(path).suffix, "")
    ticks = "````" if "```" in text else "```"
    return f"### {path}\n{ticks}{lang}\n{text.rstrip()}\n{ticks}\n"


def strip_comments_md(text: str) -> str:
    import re
    return re.sub(r"<!--.*?-->\n?", "", text, flags=re.S)


def budget_for(t: c.Ticket, cfg: dict) -> int:
    return c.pack_budget(t, cfg)


def base_of(t: c.Ticket, cfg: dict, root: Path) -> str:
    base = t.meta.get("base")
    if base:
        return str(base)
    ib = cfg["git"]["integration_branch_prefix"] + str(t.meta.get("milestone"))
    return ib if c.branch_exists(ib, root) else cfg["git"]["default_base"]


def generated_note(path: str, p: Path) -> str:
    """Name and size only: lock files and other generated files never go into a pack."""
    size = f"{p.stat().st_size / 1024:.0f} KB" if p.is_file() else "not created yet"
    return (f"### {path}\n(generated file, {size}: content not shown. Change it only with its tool, e.g. the "
            f"lock/install command in AGENTS.md; never edit or read it by hand.)\n")


def _gate(tid: str, root: Path, cfg: dict) -> dict:
    gf = c.gate_file(tid, root, cfg)
    try:
        return json.loads(gf.read_text(encoding="utf-8")) if gf.exists() else {}
    except json.JSONDecodeError:
        return {}


def ticket_text(t: c.Ticket) -> str:
    text = strip_comments_md(t.raw)
    return text.split("\n## Log")[0].rstrip() + "\n"


def gate_summary(tid: str, root: Path, cfg: dict) -> str:
    gf = c.gate_file(tid, root, cfg)
    if not gf.exists():
        return "no gate results recorded"
    data = json.loads(gf.read_text(encoding="utf-8"))
    lines = []
    for k, v in data.items():
        lines.append(f"- {k}: {v['result']} ({v['at']})")
        if v["result"] == "fail" and v.get("detail"):
            lines.append("```text\n" + c.tail(v["detail"], cfg["budgets"]["verify_tail_lines"]) + "\n```")
    return "\n".join(lines)


def executor_pack(t: c.Ticket, root: Path, cfg: dict, cwd: Path, include_owned: bool) -> tuple[str, int]:
    parts = ["# Context pack: " + t.id + " — " + str(t.meta.get("title")) + "\n"]
    role = (root / ".agents" / "roles" / "executor-local.md").read_text(encoding="utf-8")
    parts.append("## Your rules\n" + role.strip() + "\n")
    parts.append("## Ticket\n" + ticket_text(t))
    reads = t.get_list("files_read")
    if reads:
        parts.append("## Reference files (read-only)\n")
        for f in reads:
            p = root / f
            if c.is_generated(f, cfg):
                parts.append(generated_note(f, p))
            else:
                parts.append(fence(f, p.read_text(encoding="utf-8", errors="replace")) if p.is_file()
                             else f"### {f}\n(missing)\n")
    owned_tokens = 0
    owned_parts = []
    for f in t.get_list("files_owned"):
        p = cwd / f
        if "*" in f:
            owned_parts.append(f"### {f}\n(glob: you may create/edit files matching it)\n")
        elif c.is_generated(f, cfg):
            owned_parts.append(generated_note(f, p))
        elif p.is_file():
            txt = p.read_text(encoding="utf-8", errors="replace")
            owned_tokens += c.estimate_tokens(txt, cfg)
            owned_parts.append(fence(f, txt))
        else:
            owned_parts.append(f"### {f}\n(new file — create it)\n")
    if c.tdd_on(t, cfg):
        tests = [f for f in t.get_list("files_owned") if c.is_test_file(f, cfg)]
        if _gate(t.id, root, cfg).get("red", {}).get("result") == "pass":
            parts.append("## Tests first (TDD)\nThe red step is done: the tests are committed and failed without the "
                         "implementation. Now implement until verify passes. Do not weaken the committed tests.\n")
        else:
            parts.append("## Tests first (TDD)\n"
                         f"1. Write ONLY the tests first: {', '.join(tests) or '(the test files you own)'}.\n"
                         f"2. Run `python scripts/agent/run_executor.py {t.id} --red`. It commits the tests and must "
                         f"report them FAILING; it checks this with any implementation changes reverted.\n"
                         "3. Then implement until verify passes. Do not weaken the committed tests.\n")
    if include_owned:
        parts.append("## Files you own (current content)\n" + "\n".join(owned_parts))
    else:
        parts.append("## Files you own\n" + "\n".join(f"- {f}" for f in t.get_list("files_owned"))
                     + "\n(their content is provided separately by your editor)\n")
    if t.status in ("changes_requested", "in_progress") and int(t.meta.get("review_round") or 0) > 0:
        rv = c.latest_review(t.id, root, cfg)
        if rv:
            parts.append(f"## Review to address ({rv.name})\n" + strip_comments_md(rv.read_text(encoding="utf-8")))
    gf = c.gate_file(t.id, root, cfg)
    if gf.exists():
        data = json.loads(gf.read_text(encoding="utf-8"))
        fails = {k: v for k, v in data.items() if v["result"] == "fail"}
        if fails:
            parts.append("## Last gate failure\n" + "\n".join(
                f"{k}:\n```text\n{c.tail(v.get('detail', ''), cfg['budgets']['verify_tail_lines'])}\n```"
                for k, v in fails.items()))
    text = "\n".join(parts)
    total = c.estimate_tokens(text, cfg) + (0 if include_owned else owned_tokens)
    return text, total


REVIEW_OUTPUT = """## Output format (reply with ONLY this document, nothing before or after it)
---
verdict: approved | changes_requested | escalated
---
## Findings (max 5, most severe first; omit the section when approving with none)
1. [blocker] `path:line` — what is wrong. Required: exact change.
2. [minor] `path:line` — ...
## Do NOT change
- correct parts the executor must keep
## Note for architect (only if escalated)
- why the ticket itself is wrong
"""


def _pathspec(cfg: dict) -> list[str]:
    return ["--", "."] + [f":(exclude,glob){g}" for g in c.generated_globs(cfg)]


def generated_changes(rng: str, root: Path, cfg: dict) -> str:
    """Changed generated files of a diff range, with line counts only (their content is never sent)."""
    globs = c.generated_globs(cfg)
    if not globs:
        return ""
    num = c.git(["diff", "--numstat", rng, "--", *[f":(glob){g}" for g in globs]], cwd=root, check=False)
    rows = [f"- {p[2]} (+{p[0]} -{p[1]})" for p in (ln.split("\t") for ln in num.split("\n")) if len(p) >= 3]
    if not rows:
        return ""
    return ("## Generated files changed (content hidden on purpose)\n"
            "These lock/generated files ARE part of the change; only their content is left out of this packet. "
            "Do not report them as missing and do not ask to see them.\n" + "\n".join(rows) + "\n")


def review_meta(t: c.Ticket, root: Path, cfg: dict) -> dict:
    """head commit of the ticket branch and the size of its diff (for policies and incremental reviews)."""
    branch = cfg["git"]["ticket_branch_prefix"] + t.id
    if not c.branch_exists(branch, root):
        return {"head": None, "changed_lines": 0, "base": base_of(t, cfg, root)}
    base = base_of(t, cfg, root)
    head = c.git(["rev-parse", branch], cwd=root)
    num = c.git(["diff", "--numstat", f"{base}...{branch}", *_pathspec(cfg)], cwd=root, check=False)
    changed = 0
    for line in num.split("\n"):
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            changed += int(parts[0]) + int(parts[1])
    return {"head": head, "changed_lines": changed, "base": base}


def _truncate(diff: str, max_lines: int) -> str:
    lines = diff.split("\n")
    if max_lines and len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + (f"\n... [{len(lines) - max_lines} more diff lines cut by the packer; "
                                                f"review what is shown and say if the cut part matters]")
    return diff


def tdd_review_section(red: dict, branch: str, root: Path, cfg: dict) -> str:
    """What the red gate actually recorded: result, order (first/late) and test changes after the red commit."""
    head = "## Tests first (TDD)\n"
    if red.get("result") != "pass":
        return head + (f"Red gate: {red.get('result', 'not run')}. The tests were NOT proven to fail without the "
                       f"implementation.\n")
    sha = str(red.get("commit", ""))[:9]
    order = red.get("order", "unknown")
    if order == "first":
        text = (f"Red gate: pass, order: first. The tests were committed ({sha}) before any implementation change, "
                f"and a test command failed without the implementation.\n")
    else:
        text = (f"Red gate: pass, order: {order}. The tests were committed ({sha}) AFTER implementation files had "
                f"been changed; the gate reverted them and a test command still failed without them.\n")
    globs = [f":(glob){g}" for g in cfg["executor"]["tdd"].get("test_globs", [])]
    after = c.git(["diff", "--stat", f"{red['commit']}..{branch}", "--", *globs], cwd=root, check=False) \
        if red.get("commit") else ""
    return head + text + (f"Test changes AFTER the red commit (check that no test was weakened):\n```text\n{after}\n```\n"
                          if after.strip() else "The tests are unchanged since the red commit.\n")


def review_pack(t: c.Ticket, root: Path, cfg: dict) -> tuple[str, int]:
    rcfg = cfg.get("reviewer", {})
    rnd = int(t.meta.get("review_round") or 0) + 1
    parts = [f"# Review packet: {t.id} — {t.meta.get('title')}\n",
             f"Review round: {rnd} of {c.max_rounds(t, cfg)}\n"]
    role = (root / ".agents" / "roles" / "reviewer.md").read_text(encoding="utf-8")
    parts.append("## Your rules\n" + role.strip() + "\n")
    parts.append("## Ticket\n" + ticket_text(t))
    parts.append("## Gate results\n" + gate_summary(t.id, root, cfg) + "\n")
    branch = cfg["git"]["ticket_branch_prefix"] + t.id
    base = base_of(t, cfg, root)
    prev = c.latest_review(t.id, root, cfg)
    prev_meta = {}
    if prev:
        fm, _ = c.split_frontmatter(prev.read_text(encoding="utf-8"))
        prev_meta = c.parse_frontmatter(fm)
    spec = _pathspec(cfg)
    max_lines = int(rcfg.get("max_diff_lines", 0) or 0)
    if c.branch_exists(branch, root):
        stat = c.git(["diff", "--stat", f"{base}...{branch}", *spec], cwd=root, check=False)
        prev_sha = prev_meta.get("reviewed_commit")
        head = c.git(["rev-parse", branch], cwd=root)
        incremental = (rcfg.get("incremental_rereview", True) and prev_sha and str(prev_sha) != head
                       and c.run(["git", "cat-file", "-e", f"{prev_sha}^{{commit}}"], cwd=root, check=False).returncode == 0)
        parts.append(f"## Files changed in the whole ticket ({base}...{branch})\n```text\n{stat}\n```\n")
        gen = generated_changes(f"{base}...{branch}", root, cfg)
        if gen:
            parts.append(gen)
        red = _gate(t.id, root, cfg).get("red", {})
        if c.tdd_on(t, cfg):
            parts.append(tdd_review_section(red, branch, root, cfg))
        if incremental:
            d = c.git(["diff", "-U3", f"{prev_sha}..{branch}", *spec], cwd=root, check=False)
            parts.append(f"## Changes since the previous review ({str(prev_sha)[:9]}..{head[:9]})\n"
                         f"Only these changes are new. Check that every previous [blocker] is fixed and nothing regressed.\n"
                         f"```diff\n{_truncate(d, max_lines)}\n```\n")
        else:
            d = c.git(["diff", "-U3", f"{base}...{branch}", *spec], cwd=root, check=False)
            parts.append(f"## Diff\n```diff\n{_truncate(d, max_lines)}\n```\n")
            for f in t.get_list("files_read"):
                fp = root / f
                if c.is_generated(f, cfg):
                    parts.append(generated_note(f, fp))
                elif fp.is_file():
                    parts.append(fence(f, fp.read_text(encoding="utf-8", errors="replace")))
    else:
        parts.append(f"## Diff\n(branch {branch} not found)\n")
    if prev:
        parts.append(f"## Previous review ({prev.name})\n" + strip_comments_md(prev.read_text(encoding="utf-8")))
    parts.append(REVIEW_OUTPUT)
    text = "\n".join(parts)
    return text, c.estimate_tokens(text, cfg)


def build(tid: str, review: bool = False, cwd: Path | None = None, include_owned: bool = True,
          out: bool = False, force: bool = False) -> tuple[str, int, Path | None]:
    root = c.control_root()
    cfg = c.load_config(root)
    t = c.find_ticket(tid, root, cfg)
    if review:
        text, tokens = review_pack(t, root, cfg)
        budget = None
    else:
        text, tokens = executor_pack(t, root, cfg, cwd or root, include_owned)
        budget = budget_for(t, cfg)
        if tokens > budget and not force:
            sys.exit(f"error: pack for {t.id} is ~{tokens} tokens, budget {budget}. "
                     f"Split the ticket or shrink files_read (or --force).")
    path = None
    if out:
        d = c.cfg_path(cfg, "packs", root)
        d.mkdir(parents=True, exist_ok=True)
        path = d / (f"{t.id}.review.md" if review else f"{t.id}.md")
        path.write_text(text, encoding="utf-8")
    return text, tokens, path


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id")
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--cwd", type=Path)
    ap.add_argument("--no-owned", action="store_true")
    ap.add_argument("--out", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    text, tokens, path = build(a.id, a.review, a.cwd.resolve() if a.cwd else None, not a.no_owned, a.out, a.force)
    if path:
        print(f"{path} (~{tokens} tokens)")
    else:
        print(text)
        print(f"<!-- ~{tokens} tokens -->", file=sys.stderr)


if __name__ == "__main__":
    main()
