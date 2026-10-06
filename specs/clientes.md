# SPEC — CLIENTES

Desarrollar conforme a MASTER_PROMPT.md.

## Estado: implementado en Fase 2

- Persona natural y persona jurídica en la misma entidad `clients`.
- `client_type` distingue natural de jurídica; el esquema exige `full_name` para
  naturales y `legal_name` o `commercial_name` para jurídicas.
- Documento único por `(document_type, document_number)`.
- Baja lógica con `is_active`, `deleted_at` y `deleted_by`; nunca se elimina físicamente.
- Historial de cambios por campo en `change_logs` con el usuario responsable.
- Permisos: `clients:read`, `clients:create`, `clients:update`, `clients:delete`.
  Solo el administrador puede dar de baja.

## Endpoints

- `GET /api/v1/clients` — paginado, con `search`, `client_type` e `include_inactive`.
- `POST /api/v1/clients`
- `GET /api/v1/clients/{id}`
- `PATCH /api/v1/clients/{id}`
- `DELETE /api/v1/clients/{id}` — baja lógica.
- `GET /api/v1/clients/{id}/history`

## Pendiente

- Enlazar el cliente con un usuario de la plataforma para el portal del cliente.
- Permisos de solo lectura publicados para el rol `cliente`.
