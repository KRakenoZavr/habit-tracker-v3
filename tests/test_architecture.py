"""Architecture test: module import boundaries from docs/ai/modules.yaml (ADR-0002)."""

import ast
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN: dict[str, tuple[str, ...]] = {
    "habits.core": (
        "habits.storage",
        "habits.api",
        "sqlalchemy",
        "fastapi",
        "pydantic",
        "alembic",
        "starlette",
    ),
    "habits.storage": ("habits.api", "fastapi", "pydantic", "starlette"),
}


def imported_modules(source: str, module: str) -> set[str]:
    """Absolute dotted names imported by `source` (Import and ImportFrom).

    Relative imports are resolved against `module` (the dotted name of the file,
    e.g. "habits.core.rules").
    """
    found: set[str] = set()
    for bases, _members in _statement_imports(source, module):
        found.update(bases)
    return found


def _statement_imports(source: str, module: str) -> list[tuple[set[str], set[str]]]:
    """Per import statement: (imported module names, from-list member names)."""
    result: list[tuple[set[str], set[str]]] = []
    package = module.split(".")[:-1]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            result.append(({alias.name for alias in node.names}, set()))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)]
                if node.module:
                    base = [*base, *node.module.split(".")]
                name = ".".join(base)
            else:
                name = node.module or ""
            members = {
                f"{name}.{alias.name}" if name else alias.name for alias in node.names if alias.name != "*"
            }
            result.append(({name} if name else set(), members))
    return result


def _is_forbidden(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


def violations(src_root: Path) -> list[str]:
    """One "<file>: <imported>" string per forbidden import in src_root/habits/{core,storage}/**/*.py."""
    result: list[str] = []
    for package, prefixes in FORBIDDEN.items():
        pkg_dir = src_root.joinpath(*package.split("."))
        if not pkg_dir.is_dir():
            continue
        for path in sorted(pkg_dir.rglob("*.py")):
            rel = path.relative_to(src_root).with_suffix("")
            parts = list(rel.parts)
            if parts[-1] == "__init__":
                # An __init__ module is its own package for relative resolution.
                parts[-1] = "__init__"
            module = ".".join(parts)
            source = path.read_text(encoding="utf-8")
            hits: set[str] = set()
            for bases, members in _statement_imports(source, module):
                base_hits = {b for b in bases if _is_forbidden(b, prefixes)}
                hits.update(base_hits)
                for member in members:
                    # A member of an already-reported forbidden base in the same statement is not separate.
                    covered = any(member.startswith(b + ".") for b in base_hits)
                    if _is_forbidden(member, prefixes) and not covered:
                        hits.add(member)
            rel_path = path.relative_to(src_root).as_posix()
            result.extend(f"{rel_path}: {name}" for name in sorted(hits))
    return result


def test_no_forbidden_imports() -> None:
    assert violations(REPO_ROOT / "src") == []


def test_imported_modules_absolute() -> None:
    src = "import os\nimport sqlalchemy.orm\nfrom fastapi import FastAPI\n"
    assert imported_modules(src, "habits.core.rules") == {"os", "sqlalchemy.orm", "fastapi"}


def test_imported_modules_relative() -> None:
    assert imported_modules("from ..storage import a\n", "habits.core.rules") == {"habits.storage"}
    assert imported_modules("from . import b\n", "habits.core.rules") == {"habits.core"}
    assert imported_modules("from .sibling import c\n", "habits.core.rules") == {"habits.core.sibling"}


def test_prefix_match() -> None:
    prefixes = ("sqlalchemy",)
    assert _is_forbidden("sqlalchemy", prefixes)
    assert _is_forbidden("sqlalchemy.orm", prefixes)
    assert not _is_forbidden("sqlalchemyx", prefixes)


def test_violations_detects_from_list_members() -> None:
    for line in ("from habits import storage\n", "from .. import storage\n"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = root / "habits" / "core"
            core.mkdir(parents=True)
            (core / "rules.py").write_text(line, encoding="utf-8")
            assert violations(root) == ["habits/core/rules.py: habits.storage"]


def test_violations_reports_distinct_prefix_imports() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        core = root / "habits" / "core"
        core.mkdir(parents=True)
        (core / "bad.py").write_text("import sqlalchemy\nimport sqlalchemy.orm\n", encoding="utf-8")
        assert violations(root) == [
            "habits/core/bad.py: sqlalchemy",
            "habits/core/bad.py: sqlalchemy.orm",
        ]


def test_violations_detects_forbidden() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        core = root / "habits" / "core"
        core.mkdir(parents=True)
        (core / "bad.py").write_text("import sqlalchemy\nfrom ..storage import x\n", encoding="utf-8")
        (core / "ok.py").write_text("import datetime\n", encoding="utf-8")
        assert violations(root) == [
            "habits/core/bad.py: habits.storage",
            "habits/core/bad.py: sqlalchemy",
        ]
