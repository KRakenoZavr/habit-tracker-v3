#!/usr/bin/env python3
"""Find docs whose covered code changed since they were last verified.

Docs declare metadata as frontmatter (.md), '%% key: value' lines (.mmd) or '# key: value' lines (.yaml):
  covers: [src/net/**, docs/ai/contracts/net.pyi]
  verified_at: <commit sha> | none

  python scripts/agent/doc_fresh.py               # report; exit 1 if any doc is stale
  python scripts/agent/doc_fresh.py --stamp FILE  # set verified_at to the current HEAD

A covered file whose only change is a `verified_at:` stamp does not make a doc stale, so stamping one doc never
cascades into the docs that cover it: one update + stamp + commit pass is enough.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import common as c

EXTS = {".md", ".mmd", ".yaml", ".yml"}


def read_meta(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".md":
        fm, _ = c.split_frontmatter(text)
        return c.parse_frontmatter(fm)
    prefix = "%%" if path.suffix == ".mmd" else "#"
    meta_lines = []
    for line in text.split("\n")[:15]:
        s = line.strip()
        if s.startswith(prefix):
            meta_lines.append(s[len(prefix):].strip())
    return c.parse_frontmatter("\n".join(meta_lines))


def stamp(path: Path, sha: str) -> None:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        text = c.set_frontmatter_fields(text, {"verified_at": sha})
    else:
        prefix = "%%" if path.suffix == ".mmd" else "#"
        pat = re.compile(rf"^(\s*{re.escape(prefix)}\s*verified_at:).*$", re.M)
        if pat.search(text):
            text = pat.sub(lambda m: f"{m.group(1)} {sha}", text, count=1)
        else:
            text = f"{prefix} verified_at: {sha}\n" + text
    path.write_text(text, encoding="utf-8")


def stamp_only(path: str, ver: str, root: Path) -> bool:
    """True if every line of `path` changed since `ver` is a verified_at stamp line."""
    if Path(path).suffix not in EXTS:
        return False
    r = c.run(["git", "diff", "-U0", f"{ver}..HEAD", "--", path], cwd=root, check=False)
    changed = [ln for ln in r.stdout.split("\n") if ln[:1] in ("+", "-") and not ln.startswith(("+++", "---"))]
    return bool(changed) and all("verified_at:" in ln for ln in changed)


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stamp", nargs="+", type=Path)
    a = ap.parse_args()
    root = c.control_root()
    cfg = c.load_config(root)
    sha = c.head_sha(root)
    if a.stamp:
        for p in a.stamp:
            stamp(p.resolve(), sha)
            print(f"stamped {p} verified_at: {sha}")
        return

    stale, unverified = [], []
    for d in cfg["paths"]["docs_roots"]:
        base = root / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.suffix not in EXTS or not p.is_file():
                continue
            meta = read_meta(p)
            covers = meta.get("covers")
            if not covers:
                continue
            covers = covers if isinstance(covers, list) else [covers]
            rel = p.relative_to(root).as_posix()
            ver = meta.get("verified_at")
            if not ver:
                unverified.append(rel)
                continue
            r = c.run(["git", "diff", "--name-only", f"{ver}..HEAD"], cwd=root, check=False)
            if r.returncode != 0:
                stale.append((rel, [f"unknown commit {ver}"]))
                continue
            hits = [f for f in r.stdout.split("\n") if f and f != rel and c.matches(f, covers)
                    and not stamp_only(f, ver, root)]
            if hits:
                stale.append((rel, hits))

    for rel, hits in stale:
        more = f" (+{len(hits) - 5} more)" if len(hits) > 5 else ""
        print(f"STALE {rel}: {', '.join(hits[:5])}{more}")
    if unverified:
        print(f"never verified ({len(unverified)}): " + ", ".join(unverified))
    if not stale:
        print("doc_fresh: no stale docs")
    sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()
