---
name: review-ticket
description: Review one ticket's diff against its acceptance criteria and contract and give a verdict. Use when a ticket is in status in_review and you are asked to review it interactively (normally run_review.py does this with Codex).
---

# Review a ticket (interactive fallback)

Normally the architect or `run_loop.py` runs `python scripts/agent/run_review.py <id>`, which sends the packet to the
reviewer CLI and applies the verdict. Use this skill only when reviewing by hand or as a fallback reviewer.

1. Build the packet: `python scripts/agent/pack.py <id> --review` and read only its output.
2. Follow `.agents/roles/reviewer.md`, including its evidence rule (no unverifiable "untested" findings).
3. Save your answer (the packet's output format) as `work/reviews/<id>.r<round>.md`, where round = `review_round + 1`.
   Add `reviewed_commit: <sha of t/<id>>` to its frontmatter so the next round can be incremental.
4. Apply the verdict: `python scripts/agent/ticket.py status <id> <approved|changes_requested|escalated> --by reviewer`.
