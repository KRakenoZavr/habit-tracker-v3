from __future__ import annotations

from datetime import datetime
from typing import Protocol

from habits.core.models import Habit, HabitDraft


class HabitRepository(Protocol):
    def add_habit(self, draft: HabitDraft, created_at: datetime) -> Habit: ...

    def get_habit(self, habit_id: int) -> Habit | None: ...

    def list_habits(self, include_archived: bool) -> list[Habit]: ...

    def update_habit(self, habit: Habit) -> Habit: ...

    def delete_habit(self, habit_id: int) -> bool: ...
