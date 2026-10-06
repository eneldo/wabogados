# ADR-0004 — Dependency Management (Python)

**Fecha:** 2026-09-30
**Estado:** Accepted

## Contexto
El proyecto necesita una forma consistente de gestionar dependencias Python, herramientas de calidad y configuración de build.

## Decisión
Usar `pyproject.toml` con:
- Build backend: `hatchling`
- Dependencias runtime: `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `pydantic-settings`, `alembic`, `uvicorn[standard]`
- Dependencias dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`, `ruff`, `mypy`
- Configuración de herramientas en el mismo archivo: `[tool.pytest.ini_options]`, `[tool.coverage.run]`, `[tool.ruff]`, `[tool.mypy]`

## Alternativas descartadas
- `requirements.txt` + `requirements-dev.txt`: no permite configurar herramientas ni build metadata.
- `poetry` / `pdm`: añade dependencia de herramienta externa; `hatchling` es estándar PEP 517/621 y más ligero.

## Impacto
- Un solo archivo para dependencias y configuración de calidad.
- Reproducible en CI y local.
- Compatible con `pip install -e .` y `pip install .[dev]`.