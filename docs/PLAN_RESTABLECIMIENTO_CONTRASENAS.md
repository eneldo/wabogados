# Plan — Restablecer contraseñas desde Usuarios

Fecha: 2026-11-15. Implementación autorizada y realizada; ver operación y
verificaciones en `docs/RESTABLECIMIENTO_CONTRASENAS.md`.
Superficie: `http://localhost:3000/admin/usuarios`. El diagnóstico de abajo
describe el estado **anterior** a la implementación.

## Verificación realizada

- Revisión autenticada en navegador de la instalación local (HTTP 200).
  «Nuevo usuario» sí muestra un campo obligatorio de contraseña inicial,
  de 8–128 caracteres. No se enviaron altas ni ediciones.
- No hay botón de restablecimiento en el listado y «Editar» no incluye contraseña.
- OpenAPI del backend desplegado confirma `password` en `UserCreateAdmin`,
  pero no en `UserUpdateAdmin`. No existe endpoint de restablecimiento,
  cambio propio ni recuperación por correo.
- Las ramas que procesan `password` en servicios de actualización no son una
  solución disponible: el esquema de entrada actual no expone ese campo.
- `TokenService.revoke_all_for_user` revoca refrescos; `get_current_user`
  verifica JWT/usuario activo, no una versión de credenciales. Por ello los JWT
  de acceso anteriores pueden seguir siendo aceptados hasta su caducidad.
- No se encontró integración de correo de recuperación en el backend revisado.
- La sesión de revisión se cerró. No se guardaron credenciales, cookies ni tokens.

## Alcance recomendado

Restablecimiento **administrativo**, separado de la edición de perfil y del alta.
No mostrar ni recuperar contraseñas anteriores. No enviar contraseñas por correo.
El administrador asigna una nueva contraseña y la comunica al titular por un
canal seguro, previa comprobación de su identidad fuera de la aplicación.

### 1. Acción y formulario

- Mantener «Nuevo usuario» con su contraseña inicial; aclarar su función.
- Agregar «Restablecer contraseña» a las acciones de cada cuenta autorizada.
- Diálogo con cuenta destinataria claramente identificada, nueva contraseña,
  confirmación y control opcional Mostrar/Ocultar. Sin campos prellenados.
- Advertir: la contraseña anterior dejará de funcionar y se invalidarán las
  sesiones anteriores de esa cuenta. No reactivar cuentas implícitamente.
- Aplicar política central consistente con alta (actualmente 8–128 caracteres);
  no recortar espacios ni transformar contraseñas al leer `FormData`.
- Errores accesibles por campo, foco y Escape correctos, IDs únicos y estado de
  envío protegido contra duplicación. Limpiar campos tras éxito y al cerrar;
  no retornar secretos dentro del estado de una Server Action.

### 2. API y autorización

- Endpoint propuesto: `POST /api/v1/admin/users/{user_id}/reset-password`.
  Contrato dedicado, no añadir la contraseña al PATCH general de perfil.
- Permiso nuevo propuesto `users:reset_password`, sembrado por migración para
  administrador, respetando el bypass de superusuario vigente. No asumir que el
  nombre existe hoy ni esconder botones con permisos no sembrados.
- Validar permiso en backend en cada llamada. No basta ocultar el botón.
- Como regla inicial: solo superusuarios pueden restablecer a un superusuario;
  bloquear auto-restablecimiento por esta acción y separar el cambio propio.
  Revisar el control existente de `is_superuser` para evitar saltarse esa regla.
- Rechazar cuentas inexistentes/inactivas sin modificar roles, correo ni estado.
- Validar fortaleza/límites y confirmación; reutilizar Argon2 del proyecto.
- Reutilizar rate limiting; aplicar presupuesto específico si lo requiere la
  operación sensible. Mostrar éxito únicamente tras commit correcto.

### 3. Invalidación de sesiones y auditoría

- Cambiar hash y revocar todos los refrescos del destinatario en la misma
  transacción; no afectar sesiones ni claves de otras personas.
- Para invalidar también JWT de acceso, se recomienda `token_version` persistido
  por usuario, incluido en emisión/rotación y comprobado al autenticar.
  Incrementarlo al restablecer. Diseñar compatibilidad inicial con versión 0
  para no expulsar sin motivo a todo el sistema durante la migración.
- Cubrir concurrencia entre login, refresh y reset para que una operación antigua
  no emita credenciales válidas con la nueva versión. Asegurar bloqueo/orden
  transaccional consistente, no solo agregar una columna.
- Registrar actor, destinatario, fecha, resultado y sesiones revocadas. No
  guardar contraseña, confirmación, hash ni tokens en auditoría/logs/respuestas.
- Revisar el saneamiento de errores 422: el manejador actual conserva `input`
  de Pydantic. Los nuevos errores no deben reflejar valores secretos.

### 4. Integración y despliegue seguro

- Frontend mediante Server Action y cliente interno, sin ampliar el proxy público
  ni exponer tokens al navegador. Revalidar `/admin/usuarios` tras éxito.
- Archivos base: `components/admin/seguridad/user-form.tsx`, nuevo diálogo de
  reset, `features/seguridad/actions.ts`, `app/(admin)/admin/usuarios/page.tsx`;
  backend `api/v1/admin.py`, `schemas/identity.py`, `services/identity.py`,
  `services/auth.py`, `api/deps.py`, permisos y migración Alembic.
- El árbol conserva Usuarios/Roles sin commit y cambios previos de
  Dockerfile/multimedia/IA sin validar. Revisar diferencias, respaldar la base y
  preparar imagen backend selectiva reproducible. No reconstruir el backend
  completo a ciegas ni depender de otro parche efímero de contenedor.
- Actualizar memoria y CHANGELOG por fase, registrar pruebas antes de avanzar.

### 5. Verificación y aceptación

En instalación aislada, con cuentas sintéticas (no cambiar claves reales):

1. Alta con contraseña inicial sigue funcionando.
2. Administrador autorizado restablece una cuenta permitida y persiste el cambio.
3. Clave nueva permite login; antigua devuelve 401.
4. Refrescos y JWT de acceso anteriores dejan de servir para la cuenta afectada.
5. Otra sesión/otra cuenta permanece operativa; roles y datos no cambian.
6. Sin sesión: 401; sin permiso: 403; superusuario protegido y auto-reset
   bloqueados según política; cuenta inexistente/inactiva y datos inválidos
   correctamente rechazados.
7. Error o rollback no produce éxito falso ni cambio parcial; probar carrera
   login/refresh/reset y ausencia de secretos en 422/auditoría/respuesta.
8. E2E: abrir/cancelar/confirmar, validaciones, doble envío, teclado, foco y móvil.
9. Ruff/mypy/pytest, migración reversible en base de prueba, typecheck/lint/build
   frontend y comprobación de la imagen desplegada.

## Segunda fase opcional (no incluida en el reset básico)

- Cambio de contraseña propia exigiendo la actual y una nueva confirmada.
- Contraseña temporal con cambio obligatorio al siguiente acceso: requiere
  estado persistido, pantalla y bloqueo backend de operaciones privadas hasta
  completar el cambio. No etiquetar una clave como «temporal» sin imponerlo.
- «Olvidé mi contraseña» por correo: proveedor configurado, enlaces de un solo
  uso con caducidad, rate limiting y respuesta que no revele cuentas existentes.
