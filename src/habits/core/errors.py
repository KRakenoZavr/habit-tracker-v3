from __future__ import annotations

from typing import ClassVar


class DomainError(Exception):
    code: ClassVar[str] = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidHabit(DomainError):
    code = "invalid_habit"


class InvalidRange(DomainError):
    code = "invalid_range"


class FutureCheckIn(DomainError):
    code = "future_checkin"


class HabitNotFound(DomainError):
    code = "habit_not_found"


class CheckInNotFound(DomainError):
    code = "checkin_not_found"


class CheckInExists(DomainError):
    code = "checkin_exists"


class HabitArchived(DomainError):
    code = "habit_archived"
