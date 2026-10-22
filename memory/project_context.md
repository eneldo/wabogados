# Contexto del Proyecto

## Objetivo
Plataforma ERP jurídico WABOGADOS V1: gestión integral de clientes, expedientes, abogados, actuaciones, agenda, documentos, evidencias, mensajería, seguridad y auditoría.

## Estado actual
Fases 0A a 10 del backend completadas. La superficie administrativa tiene
Dashboard, Clientes, Abogados, Expedientes, Agenda, Mensajes, Solicitudes,
Documentos, Seguridad, Configuración, **Centro multimedia**, **Facturación** e
**IA Jurídica** (esta última con búsqueda literal y resumen extractivo; la
generación asistida sigue pendiente de proveedor).
- Backend FastAPI funcional con identidad, expedientes, actuaciones, agenda,
  documentos, evidencias, mensajería, auditoría, biblioteca multimedia y
  operaciones.
- Frontend Next.js con web pública, portal del cliente, gestor de evidencias y
  administración modular.
- Docker Compose levanta PostgreSQL, backend, worker de evidencias, MinIO,
  destino de respaldo y frontend con healthchecks.
- Tests Docker aislados por savepoint sobre PostgreSQL efímero: **810 pruebas,
  86,95 %** de cobertura según la última sesión registrada (2026-10-06), sin avisos
- Frontend: ESLint, TypeScript y build limpios. **Ruff y mypy estricto limpios**
  y reproducibles: los ceilings de `ruff`, `mypy` y `sqlalchemy` están fijados en
  `pyproject.toml` a lo verificado, y el extra `dev` incluye los stubs de tipos
  que faltaban. Hash de contraseñas con `argon2-cffi`.
- Sesión: cerrar sesión revoca la sesión de refresco en el servidor (ADR-060).
- Respaldos: los objetos se verifican por digest contra `MANIFEST.sha256` antes
  de la copia externa (ADR-062).

## Arquitectura
Next.js 16 (React 19, TS strict, Tailwind 4) → FastAPI 0.116 (Python 3.12, SQLAlchemy 2 async, Pydantic v2) → PostgreSQL 17 (asyncpg) + MinIO/S3 (pendiente).
Nginx en producción (pendiente).
Evidencias: originales inmutables, derivados optimizados, SHA-256, cadena de custodia.

## Backend
- Estructura: app/{api,core,db,models,schemas,services,repositories,security,middleware,workers,evidence_engine,tests}
- API v1 prefix: /api/v1
- Config: pydantic-settings desde .env
- DB: async engine + session factory, pool_pre_ping
- Migraciones: Alembic async
- Errores: formato uniforme {error: {code, message, details}}
- Tests: pytest + httpx + pytest-asyncio, coverage >=80%
- Lint: Ruff, mypy strict

## Frontend
- Next.js 16 App Router, TypeScript strict, Tailwind 4, ESLint 9
- Server Components por defecto
- Página de estado en / consumiendo /api/v1/health/ready
- Accesible: aria-live, role=status, contraste

## Base de datos
PostgreSQL 17 via Docker Compose.
Esquema de identidad aplicado hasta `d4e5f6a7b8c9`.
Convención: UUID PK, timestamps, soft delete (is_active, deleted_at).

## Infraestructura
Docker Compose local con servicios: postgres, minio, minio-backup, backend,
evidence-worker y frontend, con healthchecks donde aplica.
Security: no-new-privileges, cap_drop ALL, non-root.

## Servicios externos
MinIO/S3 (pendiente Fase 0B/7)
Redis: contador compartido de rate limiting (cerrado 2026-10-05); cola de trabajos propia de evidencias (pendiente Fase 7)
ClamAV (pendiente Fase 7)

## Seguridad
- Config sin secretos hardcodeados (.env.example)
- Errores no exponen stack traces
- JWT access/refresh, Argon2 y sesiones persistentes con rotación
- RBAC explícito por endpoint mediante `require_permission`
- Auditoría de operaciones de escritura con saneado de secretos
- Rate limiting por usuario o IP, más estricto en autenticación

## Riesgos conocidos
- Rate limiting: **cerrado el 2026-10-05** con almacén compartido sobre Redis
  (ventana deslizante con script Lua en `app/services/rate_limit_store.py`);
  si Redis cae, cuenta en memoria y registra el error. Detalle en KNOWN_ISSUES.md
- MinIO no integrado en el flujo de producción (el mecanismo S3 sí está listo)
- Sin antivirus para evidencias
- Respaldo externo en el mismo host: en producción debe ser otra máquina
- Sin ensayo de restauración con la aplicación caída
- Si el token de acceso ya expiró, cerrar sesión no puede revocar el refresco
  (ADR-060); el token sigue vivo hasta caducar
- CI/CD: `.github/workflows/quality-gates.yml` (gitleaks, ruff, mypy,
  migraciones reversibles, pytest con umbral 80 % de cobertura, builds de imagen
  y gates de frontend), sobre el remoto `github.com/eneldo/wabogados`.
  **Primera corrida real en verde (corrida #2, `e42352a`, 2026-10-22)**: la
  corrida #1 falló en gitleaks por dos literales de prueba y se exentó el
  directorio de tests en `.gitleaks.toml` (useDefault intacto).

## Funcionalidades terminadas
Ver IMPLEMENTED_FEATURES.md

## Decisiones registradas
Ver DECISIONS.md (ADR-058 a ADR-063 son de la sesión 2026-10-04)

## Funcionalidades pendientes
Ver NEXT_STEPS.md
