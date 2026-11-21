from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from habits.api.schemas import Error
from habits.core import DomainError

STATUS_BY_CODE: dict[str, int] = {
    "habit_not_found": 404,
    "checkin_not_found": 404,
    "checkin_exists": 409,
    "habit_archived": 409,
    "invalid_habit": 422,
    "invalid_range": 422,
    "future_checkin": 422,
}


def _envelope(code: str, message: str, details: list[dict[str, Any]] | None) -> dict[str, Any]:
    body = {"error": {"code": code, "message": message, "details": details}}
    return Error.model_validate(body).model_dump()


async def _domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    status = STATUS_BY_CODE.get(exc.code, 400)
    return JSONResponse(status_code=status, content=_envelope(exc.code, str(exc), None))


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content=_envelope("validation_error", "Request validation failed", details),
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
