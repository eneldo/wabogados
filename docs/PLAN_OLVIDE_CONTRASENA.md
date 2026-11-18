# Plan — «Olvidé mi contraseña»

Fecha: 2026-11-15. **Implementación autorizada y realizada; validación y guía en
`docs/RECUPERACION_CONTRASENA.md`.** Activación real pendiente de proveedor,
remitente y origen HTTPS. Las fases siguientes conservan el plan aprobado;
no autorizan contratación ni pruebas con cuentas reales.

## Objetivo y base verificada

Permitir que una persona recupere su acceso demostrando control sobre el correo
registrado, sin conocer la contraseña anterior ni pedirle al administrador una nueva.

El proyecto ya dispone de Argon2, validación de contraseñas, `token_version`,
revocación de refrescos y bloqueos transaccionales. El reset administrativo está
publicado en `de6d18a` y continúa funcionando como alternativa asistida.
No se encontró servicio de envío de correo ni endpoints de recuperación en el
código revisado. No se inspeccionaron secretos de `.env` ni se enviaron correos.

## Flujo que verá el usuario

1. En `/login`, seleccionar **«Olvidé mi contraseña»**.
2. En `/olvide-contrasena`, escribir el correo registrado y enviar.
3. Mostrar siempre: **«Si existe una cuenta habilitada con ese correo,
   recibirás instrucciones para recuperar tu acceso»**.
4. Si la cuenta es elegible, recibir un correo de WABOGADOS con un enlace
   **de un solo uso y 20 minutos de vigencia** (valor propuesto configurable).
5. El enlace abre `/restablecer-contrasena`, donde se escribe y confirma la
   nueva contraseña. Abrirlo no cambia nada ni consume el enlace.
6. Al guardar correctamente, invalidar enlaces y sesiones anteriores de esa
   cuenta; informar éxito y volver a `/login`. **Sin ingreso automático**.

Si el enlace no sirve: «El enlace no es válido o ha caducado. Solicite uno nuevo».
Si no tiene acceso al correo: indicar contacto con administración para verificar
su identidad fuera de la aplicación. No permitir sustituir el correo desde este flujo.

## Fase 0 — Decisiones y requisitos previos

- Aprobar proveedor transaccional SMTP, remitente y nombre visible; preferible
  remitente bajo dominio de la firma, con SPF/DKIM y política DMARC revisados.
  El correo público de contacto no implica que pueda usarse como remitente SMTP.
- Confirmar URL pública HTTPS fija de la aplicación. No formar enlaces a partir
  de `Host`, `Origin`, `returnTo` ni otros valores enviados por el solicitante.
- Propuesta de elegibilidad: cuentas **activas y con correo verificado**, de todos
  los perfiles, incluido administrador. No requiere `users:reset_password`:
  la autorización es el token enviado al correo, no una sesión administrativa.
  Revisar correos/verificación de cuentas existentes antes de activar, sin marcar
  cuentas masivamente como verificadas. No reactivar ni cambiar roles por recuperar.
- Aprobar caducidad de 20 minutos y presupuestos iniciales: solicitud 5/15 min por
  IP y 3/h por destinatario, con espera mínima de 60 s entre envíos; confirmación
  10/15 min por IP y presupuesto global contra abuso. Ajustables tras observar uso.
- Secretos solo en entorno/gestor de secretos, nunca en Markdown ni Git. Usar
  buzón capturador aislado para desarrollo; no hacer pruebas con cuentas reales.

**Entrega:** configuración sin secretos en `.env.example` y procedimiento de
validación del remitente/dominio. No activar mientras estos requisitos falten.

## Fase 1 — Tokens y datos persistentes

- Nueva tabla `password_reset_tokens`: ID, usuario, digest SHA-256 único del token,
  fecha de emisión/caducidad/uso/revocación, versión de credenciales al emitir y
  vinculación al correo de emisión (digest con clave). Índices y migración reversible
  posterior a `fe5f60718293`.
- Token opaco generado criptográficamente con al menos 256 bits de entropía;
  no reutilizar JWT de acceso/refresco, IDs predecibles ni contraseñas temporales.
- Como máximo un enlace vigente por cuenta. Una nueva solicitud admitida
  reemplaza los anteriores y cancela sus envíos pendientes. Pedir un enlace
  **no cambia la contraseña ni cierra sesiones**.
- Rechazar si hubo reset administrativo/otro reset, cambió el correo, o la cuenta
  fue desactivada; comparar versión y correo actual en la transacción de consumo.
- Integrar revocación de enlaces/envíos en las operaciones de cambio de correo
  y desactivación, también si después se restaura el correo o se reactiva la cuenta.
  Un cambio de correo no debe conservar verificación sin validación confiable del
  nuevo destinatario; revisar este contrato antes de habilitar recuperación.
- Limpiar tokens caducados/usados y metadatos según retención documentada;
  propuesta de purga a 24 h, separada de la retención de auditoría institucional.

**Entrega:** modelo/migración, servicio de emisión/consumo y pruebas de caducidad
y unicidad. Los tokens de recuperación nunca autentican endpoints privados.

## Fase 2 — Correo fiable, sin revelar cuentas

- Servicio SMTP con TLS, timeout, plantillas HTML/texto y remitente verificado.
  El correo indica la vigencia y que, si no solicitó el cambio, puede ignorarlo.
  Nunca incluye claves anteriores/nuevas ni información de expedientes.
  Desactivar seguimiento de apertura/clics y reescritura comercial de enlaces;
  verificar que el cliente de correo preserve el fragmento al abrirlo.
- Envío fuera de la respuesta HTTP para no revelar existencia por la demora SMTP.
  Usar outbox persistente en PostgreSQL y worker dedicado, sin mezclar trabajos
  con evidencias ni depender de BackgroundTasks sin persistencia.
- El validador guarda solo el digest. El material necesario para enviar el enlace
  en la outbox va **cifrado con clave dedicada fuera de la base**; borrarlo al
  enviarse/caducar/cancelarse. Nunca guardar enlace o token en texto claro en cola,
  logs, auditoría, errores o respaldos de payload sin cifrar.
- Reintentos limitados (propuesta: hasta 3 dentro de la vigencia), sin renovar
  caducidad ni enviar enlaces cancelados. Un SMTP incierto puede duplicar el
  mismo correo; no generar nuevos tokens por reintentar el envío.
- Alertas internas saneadas por fallos/bounces. Un 202 significa **solicitud
  recibida**, no entrega al buzón. Si la infraestructura global no puede aceptar
  solicitudes, responder indisponibilidad uniforme, independientemente del correo.
- Presupuestos por IP/destinatario/global y observación de tiempos para evitar
  enumeración. Destinatarios desconocidos/inactivos/no verificados tienen el mismo
  mensaje y estado público. El límite por correo tampoco revela si está registrado.

**Entrega:** worker/outbox, configuración y prueba de recepción/caída/reintento
en buzón aislado; prueba real controlada de entrega solo después de autorización.

## Fase 3 — API y transacción segura

Endpoints propuestos, públicos y limitados:

| Endpoint | Entrada | Resultado |
| --- | --- | --- |
| `POST /api/v1/auth/forgot-password` | `email` | 202 genérico, sin token ni datos de cuenta |
| `POST /api/v1/auth/reset-password` | `token`, `new_password`, `confirm_password` | 200 únicamente tras commit correcto |

- Token inválido/caducado/usado/revocado: error genérico común. Campos inválidos:
  422 saneado; abuso por IP/global: 429; indisponibilidad global: 503 uniforme.
- Conservar política 8–128 caracteres y espacios, con confirmación y Argon2.
- Consumo: obtener candidato por digest sin bloquearlo; bloquear primero usuario
  y después token, releyendo y validando todo. Aplicar el mismo orden que login,
  refresh y reset administrativo, incluidas emisión y cancelación de enlaces.
- Una sola transacción para consumir token, actualizar hash, incrementar
  `token_version`, revocar refrescos, invalidar demás enlaces y registrar auditoría
  `password_recovery_completed`. No etiquetar como acción de un administrador.
- Dos confirmaciones concurrentes: solo una puede cambiar la clave. Probar
  además carreras con reset administrativo, cambio de correo, login y renovación.
- Extraer una operación común de cambio de credenciales, manteniendo separadas
  las autorizaciones de recuperación y reset administrativo. No llamar al reset
  administrativo fingiendo un actor ni debilitar su protección de superusuarios.

**Entrega:** contratos, integración y pruebas positivas/negativas con rollback.

## Fase 4 — Pantallas e integración de Next.js

- Enlace en login y dos pantallas con marca actual, accesibles en móvil/teclado.
  Estados de envío, mensaje genérico, confirmación, error de enlace y éxito.
  Mostrar/ocultar clave, foco en error, IDs únicos y prevención de doble envío.
- Enlace con token en **fragmento**, no query ni path. Componente cliente lo lee
  en memoria y retira del historial antes de otras operaciones. No usar cookies,
  localStorage/sessionStorage ni telemetría para guardarlo. Al recargar después
  de retirarlo, pedir reabrir el correo si el token ya no está en memoria.
- GET/escáner de correo no consume token; solo POST con nueva clave confirmada.
  Sin recursos de terceros ni analítica en recuperación, `no-store`, `noindex`,
  `Referrer-Policy: no-referrer`; no precargar el enlace del correo.
- Rutas Next dedicadas hacia endpoints fijos internos; no ampliar el proxy
  genérico ni reenviar cookies/bearers del visitante. Validar origen/CSRF y tamaño.
  Revisar limitación en la frontera pública y confianza de proxy para que el API
  no trate a todos como la IP de Next ni confíe en un `X-Forwarded-For` arbitrario.
- Tras éxito limpiar campos/token y cookies de sesión de esa navegación, ofrecer
  acceso normal; otros dispositivos deben volver a autenticarse por versión.

**Entrega:** pantallas y E2E con buzón capturador y cuentas sintéticas.

## Fase 5 — Verificación y aceptación

1. Cuenta elegible recibe enlace; desconocida/inactiva/no verificada no revela
   existencia. Sin filtrar por respuesta, logs ni diferencias evidentes de tiempo.
2. Clave nueva permite login; anterior, accesos y refrescos previos fallan.
   Otra cuenta y sus sesiones siguen intactas; roles/perfil/estado no cambian.
3. Enlace manipulado, caducado, usado, sustituido o emitido antes de un reset/
   cambio de correo deja de servir. Abrirlo sin enviar no modifica nada.
4. Concurrencia y rollback reales en PostgreSQL; no simular carreras compartiendo
   un único savepoint. Nunca confirmar éxito tras error de commit.
5. SMTP caído, reinicio de worker, reintentos, caducidad en cola, límites y limpieza
   probados. Solicitudes no bloquean login ni reset administrativo.
6. Sin contraseñas/tokens/enlaces en logs, 422, auditoría, analítica ni trazas E2E;
   prueba de origen malicioso, enlace en dominio fijo y frontera/proxy.
7. Ruff, mypy, suite backend y migración upgrade/downgrade/upgrade; frontend
   typecheck/lint/build, E2E de recuperación y regresiones login/admin/web pública.

**Entrega:** informe con resultados reales y limitaciones; no extrapolar las
895 pruebas anteriores a esta función todavía inexistente.

## Fase 6 — Activación gradual y operación

- Flag desactivado por defecto; validar primero en instalación aislada. Respaldar
  base y comprobar restaurabilidad; preparar imagen selectiva sin los pendientes
  ajenos de Dockerfile/multimedia/IA. Revisar la configuración real de correo/HTTPS.
- Aplicar migración y desplegar backend/worker/frontend; verificar salud, dominio
  del enlace, entrega a buzón controlado y procedimiento si termina en spam.
  Activar públicamente solo con autorización y configuración completas.
- Ante problemas, desactivar **emisión y consumo** de recuperación y detener/
  cancelar envíos pendientes. Mantener login y reset administrativo. No bajar
  `token_version` ni volver a código que acepte JWT revocados. No borrar datos
  jurídicos ni modificar claves reales durante la validación.
- Actualizar guía, CHANGELOG, memoria y ADR al implementar. Esta propuesta no
  incluye MFA, cambio propio con clave actual ni modificación del correo de acceso.

## Orden propuesto de aprobación

1. Aprobar este alcance, elegibilidad y límites.
2. Definir proveedor, remitente y URL pública.
3. Implementar fases 1–4 y verificar fase 5 en entorno aislado.
4. Autorizar/configurar prueba de entrega real y activación de fase 6.
