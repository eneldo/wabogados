# SECURITY

## Implementado (Fase 1)

- JWT con `access` y `refresh` firmados con HS256.
- Argon2 para contraseñas; nunca se almacenan ni registran en claro.
- Sesiones de refresh persistentes: hash SHA-256, `jti`, rotación y revocación.
- Logout selectivo (una sesión) o total (todas las sesiones del usuario).
- RBAC explícito por endpoint mediante `require_permission`.
- Matriz de permisos versionada en código y sembrada por migración.
- `is_superuser` como vía de recuperación administrativa, auditable.
- Rate limiting por usuario autenticado o IP, más estricto en autenticación.
- Cabeceras de seguridad, CORS configurado y trusted hosts en producción.
- Auditoría de operaciones de escritura con saneado de secretos.
- Errores uniformes que no exponen trazas ni detalles internos.

## Pendiente

- Rate limiter compartido (Redis) antes de múltiples workers.
- Validación MIME y magic bytes en evidencias.
- URLs firmadas y expiradas para archivos.
- ClamAV opcional para producción.
- Protección IDOR por recurso en clientes y expedientes.
- Endurecimiento de contraseñas y bloqueos por intento fallido.

## Reglas

- No hardcodear secretos: usar `.env` y variables de entorno.
- No crear endpoints sin permiso declarado.
- No confiar en restricciones de frontend.
- No eliminar físicamente información jurídica relevante.
