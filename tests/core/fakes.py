from datetime import datetime

from habits.core import Habit, HabitDraft


class FakeHabitRepository:
    def __init__(self) -> None:
        self._habits: dict[int, Habit] = {}
        self._next_id = 1

    def add_habit(self, draft: HabitDraft, created_at: datetime) -> Habit:
        habit = Habit(
            id=self._next_id,
            name=draft.name,
            description=draft.description,
            frequency=draft.frequency,
            target_per_week=draft.target_per_week,
            archived=False,
            created_at=created_at,
        )
        self._habits[habit.id] = habit
        self._next_id += 1
        return habit

    def get_habit(self, habit_id: int) -> Habit | None:
        return self._habits.get(habit_id)

    def list_habits(self, include_archived: bool) -> list[Habit]:
        habits = sorted(self._habits.values(), key=lambda h: h.id)
        if include_archived:
            return habits
        return [h for h in habits if not h.archived]

    def update_habit(self, habit: Habit) -> Habit:
        self._habits[habit.id] = habit
        return habit

    def delete_habit(self, habit_id: int) -> bool:
        return self._habits.pop(habit_id, None) is not None
