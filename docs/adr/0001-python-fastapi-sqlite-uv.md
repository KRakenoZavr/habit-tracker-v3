# 0001 — Python 3.12 + FastAPI + SQLite, dependencies locked with uv
Status: Proposed
Date: 2026-11-21
supersedes: none

## Context
A small single-user HTTP API that must be easy to run locally on Windows/Linux/macOS, cheap for small models to
work on, and reproducible across agent worktrees.

## Options
1. FastAPI + SQLite + uv — typed, OpenAPI for free, zero-ops DB, one fast tool for venv + lock.
2. Flask + SQLite + pip/requirements.txt — fewer types, no lock file with hashes, manual OpenAPI.
3. FastAPI + Postgres — real server DB; needs Docker/ops for a single-user tool.

## Decision
Python 3.12, FastAPI, Pydantic v2, SQLite. `uv` manages the venv; `pyproject.toml` declares dependencies and
`uv.lock` pins them. Every gate runs as `uv run --frozen ...`, so a worker can never silently change the lock.
Only the architect adds dependencies (`uv add`), never a ticket. `tzdata` is a dependency so `zoneinfo` works on Windows.

## Consequences
- Easier: one command (`uv sync --frozen`) reproduces the env in every ticket worktree.
- Harder: SQLite limits (one writer, limited `ALTER TABLE`) — see ADR-0003.
- Must change: `pyproject.toml` and `uv.lock` are protected; `migrations/**`, `alembic.ini` are lock resources.
