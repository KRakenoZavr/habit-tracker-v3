# covers: [src/habits/api/**]
# verified_at: none
# owner: architect
#
# Internal wiring of habits.api (the HTTP surface itself is openapi.yaml — that file wins on any conflict).
# Imports allowed: fastapi, pydantic, habits.core, habits.storage, stdlib. Route handlers are plain `def` (sync).
# Handlers call habits.core services only; they never touch sqlalchemy or ORM rows directly.

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from fastapi import FastAPI, Request
from sqlalchemy.orm import Session
from habits.core import HabitRepository

# ---------------------------------------------------------------- habits/api/settings.py
@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = "sqlite:///./habits.db"
    timezone: str = "UTC"            # IANA name, validated with zoneinfo.ZoneInfo at load time
    @classmethod
    def from_env(cls) -> "Settings": ...  # HABITS_DATABASE_URL, HABITS_TIMEZONE; unset -> defaults

# ---------------------------------------------------------------- habits/api/deps.py
# app.state.settings: Settings; app.state.session_factory: sessionmaker[Session] (set by create_app)
def get_session(request: Request) -> Iterator[Session]: ...   # yield session; commit on success, rollback on exception, always close
def get_repo(session: Session = ...) -> HabitRepository: ...   # SqlHabitRepository(session)
def get_now() -> datetime: ...                                 # datetime.now(UTC)
def get_today(request: Request) -> date: ...                   # datetime.now(ZoneInfo(settings.timezone)).date()
# Tests override get_now / get_today via app.dependency_overrides.

# ---------------------------------------------------------------- habits/api/errors.py
def install_error_handlers(app: FastAPI) -> None:
    """DomainError -> status by code: *_not_found 404; checkin_exists, habit_archived 409;
    invalid_habit, invalid_range, future_checkin 422. Body {"error": {"code", "message": str(exc), "details": None}}.
    RequestValidationError -> 422 {"error": {"code": "validation_error", "message": "Request validation failed",
    "details": [{"loc": [...], "msg": str}]}}.
    starlette HTTPException (unknown route 404, 405, ...) -> same status and headers (e.g. Allow), body
    {"error": {"code": "not_found" | "method_not_allowed" | "http_<status>", "message": str(exc.detail), "details": None}}."""
# Request bodies are strict JSON: StrictInt / StrictBool / StrictStr (true or "3" for an int -> 422 validation_error).
# Response models have no defaults for contract-required fields (Health.status, ErrorBody.details).

# ---------------------------------------------------------------- habits/api/schemas.py
# Pydantic v2 models whose CLASS NAMES equal the openapi.yaml component names (the contract test compares them):
# Health, Habit, HabitCreate, HabitUpdate, CheckIn (M2), CheckInCreate (M2), Stats (M2), Error, ErrorBody, ErrorDetail.
# Import core types aliased to avoid the clash, e.g. `from habits import core`.

# ---------------------------------------------------------------- habits/api/app.py
def create_app(settings: Settings | None = None) -> FastAPI:
    """settings or Settings.from_env(); builds engine + session factory into app.state; installs error handlers;
    includes routers (routes/habits.py; routes/checkins.py in M2); GET /health. Never runs migrations."""
app: FastAPI   # = create_app()  -> `uv run uvicorn habits.api.app:app`
