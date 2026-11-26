---
covers: [docs/plan/**]
verified_at: none
owner: architect
---
# Milestones
<!--
Each milestone is a shippable, testable slice and ends in ONE PR from int/<id>.
Acceptance criteria here are what the architect's holistic review and the tester check.
-->

## M1 — Walking skeleton: habits CRUD end to end
Goal: create, read, list, update, archive and delete habits over HTTP, persisted in SQLite through an Alembic migration.
Acceptance:
- [ ] `uv run alembic upgrade head` on an empty DB creates the `habits` table; migration drift test passes.
- [ ] `GET /health`, `POST/GET /habits`, `GET/PATCH/DELETE /habits/{habit_id}` behave as in `openapi.yaml`.
- [ ] Errors use the `Error` envelope (`{"error": {"code", "message", "details"}}`), including request validation (422).
- [ ] Domain rules (name length, daily vs weekly target) live in `habits.core` and are unit tested without a DB.
- [ ] Import-boundary test: `core` imports no `sqlalchemy`/`fastapi`/`habits.storage`/`habits.api`; `storage` imports no `habits.api`/`fastapi`.
- [ ] `uv run uvicorn habits.api.app:app` serves the API (smoke test through `create_app`).
- [ ] `python scripts/agent/verify.py` passes on int/M1
Out of scope: check-ins, streaks, stats.

## M2 — Check-ins, streaks and stats
Goal: record and undo daily check-ins and report streaks/progress for daily and weekly habits.
Acceptance:
- [ ] Migration `0002` adds `checkins` with `UNIQUE(habit_id, day)` and `ON DELETE CASCADE`; drift test passes.
- [ ] `POST/GET /habits/{habit_id}/checkins`, `DELETE /habits/{habit_id}/checkins/{day}`, `GET /habits/{habit_id}/stats` behave as in `openapi.yaml`.
- [ ] Future days → 422 `future_checkin`; duplicate day → 409 `checkin_exists`; archived habit → 409 `habit_archived`.
- [ ] Streak rules of ADR-0005 are unit tested in `habits.core` (daily, weekly, grace for the current period, longest streak).
- [ ] Contract test: every path + method + documented status code in `openapi.yaml` exists in `app.openapi()`.
- [ ] `python scripts/agent/verify.py` passes on int/M2
Out of scope: reminders, per-weekday schedules, more than one check-in per day.
