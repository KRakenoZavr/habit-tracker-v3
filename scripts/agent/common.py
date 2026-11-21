"""Shared helpers for the agent scripts. Python 3.10+, standard library only.

Concepts
- control root: the main checkout that holds work/ (tickets, reviews, STATE.md).
  Scripts called from a ticket worktree still read and write tickets in the control root.
- frontmatter: a restricted YAML subset (``key: value`` lines, inline ``[a, "b c"]`` lists,
  ``# comments``). Keep ticket frontmatter in this subset; no nested blocks.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

STATUSES = [
    "draft", "ready", "in_progress", "in_review", "changes_requested",
    "approved", "integrated", "done", "blocked", "escalated",
]
TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ready", "blocked"},
    "ready": {"in_progress", "draft", "blocked"},
    "in_progress": {"in_review", "blocked", "ready"},
    "in_review": {"approved", "changes_requested", "escalated", "blocked"},
    "changes_requested": {"in_progress", "escalated", "blocked"},
    "approved": {"integrated", "changes_requested"},
    "integrated": {"done", "changes_requested"},
    "done": set(),
    "blocked": {"draft", "ready", "in_progress"},
    "escalated": {"draft", "ready"},
}
# A dependency counts only once its code is on the integration branch, so the dependent
# ticket's worktree (branched from int/<milestone>) actually contains it.
DEPS_SATISFIED = {"integrated", "done"}
REQUIRED_KEYS = [
    "id", "title", "status", "milestone", "depends_on", "files_owned", "files_read",
    "lock_resources", "difficulty", "context_budget_tokens", "max_review_rounds",
    "review_round", "verify",
]
REQUIRED_SECTIONS = ["Goal", "Interface", "Steps", "Acceptance criteria"]


# --------------------------------------------------------------------------- git / paths

def run(cmd: list[str], cwd: Path | str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True,
                          encoding="utf-8", errors="replace")


def git(args: list[str], cwd: Path | str | None = None, check: bool = True) -> str:
    return run(["git", *args], cwd=cwd, check=check).stdout.strip()


def script_repo() -> Path:
    return Path(__file__).resolve().parents[2]


CONTROL_MARKER = ".agent-control-root"  # local, gitignored: makes a linked worktree act as the control root


def control_root() -> Path:
    env = os.environ.get("AGENT_CONTROL_ROOT")
    if env:
        return Path(env).resolve()
    here = script_repo()
    # A marked checkout wins; a ticket worktree (<control>/.worktrees/<id>) resolves to its marked parent.
    candidates = [here] + ([here.parent.parent] if here.parent.name == ".worktrees" else [])
    for cand in candidates:
        if (cand / CONTROL_MARKER).is_file():
            return cand
    try:
        common = Path(git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=here))
        if common.name == ".git":
            return common.parent
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return here


def branch_exists(name: str, cwd: Path) -> bool:
    return run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], cwd=cwd, check=False).returncode == 0


def current_branch(cwd: Path) -> str:
    return git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)


def head_sha(cwd: Path, short: bool = True) -> str:
    return git(["rev-parse", "--short" if short else "--verify", "HEAD"], cwd=cwd)


def norm(path: str) -> str:
    p = path.replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p


def now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------- config

def load_config(root: Path | None = None) -> dict:
    root = root or control_root()
    path = root / ".agents" / "config.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def cfg_path(cfg: dict, key: str, root: Path) -> Path:
    return root / cfg["paths"][key]


def tier_of(t: "Ticket", cfg: dict) -> tuple[str, dict]:
    ex = cfg["executor"]
    key = str(t.meta.get("difficulty") or ex.get("default_tier", "S"))
    tiers = ex["tiers"]
    if key not in tiers:
        sys.exit(f"error: {t.id}: difficulty '{key}' is not a tier in .agents/config.json (have: {', '.join(tiers)})")
    return key, tiers[key]


def reviewer_command(cfg: dict, prompt: str, effort: str | None, out_file: str | None = None,
                     hard: bool = False) -> tuple[list[str], str | None, str | None]:
    """reviewer.command with {prompt}, {model}, {effort}, {out_file} substituted. Returns (cmd, model, effort).
    `hard` (L tickets, milestone PRs) uses reviewer.hard.model and, if set, reviewer.hard.effort.
    A part whose {model}/{effort} value is empty is dropped together with the flag before it (e.g. `-m {model}`),
    so the CLI falls back to its own default."""
    rv = cfg.get("reviewer", {})
    pick = rv.get("hard", {}) if hard else {}
    model = pick.get("model") or rv.get("model") or None
    effort = pick.get("effort") or effort or None
    subs = {"{model}": model or "", "{effort}": effort or "", "{out_file}": out_file or ""}
    cmd: list[str] = []
    for part in rv.get("command", []):
        if part == "{prompt}":
            cmd.append(prompt)
            continue
        if any(k in part and not v for k, v in subs.items()):
            if cmd and cmd[-1].startswith("-"):
                cmd.pop()
            continue
        for k, v in subs.items():
            part = part.replace(k, v)
        cmd.append(part.replace("{prompt}", prompt))
    return cmd, model, effort


def generated_globs(cfg: dict) -> list[str]:
    """Lock files and other generated files: agents see their names, never their content.
    Top-level `generated_globs`, plus the older `reviewer.diff_exclude` if a config still has it."""
    out = list(cfg.get("generated_globs", []))
    out += [g for g in cfg.get("reviewer", {}).get("diff_exclude", []) if g not in out]
    return [g for g in out if g]


def is_generated(path: str, cfg: dict) -> bool:
    return matches(path, generated_globs(cfg))


def tdd_on(t: "Ticket", cfg: dict) -> bool:
    """Tests-first applies unless executor.tdd.enabled is false or the ticket says `tdd: false`."""
    if not cfg.get("executor", {}).get("tdd", {}).get("enabled", False):
        return False
    return t.meta.get("tdd") is not False


def is_test_file(path: str, cfg: dict) -> bool:
    return matches(path, cfg.get("executor", {}).get("tdd", {}).get("test_globs", []))


def milestone_base(m: str, root: Path, cfg: dict) -> str:
    """Base branch of int/<m> for stacked milestone PRs (main <- int/M1 <- int/M2 ...).

    The previous milestone's integration branch (M3 -> int/M2) while it exists, is not yet merged into
    git.default_base, and is still under int/<m> (an ancestor of it). Once int/<m> was moved onto the default base
    (restack after a squash merge), the previous branch is no longer its ancestor and the base is git.default_base.
    Only milestone ids ending in a number are stacked."""
    g = cfg["git"]
    default = g.get("default_base", "main")
    mt = re.match(r"^(.*?)(\d+)$", m)
    if not mt or int(mt.group(2)) <= 1:
        return default
    prev = g["integration_branch_prefix"] + mt.group(1) + str(int(mt.group(2)) - 1)
    if not branch_exists(prev, root):
        return default

    def ancestor(a: str, b: str) -> bool:
        return run(["git", "merge-base", "--is-ancestor", a, b], cwd=root, check=False).returncode == 0
    if ancestor(prev, default):
        return default
    cur = g["integration_branch_prefix"] + m
    if branch_exists(cur, root) and not ancestor(prev, cur):
        return default
    return prev


def is_hard_ticket(t: "Ticket", cfg: dict) -> bool:
    return str(t.meta.get("difficulty")) in cfg.get("reviewer", {}).get("hard", {}).get("difficulties", [])


def reviewer_unavailable(cfg: dict, output: str) -> bool:
    """True when the reviewer CLI output matches reviewer.limit_patterns (usage/rate limit, not a review failure)."""
    low = output.lower()
    pats = cfg.get("reviewer", {}).get("limit_patterns") or ["usage limit", "rate limit", "too many requests"]
    return any(p.lower() in low for p in pats)


def pack_budget(t: "Ticket", cfg: dict) -> int:
    """Ticket override (context_budget_tokens) or the tier's pack_tokens."""
    v = t.meta.get("context_budget_tokens")
    return int(v) if v else int(tier_of(t, cfg)[1]["pack_tokens"])


def max_rounds(t: "Ticket", cfg: dict | None = None) -> int:
    v = t.meta.get("max_review_rounds")
    if v:
        return int(v)
    cfg = cfg or load_config()
    return int(cfg["budgets"].get("max_review_rounds", 3))


def estimate_tokens(text: str, cfg: dict | None = None) -> int:
    cpt = (cfg or {}).get("budgets", {}).get("chars_per_token", 3.5)
    return math.ceil(len(text) / cpt)


# --------------------------------------------------------------------------- globs

def glob_to_regex(pattern: str) -> re.Pattern:
    p = norm(pattern)
    out, i = [], 0
    while i < len(p):
        c = p[i]
        if p.startswith("**/", i):
            out.append("(?:.*/)?"); i += 3
        elif p.startswith("**", i):
            out.append(".*"); i += 2
        elif c == "*":
            out.append("[^/]*"); i += 1
        elif c == "?":
            out.append("[^/]"); i += 1
        else:
            out.append(re.escape(c)); i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(path: str, patterns: list[str]) -> bool:
    path = norm(path)
    return any(glob_to_regex(p).match(path) for p in patterns if p)


def _static_prefix(pattern: str) -> str:
    m = re.search(r"[*?\[]", pattern)
    return pattern if m is None else pattern[: m.start()]


def globs_overlap(a: str, b: str) -> bool:
    """Conservative: True if some path could match both patterns."""
    a, b = norm(a), norm(b)
    a_lit, b_lit = _static_prefix(a) == a, _static_prefix(b) == b
    if a_lit and b_lit:
        return a == b
    if a_lit:
        return bool(glob_to_regex(b).match(a))
    if b_lit:
        return bool(glob_to_regex(a).match(b))
    pa, pb = _static_prefix(a), _static_prefix(b)
    return pa.startswith(pb) or pb.startswith(pa)


def sets_overlap(xs: list[str], ys: list[str]) -> list[tuple[str, str]]:
    return [(x, y) for x in xs for y in ys if globs_overlap(x, y)]


# --------------------------------------------------------------------------- frontmatter

def split_frontmatter(text: str) -> tuple[str, str]:
    t = text.replace("\r\n", "\n")
    if not t.startswith("---\n"):
        return "", t
    end = t.find("\n---", 4)
    if end == -1:
        return "", t
    nl = t.find("\n", end + 1)
    body = "" if nl == -1 else t[nl + 1:]
    return t[4:end + 1], body


def _value_span(raw: str) -> tuple[object, int]:
    """Parse a value at the start of raw. Returns (value, end_index)."""
    s = raw
    lead = len(s) - len(s.lstrip())
    s = s.lstrip()
    if not s:
        return None, lead
    if s[0] in "[{":
        close = "]" if s[0] == "[" else "}"
        depth, quote, i = 0, None, 0
        while i < len(s):
            ch = s[i]
            if quote:
                if ch == "\\":
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == s[0]:
                depth += 1
            elif ch == close:
                depth -= 1
                if depth == 0:
                    break
            i += 1
        chunk = s[: i + 1]
        if s[0] == "{":
            return chunk, lead + i + 1
        return _parse_list(chunk[1:-1]), lead + i + 1
    if s[0] in "\"'":
        q = s[0]
        i = 1
        while i < len(s) and s[i] != q:
            i += 2 if s[i] == "\\" else 1
        inner = s[1:i]
        if q == '"':
            try:
                inner = json.loads(s[: i + 1])
            except json.JSONDecodeError:
                pass
        return inner, lead + i + 1
    m = re.search(r"\s+#", s)
    end = m.start() if m else len(s)
    return _scalar(s[:end].strip()), lead + end


def _scalar(v: str) -> object:
    if v.lower() in ("", "none", "null", "~"):
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def _parse_list(inner: str) -> list:
    items, buf, quote, i = [], [], None, 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(inner):
                buf.append(inner[i + 1]); i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch; buf.append(ch)
        elif ch == ",":
            items.append("".join(buf)); buf = []
        else:
            buf.append(ch)
        i += 1
    items.append("".join(buf))
    out = []
    for it in items:
        it = it.strip()
        if not it:
            continue
        if it[0] == '"' and it[-1] == '"':
            try:
                it = json.loads(it)
            except json.JSONDecodeError:
                it = it[1:-1]
        elif it[0] == "'" and it[-1] == "'":
            it = it[1:-1]
        out.append(it)
    return out


def parse_frontmatter(fm: str) -> dict:
    data: dict = {}
    for line in fm.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):(.*)$", line)
        if not m:
            continue
        value, _ = _value_span(m.group(2))
        data[m.group(1)] = value
    return data


def format_value(v: object) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_fmt_item(x) for x in v) + "]"
    s = str(v)
    if re.search(r"\s#|^[\[\{\"'#]|^\s|\s$", s) or s.lower() in ("none", "null", "true", "false"):
        return json.dumps(s, ensure_ascii=False)
    return s


def _fmt_item(x: object) -> str:
    s = str(x)
    return s if re.fullmatch(r"[A-Za-z0-9_./*\-]+", s) else json.dumps(s, ensure_ascii=False)


def set_frontmatter_fields(text: str, updates: dict) -> str:
    fm, body = split_frontmatter(text)
    lines = fm.split("\n")
    done = set()
    for idx, line in enumerate(lines):
        m = re.match(r"^([A-Za-z_][\w-]*):(.*)$", line)
        if m and m.group(1) in updates:
            key, rest = m.group(1), m.group(2)
            _, end = _value_span(rest)
            tail = rest[end:]
            comment = tail if tail.strip().startswith("#") else ""
            new = f"{key}: {format_value(updates[key])}"
            if comment:
                new = f"{new}  {comment.strip()}"
            lines[idx] = new
            done.add(key)
    insert_at = len(lines) - 1 if lines and lines[-1] == "" else len(lines)
    for key, val in updates.items():
        if key not in done:
            lines.insert(insert_at, f"{key}: {format_value(val)}")
            insert_at += 1
    return "---\n" + "\n".join(lines) + ("" if "\n".join(lines).endswith("\n") else "\n") + "---\n" + body


def sections(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in body.split("\n"):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current, buf = m.group(1), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    return out


# --------------------------------------------------------------------------- tickets

@dataclass
class Ticket:
    path: Path
    meta: dict
    body: str
    raw: str = field(repr=False, default="")

    @property
    def id(self) -> str:
        return str(self.meta.get("id"))

    def get_list(self, key: str) -> list[str]:
        v = self.meta.get(key)
        if v is None:
            return []
        return [norm(str(x)) for x in (v if isinstance(v, list) else [v])]

    @property
    def status(self) -> str:
        return str(self.meta.get("status"))

    def lock_set(self, cfg: dict) -> list[str]:
        locks = list(self.get_list("lock_resources"))
        cfg_locks = [x for x in cfg.get("lock_resources", []) if x]
        for f in self.get_list("files_owned"):
            if matches(f, cfg_locks):
                locks.append(f)
        return locks


def load_ticket(path: Path) -> Ticket:
    raw = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(raw)
    return Ticket(path=path, meta=parse_frontmatter(fm), body=body, raw=raw)


def ticket_files(root: Path, cfg: dict, include_archive: bool = False) -> list[Path]:
    dirs = [cfg_path(cfg, "tickets", root)]
    if include_archive:
        dirs.append(cfg_path(cfg, "archive", root))
    files: list[Path] = []
    for d in dirs:
        if d.exists():
            files += sorted(p for p in d.glob("T-*.md"))
    return files


def load_tickets(root: Path, cfg: dict, include_archive: bool = False) -> dict[str, Ticket]:
    out: dict[str, Ticket] = {}
    for p in ticket_files(root, cfg, include_archive):
        t = load_ticket(p)
        out[t.id] = t
    return out


def find_ticket(tid: str, root: Path, cfg: dict) -> Ticket:
    tid = tid.upper()
    for p in ticket_files(root, cfg, include_archive=True):
        if p.name == f"{tid}.md" or p.name.startswith(f"{tid}-"):
            return load_ticket(p)
    sys.exit(f"error: ticket {tid} not found in {cfg['paths']['tickets']}")


def append_log(text: str, line: str) -> str:
    if "\n## Log" in text:
        return text.rstrip("\n") + f"\n- {line}\n"
    return text.rstrip("\n") + f"\n\n## Log\n- {line}\n"


def save_ticket(t: Ticket, updates: dict, log: str | None = None) -> Ticket:
    text = set_frontmatter_fields(t.raw, updates)
    if log:
        text = append_log(text, log)
    t.path.write_text(text, encoding="utf-8")
    return load_ticket(t.path)


def set_status(t: Ticket, new: str, by: str = "script", note: str = "", force: bool = False) -> Ticket:
    if new not in STATUSES:
        sys.exit(f"error: unknown status '{new}'. Valid: {', '.join(STATUSES)}")
    old = t.status
    if not force and new != old and new not in TRANSITIONS.get(old, set()):
        allowed = ", ".join(sorted(TRANSITIONS.get(old, set()))) or "none"
        sys.exit(f"error: {t.id}: {old} -> {new} not allowed. From {old} you may go to: {allowed}. (--force to override)")
    updates: dict = {"status": new}
    rnd = int(t.meta.get("review_round") or 0)
    max_r = max_rounds(t)
    if new == "changes_requested" and old != new:
        if rnd + 1 >= max_r and not force:
            sys.exit(f"error: {t.id}: this is review round {rnd + 1} of {max_r} (the last). "
                     f"Choose 'approved' or 'escalated'.")
        updates["review_round"] = rnd + 1
    if new in ("draft",) and old in ("blocked", "escalated"):
        updates["review_round"] = 0
    msg = f"{now()} status {old} -> {new} (by {by})" + (f": {note}" if note else "")
    return save_ticket(t, updates, msg)


def deps_satisfied(t: Ticket, tickets: dict[str, Ticket]) -> tuple[bool, list[str]]:
    missing = []
    for d in t.get_list("depends_on"):
        dep = tickets.get(d.upper())
        if dep is None or dep.status not in DEPS_SATISFIED:
            missing.append(f"{d}({dep.status if dep else 'missing'})")
    return not missing, missing


def latest_review(tid: str, root: Path, cfg: dict) -> Path | None:
    d = cfg_path(cfg, "reviews", root)
    found = sorted(d.glob(f"{tid}.r*.md"), key=lambda p: int(re.search(r"\.r(\d+)\.md$", p.name).group(1))
                   if re.search(r"\.r(\d+)\.md$", p.name) else 0)
    return found[-1] if found else None


def gate_file(tid: str, root: Path, cfg: dict) -> Path:
    d = cfg_path(cfg, "packs", root)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{tid}.gate.json"


def update_gate(tid: str, root: Path, cfg: dict, key: str, ok: bool, detail: str, **extra) -> None:
    gf = gate_file(tid, root, cfg)
    data = {}
    if gf.exists():
        try:
            data = json.loads(gf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data[key] = {"result": "pass" if ok else "fail", "at": now(), "detail": detail, **extra}
    gf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def tail(text: str, n: int) -> str:
    lines = text.rstrip("\n").split("\n")
    return "\n".join(lines[-n:])


def ensure_utf8_stdout() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


# --------------------------------------------------------------------------- usage log

def log_usage(root: Path, cfg: dict, role: str, ticket: str | None, model: str | None,
              tokens: int | None = None, cost_usd: float | None = None, **extra) -> None:
    """Append one line to work/.pack/usage.jsonl (read by usage.py and run_loop.py summaries).
    Usual extras: milestone, effort, seconds (wall time of the run), input/cache_read/cache_write/output, turns."""
    d = cfg_path(cfg, "packs", root)
    d.mkdir(parents=True, exist_ok=True)
    rec = {"at": now(), "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"), "role": role,
           "ticket": ticket, "model": model, "tokens": tokens, "cost_usd": cost_usd}
    rec.update({k: v for k, v in extra.items() if v is not None})
    with (d / "usage.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def parse_token_count(text: str) -> int | None:
    """Fallback: the 'tokens used' line of CLI output. Codex prints the number on the next line and groups digits
    by locale ('11 611', '11,611', '11 611'), so separators inside the number are allowed."""
    m = re.findall(r"tokens?\s+used\D{0,10}?(\d(?:[\d,._   ]*\d)?)", text, flags=re.I)
    if not m:
        return None
    try:
        return int(re.sub(r"\D", "", m[-1]))
    except ValueError:
        return None


def codex_usage(output: str) -> dict:
    """Token usage of one `codex exec` run, read from its session file (~/.codex/sessions/**/rollout-*<id>.jsonl):
    the last token_count event's total_token_usage. Falls back to the 'tokens used' line.
    Returns {tokens, input, cache_read, output, reasoning} (tokens = input incl. cached + output); missing keys = unknown."""
    m = re.search(r"session id:\s*([0-9a-f-]{36})", output, flags=re.I)
    if m:
        home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        files = sorted((home / "sessions").rglob(f"rollout-*{m.group(1)}.jsonl")) if (home / "sessions").is_dir() else []
        last = None
        for f in files[-1:]:
            for line in f.open(encoding="utf-8", errors="replace"):
                if '"token_count"' not in line:
                    continue
                try:
                    p = json.loads(line).get("payload") or {}
                except json.JSONDecodeError:
                    continue
                info = p.get("info") or {}
                if p.get("type") == "token_count" and info.get("total_token_usage"):
                    last = info["total_token_usage"]
        if last:
            cached = int(last.get("cached_input_tokens") or 0)
            inp, out = int(last.get("input_tokens") or 0), int(last.get("output_tokens") or 0)
            return {"tokens": inp + out, "input": inp - cached, "cache_read": cached, "output": out,
                    "reasoning": int(last.get("reasoning_output_tokens") or 0)}
    n = parse_token_count(output)
    return {"tokens": n} if n is not None else {}


def claude_usage(data: dict) -> dict:
    """Token usage of one `claude -p --output-format json` run: totals over modelUsage (all models the run used),
    falling back to the top-level usage block. Returns {tokens, input, cache_read, cache_write, output, models}."""
    mu = data.get("modelUsage") or {}
    if mu:
        keys = {"input": "inputTokens", "cache_read": "cacheReadInputTokens",
                "cache_write": "cacheCreationInputTokens", "output": "outputTokens"}
        r = {k: sum(int(v.get(src) or 0) for v in mu.values()) for k, src in keys.items()}
        r["models"] = sorted(mu)
    else:
        u = data.get("usage") or {}
        r = {"input": int(u.get("input_tokens") or 0), "cache_read": int(u.get("cache_read_input_tokens") or 0),
             "cache_write": int(u.get("cache_creation_input_tokens") or 0), "output": int(u.get("output_tokens") or 0)}
    r["tokens"] = r["input"] + r["cache_read"] + r["cache_write"] + r["output"] or None
    return r
