---
covers: [docs/plan/**]
verified_at: none
owner: architect
---
# Glossary
| Term | Meaning | Code name |
|---|---|---|
| Habit | Something the user wants to do regularly | `Habit`, `HabitRow` |
| Frequency | `daily` or `weekly` (N times per ISO week) | `Frequency` |
| Target | Check-ins per week a weekly habit needs (1..7) | `target_per_week` |
| Check-in | "Done on this day" for one habit; max one per day | `CheckIn`, `CheckInRow` |
| Day | Calendar date of a check-in in `HABITS_TIMEZONE` | `day` |
| Today | Current date in `HABITS_TIMEZONE`, injected | `today`, `get_today` |
| Period | Today (daily) or the current ISO week Mon–Sun (weekly) | `period_count`, `period_target` |
| Streak | Consecutive met periods (days or weeks), see ADR-0005 | `current_streak`, `longest_streak` |
| Archived | Hidden from default list; keeps stats; rejects check-ins | `archived` |
