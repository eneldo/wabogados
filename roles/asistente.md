# ROL — ASISTENTE

Acceso operativo limitado según permisos.

## Permisos (Fase 2)

- `clients:read`
- `clients:create`
- `clients:update`
- `lawyers:read`
- `legal_areas:read`

No tiene permisos de eliminación: la baja de clientes y abogados es exclusiva del
administrador.

## Permisos (Fase 3)

- `cases:read_all` — consulta todo el libro de expedientes.
- `cases:create`
- `cases:update`
- `cases:assign`

No tiene `cases:close`: el cierre queda reservado al administrador.

## Permisos (Fase 5)

- `calendar:read`, `calendar:create`, `calendar:update`
- `hearings:read`, `hearings:create`, `hearings:update`

No tiene `hearings:reschedule` ni `cases:close`.

## Pendiente por fase

- Fase 6: permisos de documentos.

## Restricciones de diseño

- Acceso limitado por permiso explícito en cada endpoint.
- Sin acceso a evidencias originales ni a administración de usuarios.
