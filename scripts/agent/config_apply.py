#!/usr/bin/env python3
"""Apply a config proposal from the architect to .agents/config.json (which agents cannot edit).

The architect writes ONLY the keys it wants to change to work/config.proposed.json, e.g.
  {"verify": {"commands": ["cargo fmt --all --check", "cargo test --workspace"]},
   "executor": {"claude_cli": {"extra_allowed_tools": ["Bash(cargo:*)"]}},
   "loop": {"calibration": {"enabled": true, "tickets": 3}}}

You review and apply it:
  python scripts/agent/config_apply.py          # show the changes, ask y/N, apply, run sync.py
  python scripts/agent/config_apply.py --yes    # no question
  python scripts/agent/config_apply.py --show   # only show

Objects are merged key by key; lists and values are replaced. Keys starting with "_" are comments and are ignored.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

import common as c

HERE = Path(__file__).resolve().parent


def merge(base: dict, patch: dict, path: str, changes: list) -> None:
    for k, v in patch.items():
        if k.startswith("_"):
            continue
        key = f"{path}.{k}" if path else k
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            merge(base[k], v, key, changes)
        elif base.get(k) != v:
            changes.append((key, base.get(k, "<new>"), v))
            base[k] = v


def main():
    c.ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--file", default="work/config.proposed.json")
    a = ap.parse_args()
    root = c.control_root()
    prop_path = root / a.file
    if not prop_path.exists():
        sys.exit(f"no proposal at {a.file}")
    cfg_path = root / ".agents" / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    try:
        patch = json.loads(prop_path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    except json.JSONDecodeError as e:
        sys.exit(f"error: {a.file} is not valid JSON: {e}")
    changes: list = []
    merge(cfg, patch, "", changes)
    if not changes:
        print("proposal changes nothing")
        return
    print(f"Proposed changes to .agents/config.json ({a.file}):")
    for key, old, new in changes:
        print(f"  {key}\n    - {json.dumps(old, ensure_ascii=False)}\n    + {json.dumps(new, ensure_ascii=False)}")
    if a.show:
        return
    if not a.yes:
        if input("Apply? [y/N] ").strip().lower() not in ("y", "yes"):
            print("not applied")
            return
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    prop_path.rename(prop_path.with_suffix(".applied.json"))
    print(f"applied {len(changes)} change(s)")
    subprocess.run([sys.executable, str(HERE / "sync.py")])


if __name__ == "__main__":
    main()
