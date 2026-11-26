from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from typing import Literal

from habits.core.models import Frequency, Habit, HabitStats


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _longest_run(units: Iterable[date], step: timedelta) -> int:
    longest = 0
    run = 0
    previous: date | None = None
    for unit in sorted(units):
        run = run + 1 if previous is not None and unit - previous == step else 1
        longest = max(longest, run)
        previous = unit
    return longest


def _previous(unit: date, step: timedelta) -> date | None:
    return unit - step if unit >= date.min + step else None


def _run_ending_at(units: set[date], end: date | None, step: timedelta) -> int:
    count = 0
    while end is not None and end in units:
        count += 1
        end = _previous(end, step)
    return count


def compute_stats(habit: Habit, days: Sequence[date], today: date) -> HabitStats:
    valid = {day for day in days if day <= today}
    if habit.frequency is Frequency.WEEKLY:
        target = habit.target_per_week or 1
        counts = Counter(week_start(day) for day in valid)
        met = {week for week, count in counts.items() if count >= target}
        this_week = week_start(today)
        step = timedelta(days=7)
        end = this_week if this_week in met else _previous(this_week, step)
        current = _run_ending_at(met, end, step)
        longest = _longest_run(met, step)
        period_count = counts.get(this_week, 0)
        unit: Literal["day", "week"] = "week"
    else:
        target = 1
        step = timedelta(days=1)
        end = today if today in valid else _previous(today, step)
        current = _run_ending_at(valid, end, step)
        longest = _longest_run(valid, step)
        period_count = 1 if today in valid else 0
        unit = "day"
    return HabitStats(
        habit_id=habit.id,
        streak_unit=unit,
        current_streak=current,
        longest_streak=longest,
        total_checkins=len(valid),
        period_count=period_count,
        period_target=target,
        period_done=period_count >= target,
        as_of=today,
    )
