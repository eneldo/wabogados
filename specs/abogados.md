# SPEC — ABOGADOS

Desarrollar conforme a MASTER_PROMPT.md.

## Estado: implementado en Fase 2

Datos mínimos cubiertos: documento, nombre, tarjeta profesional, especialidades,
áreas jurídicas, contacto, estado y fotografía (`photo_url`).

- `document_type` + `document_number` únicos.
- `professional_card` único y opcional.
- `specialties` como lista de texto; `legal_areas` como relación al catálogo.
- `status`: `activo`, `inactivo` o `suspendido`.
- Baja lógica con `is_active`, `deleted_at` y `deleted_by`.
- Historial de cambios por campo en `change_logs`.
- Permisos: `lawyers:read`, `lawyers:create`, `lawyers:update`, `lawyers:delete`.
  Solo el administrador puede dar de baja.

## Endpoints

- `GET /api/v1/lawyers` — paginado, con `search`, `status` e `include_inactive`.
- `POST /api/v1/lawyers`
- `GET /api/v1/lawyers/legal-areas`
- `GET /api/v1/lawyers/{id}`
- `PATCH /api/v1/lawyers/{id}`
- `DELETE /api/v1/lawyers/{id}` — baja lógica y estado `inactivo`.
- `GET /api/v1/lawyers/{id}/history`

## Pendiente

- Asignación de expedientes y cálculo de carga de trabajo (Fase 3).
- Historial de actuaciones y agenda (Fases 4 y 5).
- Subida de fotografía a almacenamiento de objetos (Fase 7).
