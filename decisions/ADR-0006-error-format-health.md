# ADR-0006 — Uniform Error Format & Health Endpoints

**Fecha:** 2026-09-30
**Estado:** Accepted

## Contexto
Todas las respuestas de error deben tener formato consistente para facilitar consumo por frontend y clientes API. Los health checks deben distinguir liveness (proceso vivo) de readiness (listo para servir tráfico).

## Decisión
**Formato de error uniforme:**
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "object|null"
  }
}
```

Códigos iniciales:
- `not_found` (404)
- `validation_error` (422)
- `http_error` (otros 4xx/5xx)
- `service_unavailable` (503)

**Health endpoints:**
- `GET /api/v1/health/live` → 200 `{status: "ok", service, checks: {application: "up"}}` — solo proceso.
- `GET /api/v1/health/ready` → 200 `{status: "ready", service, checks: {database: "up"}}` o 503 con error `service_unavailable` si DB no responde.

## Alternativas descartadas
- Formatos diferentes por endpoint: dificulta manejo genérico en cliente.
- Un solo health endpoint: no permite distinguir reinicio necesario vs caída de dependencia.

## Impacto
- Frontend y monitoreo pueden parsear errores genéricamente.
- Kubernetes/Orquestadores pueden usar liveness/readiness probes correctamente.
- Auditoría y logging consistentes.