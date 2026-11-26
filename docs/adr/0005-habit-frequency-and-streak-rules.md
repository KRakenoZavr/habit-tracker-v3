# 0005 — Habit frequency and streak rules
Status: Proposed
Date: 2026-11-21
supersedes: none

## Context
Habits are either daily or "N times per week". Streaks must be deterministic, testable and not punish the user for
a period that is still in progress.

## Options
1. Daily streak in days, weekly streak in ISO weeks (Mon–Sun) that met the target, with grace for the current period.
2. Rolling 7-day windows for weekly habits — harder to explain, overlapping windows.
3. Convert weekly habits to a per-day schedule — needs per-weekday config (non-goal).

## Decision
Option 1. At most one check-in per habit per day; days after `today` are rejected (`future_checkin`).
Daily: `streak_unit = "day"`; current streak = run of consecutive checked days ending at `today`, or ending at
`today - 1` if today is not checked yet; else 0. Weekly (`target_per_week` 1..7): `streak_unit = "week"`; a week is
met when its check-ins ≥ target; current streak = run of consecutive met weeks ending at this week if met, else
ending at last week. Longest streak = longest run anywhere. `period_count`/`period_target` = today's 0|1 of 1 for
daily, this week's count of target for weekly. Archived habits keep their stats but reject new check-ins.

## Consequences
- Easier: pure functions over `(habit, sorted days, today)`; exhaustive table tests.
- Harder: changing the week start or adding weekday schedules needs a new ADR.
- Must change: `docs/ai/contracts/core.pyi` (`compute_stats`), `openapi.yaml` (`Stats`).
