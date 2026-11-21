from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from habits.core import (
    Frequency,
    FutureCheckIn,
    Habit,
    compute_stats,
    validate_checkin_day,
    week_start,
)

TODAY = date(2026, 1, 15)


def d(n: int) -> date:
    return date(2026, 1, n)


def _habit(frequency: Frequency, target: int | None = None) -> Habit:
    return Habit(
        id=1,
        name="h",
        description=None,
        frequency=frequency,
        target_per_week=target,
        archived=False,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _daily(days: list[date]):
    return compute_stats(_habit(Frequency.DAILY), days, TODAY)


def _weekly(days: list[date]):
    return compute_stats(_habit(Frequency.WEEKLY, 2), days, TODAY)


def test_daily_grace() -> None:
    s = _daily([])
    assert (s.current_streak, s.longest_streak) == (0, 0)
    assert (s.period_count, s.period_target, s.period_done) == (0, 1, False)
    assert s.streak_unit == "day"
    assert s.as_of == TODAY
    assert s.habit_id == 1

    s = _daily([d(13), d(14)])
    assert s.current_streak == 2
    assert (s.period_count, s.period_target, s.period_done) == (0, 1, False)


def test_daily_current_and_broken() -> None:
    s = _daily([d(15), d(13), d(14)])
    assert s.current_streak == 3
    assert (s.period_count, s.period_target, s.period_done) == (1, 1, True)

    s = _daily([d(12), d(13)])
    assert s.current_streak == 0
    assert s.longest_streak == 2


def test_daily_longest_and_future_ignored() -> None:
    s = _daily([d(10), d(11), d(12), d(14), d(15)])
    assert s.current_streak == 2
    assert s.longest_streak == 3
    assert s.total_checkins == 5

    s = _daily([d(16)])
    assert s.total_checkins == 0
    assert s.current_streak == 0
    assert s.longest_streak == 0


def test_weekly_grace_current_week() -> None:
    s = _weekly([date(2025, 12, 29), date(2025, 12, 31), d(5), d(7), d(12)])
    assert s.streak_unit == "week"
    assert s.current_streak == 2
    assert (s.period_count, s.period_target, s.period_done) == (1, 2, False)


def test_weekly_current_week_met() -> None:
    s = _weekly([date(2025, 12, 29), date(2025, 12, 31), d(5), d(7), d(12), d(14)])
    assert s.current_streak == 3
    assert (s.period_count, s.period_target, s.period_done) == (2, 2, True)


def test_weekly_gap_and_longest() -> None:
    days = [
        date(2025, 12, 1),
        date(2025, 12, 2),
        date(2025, 12, 8),
        date(2025, 12, 9),
        date(2025, 12, 29),
        d(5),
        d(7),
        d(12),
    ]
    s = _weekly(days)
    assert s.current_streak == 1
    assert s.longest_streak == 2
    assert s.total_checkins == 8


def test_week_start_and_future_rule() -> None:
    assert week_start(date(2026, 1, 18)) == d(12)
    assert week_start(d(12)) == d(12)
    with pytest.raises(FutureCheckIn) as excinfo:
        validate_checkin_day(d(16), d(15))
    assert str(excinfo.value) == "2026-01-16 is after today 2026-01-15"
    validate_checkin_day(d(15), d(15))


def test_daily_at_date_min() -> None:
    habit = _habit(Frequency.DAILY)
    s = compute_stats(habit, [], date.min)
    assert (s.current_streak, s.longest_streak) == (0, 0)
    s = compute_stats(habit, [date.min], date.min)
    assert (s.current_streak, s.longest_streak) == (1, 1)


def test_weekly_at_date_min() -> None:
    habit = _habit(Frequency.WEEKLY, 2)
    s = compute_stats(habit, [date.min], date.min)
    assert (s.current_streak, s.longest_streak) == (0, 0)
    assert (s.period_count, s.period_done) == (1, False)
    tuesday = date.min + timedelta(days=1)
    s = compute_stats(habit, [date.min, tuesday], tuesday)
    assert (s.current_streak, s.longest_streak) == (1, 1)
    assert s.period_done is True
