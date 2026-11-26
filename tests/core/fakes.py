from datetime import date, datetime

from habits.core import CheckIn, CheckInExists, Habit, HabitDraft


class FakeHabitRepository:
    def __init__(self) -> None:
        self._habits: dict[int, Habit] = {}
        self._checkins: dict[tuple[int, date], CheckIn] = {}
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
        existed = self._habits.pop(habit_id, None) is not None
        for key in [k for k in self._checkins if k[0] == habit_id]:
            del self._checkins[key]
        return existed

    def add_checkin(self, habit_id: int, day: date, created_at: datetime) -> CheckIn:
        if (habit_id, day) in self._checkins:
            raise CheckInExists(f"check-in for habit {habit_id} on {day} exists")
        checkin = CheckIn(habit_id=habit_id, day=day, created_at=created_at)
        self._checkins[(habit_id, day)] = checkin
        return checkin

    def delete_checkin(self, habit_id: int, day: date) -> bool:
        return self._checkins.pop((habit_id, day), None) is not None

    def list_checkins(self, habit_id: int, start: date | None, end: date | None) -> list[CheckIn]:
        found = [c for (hid, _), c in self._checkins.items() if hid == habit_id]
        found = [c for c in found if (start is None or c.day >= start) and (end is None or c.day <= end)]
        return sorted(found, key=lambda c: c.day)
