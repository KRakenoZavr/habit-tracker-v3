from pathlib import Path
from typing import Any

import pytest
import yaml

from habits.api.app import create_app
from habits.api.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "docs/ai/contracts/openapi.yaml").read_text(encoding="utf-8")
)
APP: dict[str, Any] = create_app(Settings(database_url="sqlite://")).openapi()

METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}
OPERATIONS: list[tuple[str, str]] = [
    (path, method) for path, item in CONTRACT["paths"].items() for method in item if method in METHODS
]
IDS = [f"{method.upper()} {path}" for path, method in OPERATIONS]


def ref_name(schema: dict[str, Any]) -> str | None:
    """Component name of a $ref (last path part); looks inside "items" and "anyOf"."""
    if not schema:
        return None
    if "$ref" in schema:
        return str(schema["$ref"]).rsplit("/", 1)[-1]
    items = schema.get("items")
    if isinstance(items, dict):
        found = ref_name(items)
        if found:
            return found
    for option in schema.get("anyOf", []):
        found = ref_name(option)
        if found:
            return found
    return None


def _json_schema(content: dict[str, Any] | None) -> dict[str, Any] | None:
    if not content or "application/json" not in content:
        return None
    return content["application/json"].get("schema") or {}


def _contract_response(response: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in response:
        return CONTRACT["components"]["responses"][ref_name(response)]
    return response


@pytest.mark.parametrize(("path", "method"), OPERATIONS, ids=IDS)
def test_operation_exists(path: str, method: str) -> None:
    assert path in APP["paths"]
    assert method in APP["paths"][path]


@pytest.mark.parametrize(("path", "method"), OPERATIONS, ids=IDS)
def test_status_codes(path: str, method: str) -> None:
    expected = set(CONTRACT["paths"][path][method]["responses"])
    actual = set(APP["paths"][path][method]["responses"])
    assert expected <= actual


@pytest.mark.parametrize(("path", "method"), OPERATIONS, ids=IDS)
def test_response_schema_names(path: str, method: str) -> None:
    responses = CONTRACT["paths"][path][method]["responses"]
    for status, response in responses.items():
        if not status.startswith("2"):
            continue
        schema = _json_schema(_contract_response(response).get("content"))
        if schema is None:
            continue
        app_schema = _json_schema(APP["paths"][path][method]["responses"][status].get("content"))
        assert app_schema is not None
        assert ref_name(app_schema) == ref_name(schema)


@pytest.mark.parametrize(("path", "method"), OPERATIONS, ids=IDS)
def test_request_schema_names(path: str, method: str) -> None:
    body = CONTRACT["paths"][path][method].get("requestBody")
    if body is None:
        return
    app_body = APP["paths"][path][method].get("requestBody")
    assert app_body is not None
    expected = _json_schema(body["content"]) or {}
    actual = _json_schema(app_body.get("content")) or {}
    assert ref_name(actual) == ref_name(expected)


def test_referenced_components_exist() -> None:
    names: set[str] = set()
    for path, method in OPERATIONS:
        operation = CONTRACT["paths"][path][method]
        for response in operation["responses"].values():
            names.add(ref_name(_json_schema(_contract_response(response).get("content")) or {}) or "")
        body = operation.get("requestBody")
        if body:
            names.add(ref_name(_json_schema(body["content"]) or {}) or "")
    names.discard("")
    assert "Error" in names
    assert names <= set(APP["components"]["schemas"])


@pytest.mark.parametrize(("path", "method"), OPERATIONS, ids=IDS)
def test_error_responses_reference_error(path: str, method: str) -> None:
    responses = CONTRACT["paths"][path][method]["responses"]
    for status in responses:
        if not status.startswith("4"):
            continue
        app_response = APP["paths"][path][method]["responses"][status]
        schema = _json_schema(app_response.get("content"))
        assert schema is not None
        assert ref_name(schema) == "Error"
