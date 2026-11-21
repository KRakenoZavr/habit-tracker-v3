---
name: reviewer
description: Reviews one ticket in status in_review. Fallback only — the default reviewer is Codex via scripts/agent/run_review.py so the executor is not graded by a similar model.
tools: Read, Grep, Glob, Bash, Write
---
Follow `.agents/roles/reviewer.md` and the skill `.agents/skills/review-ticket/SKILL.md`. Write only under `work/reviews/`.
