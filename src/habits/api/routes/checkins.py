"""Check-in and stats routes."""

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Response

from habits.api import schemas
from habits.api.deps import get_now, get_repo, get_today
from habits.core import HabitRepository, services

router = APIRouter()

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": schemas.Error},
    422: {"model": schemas.Error},
}
_CREATE: dict[int | str, dict[str, Any]] = {
    404: {"model": schemas.Error},
    409: {"model": schemas.Error},
    422: {"model": schemas.Error},
}


@router.post(
    "/habits/{habit_id}/checkins",
    operation_id="create_checkin",
    status_code=201,
    responses=_CREATE,
)
def create_checkin(
    habit_id: int,
    body: schemas.CheckInCreate | None = None,
    repo: HabitRepository = Depends(get_repo),
    today: date = Depends(get_today),
    now: datetime = Depends(get_now),
) -> schemas.CheckIn:
    day = body.day if body and body.day else today
    return schemas.CheckIn.from_core(services.check_in(repo, habit_id, day, today, now))


@router.get("/habits/{habit_id}/checkins", operation_id="list_checkins", responses=_NOT_FOUND)
def list_checkins(
    habit_id: int,
    start: date | None = None,
    end: date | None = None,
    repo: HabitRepository = Depends(get_repo),
) -> list[schemas.CheckIn]:
    checkins = services.list_check_ins(repo, habit_id, start, end)
    return [schemas.CheckIn.from_core(c) for c in checkins]


@router.delete(
    "/habits/{habit_id}/checkins/{day}",
    operation_id="delete_checkin",
    status_code=204,
    responses=_NOT_FOUND,
)
def delete_checkin(
    habit_id: int,
    day: date,
    repo: HabitRepository = Depends(get_repo),
) -> Response:
    services.undo_check_in(repo, habit_id, day)
    return Response(status_code=204)


@router.get("/habits/{habit_id}/stats", operation_id="get_stats", responses=_NOT_FOUND)
def get_stats(
    habit_id: int,
    repo: HabitRepository = Depends(get_repo),
    today: date = Depends(get_today),
) -> schemas.Stats:
    return schemas.Stats.from_core(services.get_stats(repo, habit_id, today))
