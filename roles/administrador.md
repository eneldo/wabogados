# ROL — ADMINISTRADOR

Acceso general con permisos explícitos.

## Permisos iniciales (Fase 1)

- `users:read`
- `users:create`
- `users:update`
- `users:delete`
- `users:assign_roles`
- `roles:read`
- `roles:manage`
- `permissions:read`
- `audit_logs:read`

## Notas

- Fuente de verdad: `backend/app/security/permissions.py`.
- Los permisos de recursos (clientes, expedientes, documentos, evidencias) se añaden en su fase.
- Un usuario con `is_superuser` omite la matriz; solo debe usarse para recuperación administrativa.
