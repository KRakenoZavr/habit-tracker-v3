# Changelog
<!-- One entry per merged milestone PR, newest first. Generated from done tickets + ADRs (skill: update-docs). -->

## M2 — Check-ins, streaks and stats (2026-11-21)
### Added
- Check-in/stats types, future-day rule and streak computation for daily and weekly habits (T-0015)
- `checkins` table (migration 0002, unique per day, cascade on habit delete) and repository methods (T-0016)
- Check-in, undo, list-by-range and stats use cases on the repository port (T-0017)
- `CheckIn`, `CheckInCreate`, `Stats` schemas (T-0018)
- `POST/GET /habits/{id}/checkins`, `DELETE /habits/{id}/checkins/{day}`, `GET /habits/{id}/stats` (T-0019)
- OpenAPI contract conformance test (T-0020)

## M1 — Walking skeleton: habits CRUD end to end (2026-11-21)
### Added
- Core models, domain errors and habit validation (T-0001); repository port and habit use cases (T-0002)
- Import-boundary test (T-0003, T-0014); engine/session and `habits` ORM model (T-0004)
- Alembic setup, migration 0001, migrated-DB fixture and drift test (T-0005, T-0011)
- `SqlHabitRepository` (T-0006, T-0010); settings and schemas (T-0007, T-0012); error envelope (T-0008, T-0013)
- App factory, per-request session and `/health`, `/habits` CRUD routes (T-0009)
### Changed
- Milestone review hardening: strict JSON body types, envelope for 404/405, int64 id bounds, single-statement delete.
### Decisions
- ADR-0001 Python + FastAPI + SQLite, locked with uv
- ADR-0002 core / storage / api layering, single user
- ADR-0003 SQLAlchemy 2 sync + Alembic, drift test
- ADR-0004 Contract-first OpenAPI, one error envelope
- ADR-0005 Habit frequency and streak rules
