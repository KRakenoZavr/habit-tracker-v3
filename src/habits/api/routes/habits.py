"""Habit CRUD routes."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Response

from habits.api import schemas
from habits.api.deps import get_now, get_repo
from habits.core import HabitRepository, services

router = APIRouter()

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": schemas.Error},
    422: {"model": schemas.Error},
}
_INVALID: dict[int | str, dict[str, Any]] = {422: {"model": schemas.Error}}


@router.get("/habits", operation_id="list_habits", responses=_INVALID)
def list_habits(
    include_archived: bool = False,
    repo: HabitRepository = Depends(get_repo),
) -> list[schemas.Habit]:
    habits = services.list_habits(repo, include_archived)
    return [schemas.Habit.from_core(h) for h in habits]


@router.post("/habits", operation_id="create_habit", status_code=201, responses=_INVALID)
def create_habit(
    body: schemas.HabitCreate,
    repo: HabitRepository = Depends(get_repo),
    now: datetime = Depends(get_now),
) -> schemas.Habit:
    habit = services.create_habit(repo, body.to_draft(), now)
    return schemas.Habit.from_core(habit)


@router.get("/habits/{habit_id}", operation_id="get_habit", responses=_NOT_FOUND)
def get_habit(
    habit_id: int,
    repo: HabitRepository = Depends(get_repo),
) -> schemas.Habit:
    return schemas.Habit.from_core(services.get_habit(repo, habit_id))


@router.patch("/habits/{habit_id}", operation_id="update_habit", responses=_NOT_FOUND)
def update_habit(
    habit_id: int,
    body: schemas.HabitUpdate,
    repo: HabitRepository = Depends(get_repo),
) -> schemas.Habit:
    habit = services.update_habit(repo, habit_id, body.to_patch())
    return schemas.Habit.from_core(habit)


@router.delete("/habits/{habit_id}", operation_id="delete_habit", status_code=204, responses=_NOT_FOUND)
def delete_habit(
    habit_id: int,
    repo: HabitRepository = Depends(get_repo),
) -> Response:
    services.delete_habit(repo, habit_id)
    return Response(status_code=204)
