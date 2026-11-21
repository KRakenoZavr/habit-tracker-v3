#!/usr/bin/env python3
"""Ticket tool: create tickets, change status (enforcing the state machine), list, archive.

  python scripts/agent/ticket.py new "Add retry to HttpClient" --milestone M2 --module io
  python scripts/agent/ticket.py new-batch work/batch-M2.md --milestone M2 --ready   # many tickets, one file
  python scripts/agent/ticket.py status T-0007 ready [--note "..."] [--by architect] [--force]
  python scripts/agent/ticket.py list [--status ready] [--milestone M2]
  python scripts/agent/ticket.py archive --done [--remove-worktrees]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import common as c


def cmd_new(args, root, cfg):
    tickets = c.load_tickets(root, cfg, include_archive=True)
    nums = [int(m.group(1)) for tid in tickets if (m := re.match(r"T-(\d+)", tid))]
    tid = f"T-{(max(nums) + 1 if nums else 1):04d}"
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")[:40] or "ticket"
    template = (root / "work" / "templates" / "ticket.md").read_text(encoding="utf-8")
    text = c.set_frontmatter_fields(template, {
        "id": tid, "title": args.title, "milestone": args.milestone,
        "module": args.module, "difficulty": args.difficulty,
    })
    out = c.cfg_path(cfg, "tickets", root) / f"{tid}-{slug}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(c.append_log(text, f"{c.now()} created (by {args.by})"), encoding="utf-8")
    print(out.relative_to(root).as_posix())


def _next_number(root, cfg) -> int:
    tickets = c.load_tickets(root, cfg, include_archive=True)
    nums = [int(m.group(1)) for tid in tickets if (m := re.match(r"T-(\d+)", tid))]
    return max(nums) + 1 if nums else 1


def cmd_new_batch(args, root, cfg):
    """One file, many tickets: chunks separated by a line containing only %%%.
    Each chunk = frontmatter (any ticket keys; omitted keys use the template) + body sections.
    depends_on may reference earlier tickets of the same batch as "@1", "@2", ... (1-based)."""
    import ticket_lint  # local import: lint after creation
    src = (root / args.file) if not Path(args.file).is_absolute() else Path(args.file)
    chunks = [ch.strip() for ch in re.split(r"(?m)^%%%\s*$", src.read_text(encoding="utf-8")) if ch.strip()]
    first = _next_number(root, cfg)
    ids = [f"T-{first + i:04d}" for i in range(len(chunks))]
    template = (root / "work" / "templates" / "ticket.md").read_text(encoding="utf-8")
    tdir = c.cfg_path(cfg, "tickets", root)
    tdir.mkdir(parents=True, exist_ok=True)
    created = []
    for i, chunk in enumerate(chunks):
        fm, body = c.split_frontmatter(chunk + "\n")
        meta = c.parse_frontmatter(fm)
        if not meta.get("title"):
            sys.exit(f"error: batch ticket #{i + 1} has no title")
        deps = []
        for d in (meta.get("depends_on") or []):
            d = str(d)
            if d.startswith("@"):
                n = int(d[1:])
                if not 1 <= n <= len(ids) or n == i + 1:
                    sys.exit(f"error: batch ticket #{i + 1}: bad reference {d}")
                deps.append(ids[n - 1])
            else:
                deps.append(d.upper())
        meta["depends_on"] = deps
        meta["id"] = ids[i]
        meta.setdefault("milestone", args.milestone)
        if args.milestone and not meta.get("milestone"):
            meta["milestone"] = args.milestone
        meta.setdefault("status", "draft")
        text = c.set_frontmatter_fields(template, meta)
        tfm, _ = c.split_frontmatter(text)
        text = "---\n" + tfm + "---\n" + body.strip() + f"\n\n## Log\n- {c.now()} created from batch {src.name} (by {args.by})\n"
        slug = re.sub(r"[^a-z0-9]+", "-", str(meta["title"]).lower()).strip("-")[:40] or "ticket"
        out = tdir / f"{ids[i]}-{slug}.md"
        out.write_text(text, encoding="utf-8")
        created.append(out)
    tickets = c.load_tickets(root, cfg, include_archive=True)
    bad = 0
    for path in created:
        t = c.load_ticket(path)
        errs, warns = ticket_lint.lint(t, tickets, root, cfg)
        flag = "ERR " if errs else ("warn" if warns else "ok  ")
        if not errs and args.ready:
            c.set_status(t, "ready", by=args.by, note="batch lint clean")
        bad += bool(errs)
        print(f"{flag} {t.id} {t.meta.get('title')}" + (f"  — {errs[0]}" if errs else (f"  — {warns[0]}" if warns else "")))
    print(f"{len(created)} created, {len(created) - bad} lint-clean" + (" and set ready" if args.ready else ""))
    if bad:
        sys.exit(1)


def cmd_status(args, root, cfg):
    for tid in args.ids:
        t = c.find_ticket(tid, root, cfg)
        t = c.set_status(t, args.new_status, by=args.by, note=args.note, force=args.force)
        print(f"{t.id}: {t.status} (review_round {t.meta.get('review_round')}/{c.max_rounds(t, cfg)})")


def cmd_list(args, root, cfg):
    tickets = c.load_tickets(root, cfg, include_archive=args.all)
    rows = []
    for t in tickets.values():
        if args.status and t.status != args.status:
            continue
        if args.milestone and str(t.meta.get("milestone")) != args.milestone:
            continue
        ok, missing = c.deps_satisfied(t, tickets)
        rows.append((t.id, t.status, str(t.meta.get("difficulty")), str(t.meta.get("milestone")),
                     t.meta.get("title"), "" if ok else "waits: " + ", ".join(missing)))
    if not rows:
        print("no tickets")
        return
    for r in rows:
        print(f"{r[0]}  {r[1]:<17} {r[2]:<2} {r[3]:<5} {r[4]}  {r[5]}")


def cmd_archive(args, root, cfg):
    if not args.done:
        sys.exit("error: pass --done to archive tickets with status done")
    arch = c.cfg_path(cfg, "archive", root)
    arch.mkdir(parents=True, exist_ok=True)
    reviews = c.cfg_path(cfg, "reviews", root)
    moved = 0
    for t in c.load_tickets(root, cfg).values():
        if t.status != "done":
            continue
        shutil.move(str(t.path), str(arch / t.path.name))
        for r in reviews.glob(f"{t.id}.r*.md"):
            shutil.move(str(r), str(arch / r.name))
        moved += 1
        if args.remove_worktrees:
            wt = (root / cfg["git"]["worktree_dir"] / t.id).resolve()
            if wt.exists():
                c.run(["git", "worktree", "remove", "--force", str(wt)], cwd=root, check=False)
            branch = cfg["git"]["ticket_branch_prefix"] + t.id
            if c.branch_exists(branch, root):
                c.run(["git", "branch", "-D", branch], cwd=root, check=False)
        print(f"archived {t.id}")
    print(f"{moved} ticket(s) archived")


def main():
    c.ensure_utf8_stdout()
    root = c.control_root()
    cfg = c.load_config(root)
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="create a ticket from work/templates/ticket.md")
    n.add_argument("title")
    n.add_argument("--milestone", default="M1")
    n.add_argument("--module", default="none")
    n.add_argument("--difficulty", default=cfg["executor"].get("default_tier", "S"),
                   choices=list(cfg["executor"]["tiers"]))
    n.add_argument("--by", default="architect")

    nb = sub.add_parser("new-batch", help="create many tickets from one file (chunks separated by %%%%%%)")
    nb.add_argument("file")
    nb.add_argument("--milestone", default="M1")
    nb.add_argument("--ready", action="store_true", help="set lint-clean tickets to ready")
    nb.add_argument("--by", default="architect")

    s = sub.add_parser("status", help="change status (state machine enforced)")
    s.add_argument("ids", nargs="+", help="one or more ticket ids, then the new status")
    s.add_argument("--note", default="")
    s.add_argument("--by", default="agent")
    s.add_argument("--force", action="store_true")

    ls = sub.add_parser("list")
    ls.add_argument("--status")
    ls.add_argument("--milestone")
    ls.add_argument("--all", action="store_true", help="include archive")

    a = sub.add_parser("archive")
    a.add_argument("--done", action="store_true")
    a.add_argument("--remove-worktrees", action="store_true",
                   help="also remove the ticket worktree and DELETE its branch t/<id>")

    args = p.parse_args()
    if args.cmd == "status":
        if len(args.ids) < 2:
            sys.exit("usage: ticket.py status <id> [<id>...] <new_status>")
        args.new_status = args.ids.pop()
    {"new": cmd_new, "new-batch": cmd_new_batch, "status": cmd_status, "list": cmd_list,
     "archive": cmd_archive}[args.cmd](args, root, cfg)


if __name__ == "__main__":
    main()
