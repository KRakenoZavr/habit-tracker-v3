from __future__ import annotations

from dataclasses import replace

from habits.core.errors import InvalidHabit
from habits.core.models import (
    DESCRIPTION_MAX,
    NAME_MAX,
    Frequency,
    Habit,
    HabitDraft,
    HabitPatch,
)


def _check_name(name: str) -> str:
    name = name.strip()
    if not 1 <= len(name) <= NAME_MAX:
        raise InvalidHabit(f"name must be 1..{NAME_MAX} characters")
    return name


def _check_description(description: str | None) -> str | None:
    if description is None:
        return None
    description = description.strip()
    if not description:
        return None
    if len(description) > DESCRIPTION_MAX:
        raise InvalidHabit(f"description must be at most {DESCRIPTION_MAX} characters")
    return description


def _check_target(frequency: Frequency, target: int | None) -> int | None:
    if type(frequency) is not Frequency:
        raise InvalidHabit("frequency must be daily or weekly")
    if frequency is Frequency.DAILY:
        if target is not None:
            raise InvalidHabit("target_per_week must be empty for daily habits")
        return None
    if type(target) is not int or not 1 <= target <= 7:
        raise InvalidHabit("target_per_week must be 1..7 for weekly habits")
    return target


def validate_draft(draft: HabitDraft) -> HabitDraft:
    return replace(
        draft,
        name=_check_name(draft.name),
        description=_check_description(draft.description),
        target_per_week=_check_target(draft.frequency, draft.target_per_week),
    )


def apply_patch(habit: Habit, patch: HabitPatch) -> Habit:
    frequency = patch.frequency if patch.frequency is not None else habit.frequency
    if frequency is Frequency.DAILY:
        if patch.target_per_week is not None:
            raise InvalidHabit("target_per_week must be empty for daily habits")
        target = None
    elif patch.target_per_week is not None:
        target = patch.target_per_week
    elif habit.frequency is Frequency.WEEKLY:
        target = habit.target_per_week
    else:
        target = None
    description = habit.description if patch.description is None else patch.description
    return replace(
        habit,
        name=_check_name(patch.name if patch.name is not None else habit.name),
        description=_check_description(description),
        frequency=frequency,
        target_per_week=_check_target(frequency, target),
        archived=patch.archived if patch.archived is not None else habit.archived,
    )
