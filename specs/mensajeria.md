# SPEC — MENSAJERIA

Desarrollar conforme a `MASTER_PROMPT.md`, secciones 33, 35 y 37.

## Estado: implementado en Fase 8

## Principio rector

**Una conversación interna no es un caso raro: es el caso por defecto.** El
riesgo principal de un sistema de mensajería en un despacho no es que un
mensaje se lea tarde, sino que una conversación interna llegue al portal del
cliente. Por eso la regla se aplica en tres capas independientes:

1. La capa de servicio rechaza añadir a un usuario de cliente a una
   conversación interna. **Rechaza con error, no ignora en silencio**: si el
   despacho cree que ha avisado al equipo y en realidad nadie fue notificado,
   el fallo es invisible hasta que es tarde.
2. La visibilidad de un listado filtra por tipo de conversación, además de por
   participación.
3. La ausencia de acceso responde `404` y no `403`, para no confirmar la
   existencia de la conversación a quien no participa en ella.

## Modelo de datos

Cinco tablas:

| Tabla | Contenido |
| --- | --- |
| `conversations` | Hilo, con tipo `interna`/`cliente`, expediente y cliente opcionales |
| `conversation_participants` | Membresía, rol, `last_read_at`, `is_muted`, `left_at` |
| `messages` | Mensaje, con borrado lógico y marca de mensaje de sistema |
| `message_attachments` | Archivo adjunto, con SHA-256 y clave de almacenamiento |
| `notifications` | Aviso de mensaje, documento, evidencia o vencimiento |

`uq_conversation_participant (conversation_id, user_id)` hace imposible el
participante duplicado.

`messages.sent_at` tiene valor por defecto **en Python**, no solo
`server_default=func.now()`. En PostgreSQL `now()` es la marca de tiempo de la
transacción: todos los mensajes escritos dentro de una misma petición
compartirían un instante y el orden del hilo sería arbitrario. Un chat que se
lee en orden aleatorio es un chat que no sirve.

## Visibilidad

`MessagingService._visibility_clause` compone:

- el usuario es participante activo, **o**
- es personal interno y la conversación es interna, **o**
- es un usuario de cliente y la conversación pertenece a su cliente.

La pertenencia se resuelve por `user_id`, no por rol: ser administrador no es
una credencial para leer el correo de otras personas.

## Permisos

| Permiso | administrador | abogado | asistente | cliente |
| --- | --- | --- | --- | --- |
| `messages:read` | sí | sí | sí | sí |
| `messages:send` | sí | sí | sí | sí |
| `messages:create_conversation` | sí | sí | sí | no |
| `messages:attach` | sí | sí | sí | no |
| `messages:archive` | sí | sí | sí | no |
| `messages:manage_participants` | sí | sí | sí | no |
| `notifications:read` | sí | sí | sí | sí |
| `notifications:send` | sí | sí | sí | no |

El portal del cliente es un canal hacia el despacho, no un lugar de trabajo: el
cliente participa y responde, pero no abre hilos, no adjunta y no archiva.

**`messages:archive` y no `messages:delete`.** El borrado de mensajes es lógico
(`deleted_at`) y la fila sobrevive; el permiso se llama `archive` para no
contradecir la invariante del proyecto de que los roles operativos no poseen
ningún permiso `*:delete`. Es el mismo criterio que `evidences:archive`.

El test `test_every_role_permission_exists_in_the_catalog` protege contra el
fallo que hizo esta fase: un permiso asignado a un rol pero ausente del catálogo
de definiciones no lo siembra ninguna migración, y el síntoma es un `403` sin
causa visible.

## Adjuntos

Un adjunto de chat **no es una evidencia**: no tiene valor probatorio y no
entra en la cadena de custodia. Aun así se valida con la misma rigor que un
documento, porque un archivo que llega por el canal de mensajería llega igual:

- content sniffing por magic bytes;
- rechazo de ejecutables aunque el nombre diga `.pdf`;
- límite de tamaño y de número de archivos por mensaje;
- SHA-256 registrado y **verificado en cada descarga**: si el hash no
  coincide, la descarga se bloquea;
- clave de almacenamiento derivada de identificadores del servidor
  (`messages/<conversation>/<attachment>.ext`), nunca del nombre subido;
- la descarga se sirve siempre como `attachment`, nunca `inline`.

## Auditoría

`change_logs` registra creación de conversación, envío, archivado, cambios de
participantes y notificaciones. **El cuerpo del mensaje nunca se escribe en la
auditoría**: la tabla de auditoría no debe convertirse en una segunda copia de
la correspondencia del despacho, con el mismo riesgo de exposición y sin
ninguna ventaja. `test_message_audit_never_stores_the_body` lo verifica con un
marcador que no debe aparecer en `old_value` ni en `new_value`.

## Notificaciones

Se genera una notificación por mensaje a cada participante salvo al emisor, a
los que han salido del hilo (`left_at`) y a los que han silenciado la
conversación (`is_muted`). Una notificación solo puede marcarse como leída por
su destinatario. Los tipos disponibles cubren mensaje, conversación, cambio de
expediente, evidencia o documento publicado, audiencia y vencimiento.

## Límite de tasa

Los mensajes tienen perfil propio, más estricto que el general y más laxo que
el de autenticación. El perfil se aplica por ruta y método: solo los `POST`
que escriben.

## Endpoints

| Método | Ruta | Permiso |
| --- | --- | --- |
| `POST` | `/api/v1/conversations` | `messages:create_conversation` |
| `GET` | `/api/v1/conversations` | `messages:read` |
| `GET` | `/api/v1/conversations/{id}` | `messages:read` + participación |
| `PATCH` | `/api/v1/conversations/{id}` | `messages:manage_participants` |
| `POST` | `/api/v1/conversations/{id}/messages` | `messages:send` + `messages:attach` |
| `POST` | `/api/v1/conversations/{id}/participants` | `messages:manage_participants` |
| `GET` | `/api/v1/messages/{id}` | `messages:read` + participación |
| `DELETE` | `/api/v1/messages/{id}` | `messages:archive` |
| `GET` | `/api/v1/messages/attachments/{id}` | `messages:read` + participación |
| `GET` | `/api/v1/messages/unread/summary` | `messages:read` |
| `GET` | `/api/v1/notifications` | `notifications:read` |
| `POST` | `/api/v1/notifications/{id}/read` | `notifications:read` + propiedad |
| `POST` | `/api/v1/notifications/read-all` | `notifications:read` |

## Verificación

- 43 tests en `app/tests/test_messaging.py`.
- Suite completa: **486 tests, 84.59 % de cobertura**, Ruff y mypy limpios.
- Migraciones `a9b0c1d2e3f4` (tablas) y `b0c1d2e3f4a5` (permisos) verificadas con
  `downgrade` y `upgrade`: los 8 permisos y las 5 tablas aparecen y desaparecen
  de forma simétrica.

## Pendiente

- No hay cifrado en reposo específico para el cuerpo de los mensajes. El
  volumen se apoya en el cifrado del volumen de base de datos.
- No hay búsqueda de texto completo ni conversationes grupales.
- No hay respuesta en hilo (`reply_to`): todos los mensajes cuelgan del hilo.