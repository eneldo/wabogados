# ADR-0008 — Docker Compose & Local Infrastructure

**Fecha:** 2026-09-30
**Estado:** Accepted

## Contexto
Entorno local reproducible que refleje producción lo máximo posible.

## Decisión
**Servicios:**
1. `postgres`: `postgres:17-alpine`
   - Healthcheck: `pg_isready`
   - Volume persistente: `postgres_data`
   - Credenciales via env vars (`.env`)

2. `backend`: build desde `./backend`
   - Puerto 8000
   - Depende de `postgres` (condition: service_healthy)
   - Healthcheck: `python -c "urllib.request.urlopen('http://localhost:8000/api/v1/health/ready', timeout=2)"`
   - `DATABASE_URL` construida desde vars de postgres
   - Security: `no-new-privileges:true`, `cap_drop: ALL`

3. `frontend`: build desde `./frontend`
   - Puerto 3000
   - Depende de `backend` (condition: service_healthy)
   - Healthcheck: `wget --spider -q http://localhost:3000/`
   - `API_INTERNAL_URL=http://backend:8000`
   - Security: `no-new-privileges:true`, `cap_drop: ALL`

**Red:** bridge por defecto (DNS por nombre de servicio).
**Volúmenes:** solo `postgres_data` persistente.

## Alternativas descartadas
- SQLite local: no refleja PostgreSQL real (tipos, concurrencia, extensiones).
- Backend+DB en mismo contenedor: viola single-process-per-container.
- Exponer puertos DB en host: innecesario, acceso solo via backend.

## Impacto
- `docker compose up` levanta stack completo funcional.
- Healthchecks encadenados evitan race conditions.
- Configuración idéntica a base de producción (salvo secrets management).
- Fácil extensión: MinIO, Redis, Nginx proxy.