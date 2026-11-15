# Restablecimiento administrativo de contraseñas

## Uso

En **Usuarios** (`/admin/usuarios`), seleccione **Restablecer contraseña** en
una cuenta activa, escriba la nueva clave y confírmela. Se admiten 8–128
caracteres y se conservan los espacios. Verifique antes la identidad del titular
y comunique la nueva clave por un canal seguro. No es una contraseña temporal
ni se envía por correo; no hay cambio obligatorio al siguiente ingreso.

La clave anterior deja de servir y los accesos/refrescos previos de esa cuenta
se invalidan al guardar. No cambia roles, datos de perfil ni estado. Las otras
cuentas mantienen sus sesiones. Una petición ya autorizada antes del commit
puede terminar; la invalidación se comprueba en las siguientes peticiones.

## Autorización y API

- `POST /api/v1/admin/users/{user_id}/reset-password`.
- JSON: `new_password`, `confirm_password` (sin normalización ni recorte).
- Permiso dedicado `users:reset_password`, concedido por migración a
  `administrador`; el superusuario conserva su bypass habitual.
- No permite auto-restablecimiento, cuentas inactivas ni inexistentes. Solo un
  superusuario puede restablecer a otro superusuario. El PATCH/alta también
  impide que un no-superusuario cambie esa condición para saltarse la protección.
- Respuesta 200: mensaje y `revoked_sessions`; 400 para auto-reset/inactivos,
  401 sin sesión, 403 sin permiso/objetivo protegido, 404 inexistente, 422 inválido,
  429 presupuesto agotado. Tiene contador separado con los límites de autenticación.
- Server Action y API interna; no se amplía el proxy público ni se exponen tokens
  al navegador. Los campos se limpian al cerrar, al responder y tras éxito.

## Seguridad y compatibilidad

Migración `fe5f60718293` añade `users.token_version` con valor inicial 0 y
siembra el permiso. Los tokens antiguos sin versión se interpretan como 0:
desplegar no cierra las sesiones existentes. Un reset aumenta la versión y revoca
todos los refrescos del destinatario en la misma transacción que el hash Argon2
y la auditoría `admin_password_reset` (actor, destinatario, fecha, resultado,
número de refrescos revocados; nunca contraseña/hash/tokens).

Login, emisión, renovación y reset toman bloqueo de usuario antes de los
registros de refresco. Se relee el usuario tras esperar un bloqueo para no emitir
credenciales de una autenticación obsoleta con la versión nueva. Los errores 422
solo exponen tipo, ubicación y mensaje, nunca `input` ni contexto del validador.

## Verificación reproducible

- Suite backend: `pytest app/tests/ -q`; Ruff y mypy según `pyproject.toml`.
- `test_password_reset.py`: clave nueva/antigua, aislamiento, permisos, protección
  superusuario, validaciones sin secretos, rollback, límite y cuatro carreras con
  **conexiones PostgreSQL independientes** y espera de bloqueo comprobada.
- Migración: upgrade/downgrade/upgrade **solo en base efímera**.
- Frontend: `npm run typecheck`, `npm run lint`, build; Playwright
  `--project=password-reset` requiere `PASSWORD_RESET_TEST_AUTH` (JSON efímero de
  cuentas sintéticas) y `PASSWORD_RESET_TEST_API`, nunca cuentas reales.
- E2E cubre cancelación/Escape/foco, limpieza, mostrar/ocultar, confirmación,
  doble envío, Escape durante envío, éxito real/login/revocación, superusuario
  sin roles, IDs y límites de contenido del diálogo a 320/390/768/1440 px.
- La web pública se comprueba con `--project=public` (19 pruebas).

## Despliegue y recuperación

Respaldar PostgreSQL y verificar el archivo con `pg_restore --list`. Construir
con `execution/prepare_scoped_backend.py` desde HEAD más la lista explícita del
manifest: no incluir los pendientes de Dockerfile/multimedia/IA. La entrega
incluye los tres archivos previos de Usuarios/Roles ya activos, evitando perderlos
al reemplazar el parche efímero por una imagen reproducible.

Aplicar migración con la imagen nueva y recrear solo backend/frontend. Conservar
imagen anterior y dump protegido. **Después de un reset no volver ciegamente al
código anterior ni bajar `token_version`: perdería la revocación de JWT antiguos.**
Preferir corrección hacia adelante; una restauración excepcional necesita
planificar rotación de la clave de firma e invalidación general, con autorización.

Pendientes fuera de alcance: cambio propio y «Olvidé mi contraseña» por correo.

## Resultado local — 2026-11-15

Activo en `http://localhost:3000/admin/usuarios`, backend/frontend saludables.
**895 tests backend, 85,56 % cobertura**, Ruff/mypy limpios, migración reversible;
build/typecheck frontend correctos, lint sin errores (warning previo del portal).
**2 E2E de restablecimiento y 19 públicos aprobados**, con los públicos repetidos
en la instalación desplegada. Cuentas sintéticas solo en revisión aislada;
ninguna contraseña real modificada. Snapshot/manifest, respaldo e imagen anterior
referenciados en `memory/session_summary.md`. Commit/push autorizados después
por el usuario; consultar Git para la referencia de publicación.
