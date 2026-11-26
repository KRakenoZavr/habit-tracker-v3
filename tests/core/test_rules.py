from __future__ import annotations

from datetime import UTC, datetime

import pytest

from habits.core import (
    DESCRIPTION_MAX,
    NAME_MAX,
    CheckInExists,
    CheckInNotFound,
    DomainError,
    Frequency,
    FutureCheckIn,
    Habit,
    HabitArchived,
    HabitDraft,
    HabitNotFound,
    HabitPatch,
    InvalidHabit,
    InvalidRange,
    apply_patch,
    validate_draft,
)

CREATED = datetime(2026, 1, 1, tzinfo=UTC)


def make_habit(
    frequency: Frequency = Frequency.DAILY,
    target: int | None = None,
    description: str | None = "desc",
) -> Habit:
    return Habit(
        id=7,
        name="Read",
        description=description,
        frequency=frequency,
        target_per_week=target,
        archived=False,
        created_at=CREATED,
    )


def test_validate_draft_name() -> None:
    assert validate_draft(HabitDraft(name="  Read  ")).name == "Read"
    assert validate_draft(HabitDraft(name="a" * NAME_MAX)).name == "a" * NAME_MAX
    for bad in ["", "   ", "a" * (NAME_MAX + 1)]:
        with pytest.raises(InvalidHabit):
            validate_draft(HabitDraft(name=bad))


def test_validate_draft_description() -> None:
    assert validate_draft(HabitDraft(name="x", description="")).description is None
    assert validate_draft(HabitDraft(name="x", description="  \n ")).description is None
    assert validate_draft(HabitDraft(name="x", description=" hi ")).description == "hi"
    assert validate_draft(HabitDraft(name="x")).description is None
    ok = "d" * DESCRIPTION_MAX
    assert validate_draft(HabitDraft(name="x", description=ok)).description == ok
    with pytest.raises(InvalidHabit):
        validate_draft(HabitDraft(name="x", description="d" * (DESCRIPTION_MAX + 1)))


def test_validate_draft_frequency_target() -> None:
    with pytest.raises(InvalidHabit):
        validate_draft(HabitDraft(name="x", target_per_week=3))
    for bad in [None, 0, 8]:
        with pytest.raises(InvalidHabit):
            validate_draft(HabitDraft(name="x", frequency=Frequency.WEEKLY, target_per_week=bad))
    for good in [1, 7]:
        out = validate_draft(HabitDraft(name="x", frequency=Frequency.WEEKLY, target_per_week=good))
        assert out.target_per_week == good
    assert validate_draft(HabitDraft(name="x")).target_per_week is None


def test_apply_patch_empty_unchanged() -> None:
    h = make_habit()
    assert apply_patch(h, HabitPatch()) == h
    w = make_habit(Frequency.WEEKLY, 3)
    assert apply_patch(w, HabitPatch()) == w


def test_apply_patch_fields() -> None:
    h = make_habit()
    assert apply_patch(h, HabitPatch(name="  New ")).name == "New"
    assert apply_patch(h, HabitPatch(description="")).description is None
    assert apply_patch(h, HabitPatch(description=" x ")).description == "x"
    assert apply_patch(h, HabitPatch(archived=True)).archived is True
    assert (
        apply_patch(apply_patch(h, HabitPatch(archived=True)), HabitPatch(archived=False)).archived is False
    )
    with pytest.raises(InvalidHabit):
        apply_patch(h, HabitPatch(name=" "))
    with pytest.raises(InvalidHabit):
        apply_patch(h, HabitPatch(description="d" * (DESCRIPTION_MAX + 1)))


def test_apply_patch_frequency_changes() -> None:
    w = make_habit(Frequency.WEEKLY, 3)
    out = apply_patch(w, HabitPatch(frequency=Frequency.DAILY))
    assert out.frequency is Frequency.DAILY
    assert out.target_per_week is None
    with pytest.raises(InvalidHabit):
        apply_patch(w, HabitPatch(frequency=Frequency.DAILY, target_per_week=2))
    d = make_habit()
    with pytest.raises(InvalidHabit):
        apply_patch(d, HabitPatch(frequency=Frequency.WEEKLY))
    with pytest.raises(InvalidHabit):
        apply_patch(d, HabitPatch(target_per_week=2))
    up = apply_patch(d, HabitPatch(frequency=Frequency.WEEKLY, target_per_week=4))
    assert (up.frequency, up.target_per_week) == (Frequency.WEEKLY, 4)
    assert apply_patch(w, HabitPatch(target_per_week=5)).target_per_week == 5
    for bad in [0, 8]:
        with pytest.raises(InvalidHabit):
            apply_patch(w, HabitPatch(target_per_week=bad))


def test_rejects_invalid_frequency() -> None:
    with pytest.raises(InvalidHabit):
        validate_draft(HabitDraft(name="x", frequency="monthly", target_per_week=3))  # type: ignore[arg-type]
    with pytest.raises(InvalidHabit):
        apply_patch(make_habit(), HabitPatch(frequency="monthly", target_per_week=3))  # type: ignore[arg-type]
    with pytest.raises(InvalidHabit):
        apply_patch(make_habit(Frequency.WEEKLY, 3), HabitPatch(frequency="monthly"))  # type: ignore[arg-type]


def test_rejects_non_int_target() -> None:
    for bad in [1.5, True]:
        with pytest.raises(InvalidHabit):
            validate_draft(
                HabitDraft(name="x", frequency=Frequency.WEEKLY, target_per_week=bad)  # type: ignore[arg-type]
            )
        with pytest.raises(InvalidHabit):
            apply_patch(
                make_habit(Frequency.WEEKLY, 3),
                HabitPatch(target_per_week=bad),  # type: ignore[arg-type]
            )


def test_apply_patch_keeps_identity() -> None:
    out = apply_patch(make_habit(), HabitPatch(name="Other", archived=True))
    assert out.id == 7
    assert out.created_at == CREATED


@pytest.mark.parametrize(
    ("cls", "code"),
    [
        (InvalidHabit, "invalid_habit"),
        (InvalidRange, "invalid_range"),
        (FutureCheckIn, "future_checkin"),
        (HabitNotFound, "habit_not_found"),
        (CheckInNotFound, "checkin_not_found"),
        (CheckInExists, "checkin_exists"),
        (HabitArchived, "habit_archived"),
    ],
)
def test_error_codes(cls: type[DomainError], code: str) -> None:
    err = cls("boom")
    assert isinstance(err, DomainError)
    assert err.code == code
    assert err.message == "boom"
    assert str(err) == "boom"
