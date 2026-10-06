"""What the image runs has to be something the image declares.

This file exists because of an outage that every other gate missed. A dependency
was dropped from `pyproject.toml` by accident: `ruff` passed, `mypy` passed and
all 678 tests passed, because **nothing in the suite imports uvicorn**. The only
thing that noticed was `docker compose up`, which failed with
`exec: "uvicorn": executable file not found in $PATH`.

That is the shape of the failure worth guarding: the build is green, the tests
are green, and the service is dead. A test cannot import the entrypoint, but it
can read what the Dockerfile asks for and check that it was ever declared.
"""

import re
import tomllib
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = BACKEND_ROOT / "Dockerfile"
PYPROJECT = BACKEND_ROOT / "pyproject.toml"


def _declared_runtime_dependencies() -> set[str]:
    """Distribution names in `[project.dependencies]`, without their specifiers."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    names: set[str] = set()
    for specifier in data["project"]["dependencies"]:
        # `sqlalchemy[asyncio]>=2.0.41,<2.1` -> `sqlalchemy`
        name = re.split(r"[\[<>!=, ]", specifier, maxsplit=1)[0]
        names.add(name.lower())
    return names


def _entrypoint_executable() -> str:
    """The binary the runtime image is started with, from its `CMD`."""
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("CMD"):
            parts: list[str] = re.findall(r'"([^"]+)"', stripped)
            assert parts, f"CMD sin binario entrecomillado: {stripped}"
            return parts[0]
    raise AssertionError("El Dockerfile no declara CMD: no se sabe qué se ejecuta")


def test_the_container_entrypoint_is_a_declared_dependency() -> None:
    assert _entrypoint_executable().lower() in _declared_runtime_dependencies()


def test_every_imported_third_party_module_has_a_declared_dependency() -> None:
    """A missing runtime dependency must fail here, not at boot.

    Only the packages the application actually imports are checked, and the ones
    that ship inside another distribution are excluded because they have no
    entry of their own.
    """
    declared = _declared_runtime_dependencies()
    imported = {
        "fastapi",
        "sqlalchemy",
        "pydantic",
        "pydantic_settings",
        "asyncpg",
        "alembic",
        "boto3",
        "PIL",
        "pikepdf",
        "jose",
        "argon2",
        "anyio",
        "uvicorn",
    }
    # Modules provided by another distribution rather than by themselves.
    provided_by_another = {
        "PIL": "pillow",
        "jose": "python-jose",
        "pydantic_settings": "pydantic-settings",
        "argon2": "argon2-cffi",
    }

    missing = {
        module
        for module in imported
        if provided_by_another.get(module, module) not in declared
    }
    assert missing == set()
