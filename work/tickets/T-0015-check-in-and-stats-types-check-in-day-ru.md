---
id: T-0015
title: Check-in and stats types, check-in day rule and streak computation
status: approved  # draft|ready|in_progress|in_review|changes_requested|approved|integrated|done|blocked|escalated
milestone: M2
module: core  # from docs/ai/modules.yaml
depends_on: []  # ticket ids that must be integrated (merged into int/<milestone>) first
files_owned: [src/habits/core/models.py, src/habits/core/rules.py, src/habits/core/streaks.py, src/habits/core/__init__.py, tests/core/test_streaks.py]  # exact paths (globs allowed), within the tier's max. The ONLY files the executor may change.
                         # Tests first: include the test file(s) that prove the Acceptance criteria.
files_read: []  # contracts/stubs inlined into the pack. Keep tiny.
lock_resources: []       # lock files this ticket must touch (see .agents/config.json)
difficulty: M  # tier from .agents/config.json executor.tiers (S/M/L by default)
context_budget_tokens: none   # none = tier's pack_tokens; a number overrides it for this ticket
max_review_rounds: none       # none = budgets.max_review_rounds
review_round: 1
base: int/M2  # set by run_executor.py
tdd: none               # none = executor.tdd (tests first). false only for scaffolding/config/docs/test-only tickets; say why in Notes
verify: ["uv run --frozen pytest tests/core/test_streaks.py -x -q", "uv run --frozen ruff check src/habits/core tests/core", "uv run --frozen pyright src/habits/core tests/core/test_streaks.py"]  # e.g. ["pytest tests/core/test_x.py -x -q", "ruff check src/core/x.py"]
---
## Goal
Pure streak and progress math for daily and weekly habits (ADR-0005), plus the CheckIn/HabitStats types and the "no future check-ins" rule.

## Interface
```python
# models.py (add; keep everything that exists)
@dataclass(frozen=True, slots=True)
class CheckIn:
    habit_id: int
    day: date
    created_at: datetime   # tz-aware UTC
@dataclass(frozen=True, slots=True)
class HabitStats:
    habit_id: int
    streak_unit: Literal["day", "week"]
    current_streak: int
    longest_streak: int
    total_checkins: int
    period_count: int      # daily: 1 if today checked else 0; weekly: check-ins in this ISO week
    period_target: int     # daily: 1; weekly: target_per_week
    period_done: bool      # period_count >= period_target
    as_of: date            # the `today` used
# rules.py (add)
def validate_checkin_day(day: date, today: date) -> None: ...   # day > today -> FutureCheckIn(f"{day} is after today {today}")
# streaks.py (new)
def week_start(day: date) -> date: ...   # Monday of day's ISO week
def compute_stats(habit: Habit, days: Sequence[date], today: date) -> HabitStats:
    """days: check-in days of this habit (any order, no duplicates). Days > today are ignored.
    daily: current streak = consecutive days ending today, or ending yesterday if today is not checked; else 0.
    weekly: a week is met when count >= target_per_week; current = consecutive met weeks ending this week
    if met, else ending last week. longest = longest run anywhere (>= current). total_checkins counts days <= today."""
# __init__.py: also export CheckIn, HabitStats, validate_checkin_day, week_start, compute_stats
```

## Steps
1. Add the two dataclasses and `validate_checkin_day`.
2. `streaks.py`: daily runs over a sorted set of days; weekly: count per `week_start`, then runs of consecutive met weeks (step 7 days).
3. Tests first in `tests/core/test_streaks.py` with `today = date(2026, 1, 15)` (a Thursday; its week starts Mon 2026-01-12).

## Acceptance criteria
Daily habit; d(n) = date(2026, 1, n):
- [ ] {} → current 0, longest 0, period 0/1, not done; {d13,d14} → current 2 (grace), period 0/1 — `test_daily_grace`
- [ ] {d13,d14,d15} → current 3, period 1/1 done; {d12,d13} → current 0, longest 2 — `test_daily_current_and_broken`
- [ ] {d10,d11,d12,d14,d15} → current 2, longest 3; {d16} ignored → total 0 — `test_daily_longest_and_future_ignored`
Weekly habit, target 2:
- [ ] weeks of Dec 29 {Dec 29, Dec 31} and Jan 5 {d5,d7} met, this week {d12} → current 2, period 1/2 not done — `test_weekly_grace_current_week`
- [ ] same plus d14 → current 3, period 2/2 done — `test_weekly_current_week_met`
- [ ] Dec 29 week has only one day → current 1; longest counts the longest run across a gap — `test_weekly_gap_and_longest`
- [ ] `week_start` of Sun 2026-01-18 is Mon 2026-01-12; `validate_checkin_day(d16, d15)` raises FutureCheckIn, same day passes — `test_week_start_and_future_rule`

## Out of scope
- Repository port and services (next tickets). Storage, API.

## Notes from architect
- Stdlib only. `streak_unit` is "day" for daily, "week" for weekly; `period_target` for weekly is `target_per_week`.

## Log
- 2026-11-21 21:42 created from batch batch-M2.md (by architect)
- 2026-11-21 21:42 status draft -> ready (by architect)
- 2026-11-21 21:42 status ready -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 21:43 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:43 status in_review -> changes_requested (by run_review): round 1
- 2026-11-21 21:43 status changes_requested -> in_progress (by run_executor): tier M, claude-cli sonnet
- 2026-11-21 21:44 status in_progress -> in_review (by run_executor): gates passed
- 2026-11-21 21:44 status in_review -> approved (by run_review): round 2
