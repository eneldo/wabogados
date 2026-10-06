# ROL — ABOGADO

Acceso a expedientes asignados o autorizados.

## Permisos (Fase 2)

- `clients:read`
- `clients:create`
- `clients:update`
- `lawyers:read`
- `legal_areas:read`

No tiene permisos de eliminación: la baja de clientes y abogados es exclusiva del
administrador.

## Permisos (Fase 3)

- `cases:read_assigned` — solo expedientes donde es responsable o colaborador.
- `cases:create`
- `cases:update`
- `cases:assign`

No tiene `cases:read_all` ni `cases:close`: el cierre es un acto jurídico
reservado al administrador.

## Permisos (Fase 5)

- `calendar:read`, `calendar:create`, `calendar:update`
- `hearings:read`, `hearings:create`, `hearings:update`

No tiene `hearings:reschedule`: la fecha de una audiencia la fija el juzgado.

## Pendiente por fase

- Fase 6: `documents:read`, `documents:create`, `documents:update`.
- Fase 7: evidencias y originals.

## Restricciones de diseño

- Nunca confiar solo en el frontend: cada endpoint declara su permiso.
- El acceso a expedientes debe comprobar la asignación, no solo el permiso.
