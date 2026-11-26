# 0004 — Contract-first OpenAPI and one error envelope
Status: Proposed
Date: 2026-11-21
supersedes: none

## Context
FastAPI generates an OpenAPI document from code, but then the code is the spec and drift is invisible. Executors
need a fixed target, and clients need one predictable error shape.

## Options
1. Hand-written `docs/ai/contracts/openapi.yaml` as source of truth + a conformance test against `app.openapi()`.
2. Code-first: publish whatever FastAPI generates — no review point for API changes.
3. Generate server stubs from the YAML — extra tooling, poor fit with FastAPI.

## Decision
Option 1. The YAML is reviewed like code; an API change is a contract ticket first. A test checks that every path,
method and documented status code in the YAML exists in `app.openapi()` and that response schema names match.
All errors use `{"error": {"code": str, "message": str, "details": list | null}}`: domain errors map by `code`
(404 `*_not_found`, 409 `checkin_exists`/`habit_archived`, 422 `invalid_*`/`future_checkin`), FastAPI request
validation becomes 422 `validation_error` with `details` = `[{"loc": [...], "msg": str}]`.

## Consequences
- Easier: reviewers check behavior against one file; clients parse one error shape.
- Harder: the YAML and the Pydantic schemas are kept in sync by hand (the test catches drift).
- Must change: routes declare `responses=` for every non-2xx code they return.
