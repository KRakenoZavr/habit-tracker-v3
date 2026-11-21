# Profile: Python
- Layout: `src/<package>/`, tests in `tests/` mirroring `src/`. Python ≥3.11.
- Gates (`verify.commands`): `ruff format --check .`, `ruff check .`, `pyright`, `pytest -x -q`.
- Auto-fix before the gates (`verify.fix_commands`): `ruff format {files}`, `ruff check --fix-only {files}` (prefix `uv run --frozen` with uv).
- Generated, names only (`generated_globs`): `uv.lock`/`poetry.lock` are already covered by `**/*.lock`.
- Ticket verify: `pytest tests/<path>/test_x.py -x -q` + `ruff check <owned paths>` + `pyright <owned paths>`.
- Contracts: `.pyi` stubs or Pydantic models in `docs/ai/contracts/`. Full type hints on every public function — small models work far better from typed signatures.
- Lock resources: `pyproject.toml`, `uv.lock`/`poetry.lock`, `migrations/**`, `alembic/versions/**`.
- Dependencies are added only by the architect, never inside an S/M ticket.
- `.gitignore`: `.venv/ .pytest_cache/ .ruff_cache/ .mypy_cache/ dist/ *.egg-info/`
