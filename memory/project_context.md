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
- Compose define PostgreSQL, Redis, backend, worker de evidencias, ClamAV y
  frontend. MinIO y el destino provisional están comentados; el almacenamiento
  local es el activo y el destino S3 externo sigue pendiente de la firma.
- Tests Docker aislados por savepoint: **881 pruebas y 85,77 % de cobertura** en
  la release de analítica (2026-11-11), Git `0d91b47` más cambios de esta función.
  El árbol conserva cambios anteriores de multimedia/IA sin validar y excluidos
  de la imagen desplegada; no extrapolar este resultado a esos pendientes.
- Frontend: TypeScript/build correctos; ESLint sin errores, con un warning previo
  en `portal/casos/[caseId]/page.tsx:288`. **Ruff y mypy estrictos limpios en la release aislada**
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
- Web corporativa pública en `/`; estado en `/estado` consumiendo `/api/v1/health/ready`
- Identidad pública revisada el 2026-10-22: logo real servido desde
  `frontend/public/marca/`, tema azul noche/gris/rojo de `wabogado-2.jpg` limitado
  a `.public-site`, ancho fluido. Guía: `docs/IDENTIDAD_WEB_PUBLICA.md`;
   19 regresiones públicas ejecutables sin credenciales (`--project=public`).
- Portada renovada el 2026-11-11 con composición editorial, hero de dos columnas,
  servicios numerados y estilos exclusivos `.public-home`. Frontend reconstruido
  y activo en `http://localhost:3000`. Cada tarjeta enlaza a `/servicios/[slug]`,
  con catálogo compartido y formulario preseleccionado; iconos SVG semánticos por
  nombre del servicio y **19 regresiones públicas verificadas**. El adaptador de consultas preserva el nombre del área en el
  mensaje al normalizarlo al contrato antiguo del backend desplegado.
- Analítica pública first-party activa con panel privado `/admin/estadisticas-web`
  y permiso administrador `website_analytics:read`. Vistas, navegaciones estimadas,
  áreas, clics y consultas registradas, filtros y series diarias/mensuales. Sin
  cookies, IP ni fingerprint; UUID solo en memoria, dedup 48 h y agregados 400 días.
  **25 regresiones públicas/analítica verificadas en instalación aislada**.
  Operación y límites de estimación: `docs/ESTADISTICAS_WEB.md` (ADR-064).
- Administración en `/admin` (16 módulos disponibles, visibles según permisos), cliente en `/portal` y acceso compartido
  en `/login`. Destino administrativo y reentrada con sesión **corregidos y
  verificados el 2026-10-22**. Se usa el cliente interno y guarda comunes, sin
  consultar localhost desde Docker ni aceptar identidades vacías al fallar la API.
  Ver `docs/VERIFICACION_PORTAL_ADMIN_2026-10-22.md`: 4 pruebas privadas, 13
  módulos en lectura, 52 inspecciones de layout y cierre con revocación verificados.
  Las limitaciones funcionales del informe `REVISION_WEB_Y_PORTALES_2026-10-22.md`
  (actuaciones, etc.) siguen siendo trabajos separados de la navegación.
- Accesible: aria-live, role=status, contraste

## Base de datos
PostgreSQL 17 via Docker Compose.
Esquema local aplicado hasta `fd4e5f607182` (analítica web, 2026-11-11).
Convención: UUID PK, timestamps, soft delete (is_active, deleted_at).

## Infraestructura
Docker Compose local con servicios: postgres, redis, backend, evidence-worker,
clamav y frontend. MinIO/minio-backup permanecen fuera del stack activo.
Security: no-new-privileges, cap_drop ALL, non-root.

## Servicios externos
MinIO/S3 (pendiente Fase 0B/7)
Redis: contador compartido de rate limiting. Cola de evidencias y worker existentes.
ClamAV integrado en evidencias/documentos; biblioteca multimedia pendiente.

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
- La biblioteca multimedia todavía tiene pendientes de procesamiento/escaneo;
  no confundirlo con el motor antivirus ya integrado en evidencias/documentos.
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
Ver `memory/IMPLEMENTED_FEATURES.md` y estado vigente en `memory/CURRENT_STATE.md`.

## Decisiones registradas
Ver `memory/DECISIONS.md` (ADR-064: analítica first-party, 2026-11-11).

## Funcionalidades pendientes
Ver `memory/NEXT_STEPS.md`.
