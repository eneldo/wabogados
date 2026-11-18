# Recuperación de acceso por correo

## Estado y uso

Implementación autorizada el 2026-11-15 a partir de
`PLAN_OLVIDE_CONTRASENA.md`. El envío real permanece **apagado por defecto** hasta
que la firma configure proveedor SMTP, remitente autorizado y origen público HTTPS.
Sin esos requisitos, la pantalla informa que debe contactar al administrador;
no simula envíos ni genera contraseñas temporales.

En `/login` aparece **Olvidé mi contraseña**. `/olvide-contrasena` acepta el
correo y responde de forma genérica. Una cuenta activa con correo verificado
recibe un enlace para `/restablecer-contrasena`, válido **20 minutos desde la
solicitud**, de un solo uso. Pedir/abrir el enlace no cambia la contraseña ni
cierra sesiones. Al guardar una clave nueva confirmada (8–128 caracteres, sin
recortar espacios), se invalidan los enlaces y sesiones anteriores y se ofrece
volver al login, sin acceso automático.

Todos los perfiles pueden recuperar por su correo verificado, incluidos
administrador y superusuario; no es el reset administrativo y no necesita su
permiso. Si pierde también el acceso al correo, se requiere verificación de
identidad fuera de la aplicación y asistencia administrativa.

**Cambio de correo:** la edición retira la verificación, aunque el mismo PATCH
envíe `is_verified=true`. Administración debe comprobar el nuevo destinatario
antes de volver a marcarlo como verificado mediante una operación separada.
No se verificaron ni modificaron masivamente las cuentas existentes al desplegar.

## Contratos y datos

- `GET /api/v1/auth/password-recovery`: solo informa disponibilidad global.
- `POST /api/v1/auth/forgot-password`, JSON `email`: 202 genérico. No confirma
  registro ni entrega. Suprime solicitudes repetidas sin revelar destinatarios.
- `POST /api/v1/auth/reset-password`, JSON `token`, `new_password`,
  `confirm_password`: 200 solo tras commit; 400 para enlace inválido/caducado/
  usado/revocado, 422 para campos inválidos sin reflejar entradas, 429 por abuso,
  503 si la recuperación/infraestructura no está disponible.
- Los POST de recuperación exigen `Content-Length` y cuerpo de hasta 4 KiB
  (411/413 si no se cumplen). Los límites de IP/global se aplican antes de validar
  JSON para que las solicitudes inválidas también consuman presupuesto.
- Next usa exclusivamente `/api/recuperacion/solicitar` y
  `/api/recuperacion/restablecer`; valida origen y JSON de hasta 4 KiB, no reenvía
  cookies ni bearer y nunca devuelve tokens. No amplía el proxy genérico.
- Migración `ff60718293a4`: `password_reset_tokens`,
  `password_recovery_outbox` y `users.recovery_invalidated_at`. El validador guarda
  SHA-256 del token opaco de 256 bits, versión, digest con clave del correo y
  fechas. Índice parcial impone un solo enlace no consumido/revocado por cuenta.
- El enlace lleva el token en fragmento `#token=…`, nunca query/path. El cliente
  lo lee en memoria y limpia el historial; no hay almacenamiento persistente,
  analítica, envío de referer ni indexación en estas pantallas. Al recargar sin
  token se debe reabrir el correo o solicitar otro. GET no consume enlaces.

## Cola, entrega y concurrencia

La respuesta HTTP no consulta usuarios ni espera SMTP: todas las solicitudes
admitidas, incluso desconocidas, entran en una outbox cifrada con Fernet.
`app.cli.recovery_worker` resuelve elegibilidad fuera del tiempo de respuesta,
genera el enlace y realiza entrega SMTP con TLS y timeout. El payload cifrado
se elimina al enviar, cancelar, caducar o agotar intentos. Metadatos y digests se
purgan 24 h después de caducar; la auditoría institucional se conserva aparte.

Worker independiente del de evidencias; leases persistentes de 120 s y
`SKIP LOCKED`. Hasta 3 intentos, con espera de 30 s × número de intento, sin
extender la vigencia ni generar un token distinto al reintentar. Un resultado
SMTP incierto puede duplicar **el mismo** correo/Message-ID; no se promete entrega
exactamente una vez ni llegada a bandeja principal. No se integra webhook de
bounces: los rechazos síncronos se registran con código saneado, y los diferidos
deben observarse en el proveedor. Sin tracking de clics/aperturas en la plantilla;
desactivar también estas funciones en el proveedor contratado.

El worker y los cambios de identidad bloquean primero usuario y luego los
registros asociados. Durante el SMTP acotado se conserva el bloqueo de identidad
para serializar cancelación/envío: un proveedor lento puede retrasar las
operaciones de esa misma cuenta hasta sus timeouts de E/S (no es un SLA de tiempo
total de entrega). No bloquea cuentas distintas. Tras un
crash se puede reintentar el mismo enlace, nunca saltar las comprobaciones.

La confirmación consume el token y aplica Argon2, incremento de `token_version`,
revocación de refrescos/enlaces y auditoría `password_recovery_completed` en una
transacción. El correo cambiado, desactivación, retiro de verificación o reset
administrativo invalidan enlaces y solicitudes previas, aunque después se
restaure el correo/reactive la cuenta. Dos confirmaciones concurrentes no pueden
ganar. Una petición privada autorizada antes del commit puede terminar.

## Configuración y activación

Variables documentadas sin secretos en `.env.example`:

| Variable | Uso |
| --- | --- |
| `PASSWORD_RECOVERY_ENABLED` | `false` por defecto; controla emisión y consumo |
| `PASSWORD_RECOVERY_PUBLIC_URL` | Origen HTTPS fijo, sin path/query/fragmento |
| `PASSWORD_RECOVERY_ENCRYPTION_KEY` | Clave Fernet nueva, dedicada; nunca en frontend |
| `PASSWORD_RECOVERY_PROXY_KEY` | Secreto aleatorio de al menos 32 caracteres compartido solo con Next |
| `PASSWORD_RECOVERY_SMTP_HOST/PORT/SECURITY` | Host, puerto y `starttls` o `tls` |
| `PASSWORD_RECOVERY_SMTP_USER/SMTP_PASSWORD` | Credencial del proveedor, ambos o ninguno |
| `PASSWORD_RECOVERY_MAIL_FROM` | Correo emisor autorizado, sin nombre visible incrustado |
| `PASSWORD_RECOVERY_IMAGE` | Imagen selectiva validada del backend/worker |

No usar prefijo `NEXT_PUBLIC_`. SMTP sin cifrar y origen HTTP de loopback se
permiten **solo** con `APP_ENVIRONMENT=test`. El backend rechaza al arrancar
activación con configuración incompleta/insegura. No usar el correo público de
contacto como remitente hasta comprobar que el proveedor lo autoriza; revisar
SPF/DKIM/DMARC y preservación del fragmento en el cliente de correo.

Presupuestos independientes: solicitud 5/15 min por IP, confirmación 10/15 min
por IP, global **100/15 min por operación**, destinatario 3/h y espera mínima
de 60 s. Son configurables en `.env.example`. Redis comparte los contadores;
si está configurado y falla, **solo esta recuperación falla cerrada**. En un
despliegue de varios procesos es obligatorio configurar Redis. Los identificadores
de correo/IP se protegen con HMAC; no se guardan correos en claves de límites.

### Confianza de ingress

Next firma una aserción efímera de cliente ligada al endpoint. Backend comprueba
firma y antigüedad; las llamadas directas mantienen la IP observada por el API.
No se acepta un bearer inventado ni `X-Forwarded-For` libre para obtener presupuesto.

Con Next expuesto directamente y sin cabecera confiable, usa un presupuesto web
compartido conservador (5/15 min): **no identifica IP individuales**. Para activar
a usuarios reales, configurar `PASSWORD_RECOVERY_TRUSTED_IP_HEADER` únicamente
detrás de un ingress que sobreescriba esa cabecera y bloquee el acceso directo a
Next. Esta integración de red debe validarse en el despliegue HTTPS real; no se
considera probada por las pruebas locales con cabeceras firmadas.

### Secuencia operativa

1. Mantener flag apagado; respaldar base y verificar el dump. Preparar imagen
   selectiva con `execution/prepare_scoped_backend.py`, no mezclar pendientes de
   multimedia/IA/Dockerfile. Aplicar `alembic upgrade head` con esa imagen.
2. Configurar secretos en entorno/gestor, URL, Redis, SMTP/ingress y verificar
   destinatarios existentes. No pegar credenciales en conversaciones ni docs.
3. Hacer prueba autorizada con buzón controlado y revisar spam/dominio/demora.
4. Activar flag, recrear backend/Next y arrancar el worker opt-in:
   `docker compose --profile recovery up -d --no-build --no-deps backend frontend recovery-worker`.
   El servicio usa la imagen validada, no un rebuild implícito del árbol roto.
5. Observar salud y logs saneados del worker; alertar por trabajos `failed` y
   solicitudes pendientes más antiguas que el intervalo normal de procesamiento.
   `202` no sustituye la supervisión de entrega ni la revisión del proveedor.

Para suspender, desactivar flag y recrear backend/Next/worker; ejecutar una
iteración del worker con flag apagado para limpiar pendientes y detenerlo si no
se necesita. Los enlaces enviados se rechazan mientras esté apagado. En incidente
de claves, rotar la clave dedicada invalida los enlaces anteriores y hace
indescifrables los envíos antiguos; cancelar pendientes y solicitar nuevos enlaces.
No restaurar una base vieja ni bajar `token_version` para deshacer un despliegue:
podría resucitar credenciales anteriores. Preferir flag apagado y corrección hacia adelante.

## Pruebas reproducibles

- Backend: `pytest app/tests/ -q`, Ruff y mypy; migración reversible solo en base
  efímera. Tests de recuperación incluyen SMTP real local, colas, reintento/lease,
  límites/firmas, rollback y carreras con conexiones PostgreSQL independientes.
- Frontend: typecheck/lint/build y Playwright `--project=password-recovery`.
  Requiere `RECOVERY_TEST_API`, `RECOVERY_TEST_MAILBOX`, `RECOVERY_TEST_AUTH`
  (JSON efímero protegido), y `FRONTEND_BASE_URL` apuntando a instalación test.
- `execution/recovery_test_mailbox.py`: SMTP/HTTP en memoria para pruebas;
  solo acepta `@example.com`. Nunca desplegar ese buzón junto a cuentas reales ni
  exponer sus puertos fuera de loopback en el host.
- `execution/seed_recovery_review.py`: se ejecuta dentro del API test con base
  sin usuarios, crea cuentas sintéticas y emite bundle temporal. Redirigir con
  `umask 077`, sin mostrarlo; destruir bundle y stack al acabar.
- E2E crea un destinatario nuevo por corrida, recibe el correo real aislado y
  comprueba GET no consumidor, fragmento sin filtración, formulario, doble envío,
  cierre de sesiones, login, rechazo de reutilización y origen malicioso, además
  de layout/IDs/teclado y exclusión de analítica.

Los resultados de la entrega y el snapshot concreto figuran en
`memory/session_summary.md`; no validan los pendientes ajenos del árbol completo.
