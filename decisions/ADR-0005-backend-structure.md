# ADR-0005 — Backend Structure & Configuration

**Fecha:** 2026-09-30
**Estado:** Accepted

## Contexto
Se requiere una estructura de backend escalable, tipada y mantenible desde el inicio.

## Decisión
Estructura modular bajo `backend/app/`:
- `api/v1/` — routers y endpoints versionados
- `core/` — configuración, constantes, utilidades transversales
- `db/` — engine, session factory, base models
- `models/` — SQLAlchemy ORM models
- `schemas/` — Pydantic schemas (request/response)
- `services/` — lógica de negocio
- `repositories/` — acceso a datos
- `security/` — auth, RBAC, crypto
- `middleware/` — request/response middleware
- `workers/` — background jobs
- `evidence_engine/` — procesamiento de evidencias
- `tests/` — tests de integración y unitarios

Configuración vía `pydantic-settings.BaseSettings` con `.env` y `SettingsConfigDict(extra="ignore")`.

IDs: UUID v7 (pendiente) / UUID v4. Timestamps: `created_at`, `updated_at`. Soft delete: `is_active`, `deleted_at`, `deleted_by`.

## Alternativas descartadas
- Estructura plana: no escala.
- Configuración hardcodeada o YAML: menos type-safe que Pydantic Settings.

## Impacto
- Separación clara de responsabilidades.
- Fácil testing (dependency injection via FastAPI Depends).
- Preparado para multi-tenancy futuro.