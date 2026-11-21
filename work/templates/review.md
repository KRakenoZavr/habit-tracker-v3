---
ticket: T-0000
round: 1
verdict: changes_requested   # approved | changes_requested | escalated
reviewer_model: <model>
gates: {verify: pass, owned_diff: pass}
---
## Findings (max 5, most severe first)
1. [blocker] `path/file.ext:42` — <what is wrong>. Required: <exact change>.
2. [minor] `path/file.ext:10` — <...>

## Do NOT change
- <things that are correct; the executor must keep them as they are>

## Note for architect (only if escalated)
- <why the ticket itself is wrong: missing file, bad contract, too big>
