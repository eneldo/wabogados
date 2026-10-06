# NEXT STEPS

## Hallazgos de la auditoría del 2026-10-05 — Fase 1 CERRADA el 2026-10-06

**Los ocho primeros están cerrados.** La puerta quedó en **810 pruebas, 86,95 % de
cobertura**, `ruff` y `mypy` limpios, y las tres migraciones nuevas verificadas con
`downgrade` + `upgrade`. El noveno (documentación) sigue abierto, y hay un décimo
hallazgo nuevo sin cerrar más abajo.

1. ~~**IDOR en documentos**~~ **Cerrado**: el alcance de expediente es obligatorio en
   `get_visible_document` y los cinco endpoints pasan por un único
   `_visible_document()`. Seis pruebas.
2. ~~**`SECRET_KEY` con valor por defecto conocido**~~ **Cerrado**:
   `assert_production_is_safe` se niega a arrancar en producción.
3. ~~**`X-Forwarded-For` se confía sin proxy**~~ **Cerrado, pero el primer arreglo
   estaba a medias**: se arregló `get_client_ip` y solo se actualizó el limitador.
   `audit.py` y las seis llamadas de evidencias seguían sin proxies, así que detrás de
   un proxy real **toda la auditoría registraba la IP del proxy**. Seguro frente a
   falsificación e inútil para peritaje. Ahora `_trusted_proxies()` se lee de settings
   en tiempo de llamada, y hay prueba de *cableado*, no de seguridad.
4. ~~**`TrustedHostMiddleware` con URLs completas**~~ **Cerrado**:
   `allowed_hosts_from_origins()`.
5. ~~**`evidences:update` ausente del catálogo**~~ **Cerrado**: catálogo, matriz de roles
   y base (migración `a1b2c3d4e5f6`). El endpoint llevaba muerto desde que se escribió
   el módulo.
6. ~~**Adjuntos leídos íntegros y sin límite de cantidad**~~ **Cerrado**: `413` antes de
   leer, por cantidad y por tamaño. Lección asociada: el campo del formulario debe
   llamarse como el parámetro (`files`, no `file`); enviado mal, la prueba pasa sin
   ejercitar nada.
7. ~~**Alcance ausente**~~ **Cerrado en facturación y `create_evidence`, y también en
   multimedia** (este último estaba fuera de la lista original).
   - Facturación, las diez rutas. Las facturas **sin** `case_id` siguen visibles para
     quien tenga `invoices:read`, y es deliberado: recepción redacta facturas sin
     expediente. Lo fija `test_a_firm_wide_invoice_is_not_case_scoped`.
   - `create_evidence`: la comprobación era código muerto.
   - **Multimedia**: ninguna ruta tomaba `get_user_scope` y `media_items.case_id` está
     poblado. Los recursos sin expediente son material firm'swide y siguen visibles.
   - El **directorio de clientes/abogados** resultó **correcto por diseño**: ni `Client`
     ni `Lawyer` tienen relación con `Case`. No era un hallazgo.
8. ~~**Descargas de multimedia sin rastro**~~ **Cerrado**: tabla `media_access_logs`
   (migración `b2c3d4e5f6a7`) con `bytes_served` real, para que una lectura con `Range`
   no anote el tamaño completo.
9. **46 discrepancias documentales** — **sigue abierto**. Dos comandos documentados son
   Hazard: `scripts/backup.sh --restore` no restaura, y `RESTORE.md` dice detener solo
   backend y frontend dejando el `evidence-worker` escribiendo sobre la base que se
   repone.

## PENDIENTE CRÍTICO: el alcance en `messages.py` (2026-10-06, SIN arreglar)

**Es el mismo fallo que los otros cuatro y el más grave de todos, porque descarga
bytes.** No está cerrado.

`Conversation` **sí** tiene `case_id` con relación a `Case`. `create_conversation` **sí**
resuelve el alcance, y por eso `test_unassigned_lawyer_cannot_open_thread_on_another_case`
pasa. **Nada lo vuelve a comprobar al salir**: la participación era la única puerta de
las lecturas.

> Un abogado que estuvo en un hilo y luego salió del expediente **sigue leyéndolo**,
> con su `case_number`, y puede descargar los adjuntos. Estar en la conversación
> responde «me escribieron esto»; no responde «puedo seguir viéndolo».

- `backend/app/services/messaging.py` **no acepta ningún parámetro de scope**, al
  contrario que los seis services ya corregidos. El trabajo está a medias justo en el
  lado opuesto: el service sabe calcular el alcance, pero solo se lo pide al escribir.
- Sin filtrar: `get_conversation`, `list_conversations`, `list_messages`,
  `read_attachment`, `get_message`, y las escrituras `update_conversation`,
  `add_participant`, `send_message`, `delete_message`.
- `list_conversations` acepta `case_id` como filtro **sin validar** que el expediente
  esté en alcance.
- `_visibility_clause` tiene un docstring que promete *«Staff with case wide read see
  conversations of their scope»* y la implementación **no contiene ninguna cláusula de
  expediente**. Hay que corregir esa documentación al arreglar el código.
- Los hilos **sin** `case_id` deben seguir funcionando: son notas internas ordinarias.
  `test_staff_drafts_but_neither_issues_nor_voids` ya demostró que un filtro que
  responde «no existe» donde la verdad es «ese no es tuyo» es una regresión.
- Reutilizar el criterio ya fijado dos veces: expediente presente → se filtra;
  `NULL` → material firm'swide, visible.

### La regla de los ocho routers que NO llevan `get_user_scope` (y está bien)

`admin`, `admin_metrics`, `admin_settings`, `auth`, `clients`, `consultations`, `health`
y `lawyers` se revisaron uno a uno: o no tienen relación con `Case`, o son material
firm'swide. `admin_metrics` consulta `Evidence` pero solo devuelve agregados, nunca
filas ni un `case_id`. **No "corregirlos": ya está revisado.**

## Módulos de administración por construir

La API de los nueve módulos reales está completa. Falta la interfaz, en este
orden:

1. ~~**Expedientes**~~ — **hecho**: alta, edición, cierre (`POST /close`, nunca
   `DELETE`), partes, incorporación de abogados y ficha 360 sobre
   `GET /cases/{id}/360`.
2. ~~**Agenda y audiencias**~~ — **hecho**: Día/Semana/Mes, filtros,
   vencimientos, eventos y ciclo completo de audiencias con registro,
   reprogramación, conflicto y trazabilidad.
3. ~~**Mensajes**~~ — **hecho**: bandeja personal del despacho, filtros, métricas,
   creación de hilos internos o de cliente, lectura, respuesta, adjuntos, archivado
   lógico de mensajes propios y cierre confirmado. La participación, no el rol
   administrativo, sigue gobernando el acceso.
4. ~~**Documentos**~~ — **hecho**: listado global con `GET /documents` (alcance,
   tipo, estado, confidencialidad, visibilidad, `legal_hold` y búsqueda sobre
   título, descripción y expediente) y ficha con versiones, hash y descarga. La
   regla no cambia: un documento acaba en `anulado`, una versión en ser
   reemplazada.
5. ~~**Seguridad**~~ — **hecho**: directorio con búsqueda y filtros por rol y
   estado, altas y ediciones en diálogo, asignación de roles, desactivación y
   reactivación, catálogo de roles con los permisos que concede cada uno y el
   catálogo completo por recurso, y la auditoría paginada con filtros de texto,
   resultado y actor. `GET /admin/users/{id}` se añadió en esta fase, así que la
   ficha de usuario ya no se deriva de la lista.
6. ~~**Configuración**~~ — **hecho**: `/admin/configuracion` lista `system_settings`
   agrupada por categoría, con alta y edición en diálogo, borrado por clave con
   confirmación y el historial de cambios que deja el valor anterior. El valor se
   edita como el texto que se guarda y la columna «tipo» dice con qué se relee.

**Los nueve módulos reales tienen pantalla** y el décimo, Multimedial, se construyó
el 2026-10-03 anulando la prohibición del brief (ADR-055): Dashboard, Clientes,
Abogados, Expedientes, Agenda, Mensajes, Documentos, Seguridad, Configuración y
Centro multimedia. Solo quedan en el menú los dos módulos que el brief todavía
prohíbe (IA Jurídica y Facturación), inertes con su motivo y con su alcance
escrito.

### Los dos módulos futuros que faltan

`MASTER_PROMPT.md` los sitúa en «Fases futuras, NO implementar aún» y solo pide
que la arquitectura quede preparada. Sus alcances están escritos en **ADR-054** y
visibles en la ficha de cada módulo, para que la dirección vea una decisión y no
una ausencia:

**Los módulos V3 y V5 ya están construidos** (corregido 2026-10-05). La nota de
abajo era **obsoleta**: ambos tienen backend, permisos sembrados, migraciones y
pantalla, y funcionan.

1. ~~**V4 Centro multimedia**~~ — **construido**: la dirección ordenó levantar la
   prohibición del brief (ADR-055). Queda `/admin/multimedia` con biblioteca
   interna, `Range` para poder reproducir y borrar por desactivación.
2. ~~**V3 Facturación**~~ — **construido y verificado (2026-10-05)**:
   `/admin/facturacion` con alta, listado, conceptos, pagos, saldo derivado por el
   servidor, emisión y anulación que conserva el número. Permisos `invoices:*`.
3. ~~**V5 IA jurídica**~~ — **construido y verificado (2026-10-05)**:
   `/admin/ia-juridica` con búsqueda literal sobre expedientes, documentos y
   biblioteca, y resumen extractivo. La pantalla **dice en voz alta** que no hay
   modelo: la generación asistida queda pendiente de proveedor.

**Lo que al centro multimedia le falta, y por qué no se entregó entero.** El suelo
está puesto (tablas, cola y claves, 2026-10-05), pero las cuatro capacidades son
trabajo de varias sesiones, no un botón:

1. **Miniaturas.** Lo más cercano a cerrar y **no necesita `ffmpeg`**: reutiliza
   `evidence_processing` (Pillow), que ya genera miniatura de 400 px. Falta el
   servicio que la escriba, la ruta que la sirva (`/api/media/[id]/thumb`, el
   original hoy se sirve entero) y la celda/poster del frontend.
2. **Duración medida.** La columna existe desde `b6c7d8e9f0a1` y **nadie la
   escribe**. Para vídeo y audio hace falta `ffprobe`; mientras tanto,
   `MediaUpdate.duration_seconds` deja que el **cliente** la escriba, lo que
   contradice el comentario del modelo. Eso debería cerrarse antes que las demás
   cosas: es un dato que hoy acepta cualquiera.
3. **Transcodificación.** Falta `ffmpeg` en la imagen (builder y runtime), una
   dependencia de vídeo en Python, un contrato de **escritura en streaming**
   porque `StorageBackend.write()` solo acepta bytes completos —con 500 MB de
   tope, hoy eso significa el archivo entero en memoria—, y elegir formatos y
   política.
4. **Archivos grandes.** Hoy hay un tope de 500 MB y un **413 que admite que la
   cola no está disponible**. Falta el worker (copiando el patrón `SKIP LOCKED`
   de `evidence_worker`) y el servicio de Compose. Además `MAX_MEDIA_BYTES` no
   está en `.env.example` y no hay ni un test del 413.

Cada uno necesita: tabla con paginación, alta en diálogo, ficha con edición,
diálogo de confirmación y, donde aplique, el motivo por el que **no** hay botón
de borrar. La base ya está: `app/(admin)/admin/layout.tsx`, `lib/admin-nav.ts`,
`components/admin/form-controls.tsx` y `components/admin/page-furniture.tsx`.

Al añadir un módulo, mirar primero el nombre del permiso en la API: si el módulo
se autoriza por alcance y no por permiso, no se pone `permission` en
`lib/admin-nav.ts`, porque una llave que nadie tiene esconde el módulo a todos.

Dos detalles pendientes de la base:

- La cabecera del shell muestra el correo como nombre visible porque
  `/auth/me` no devuelve `full_name` para administración.
- ~~La salida de sesión borra las cookies pero no revoca la sesión de refresco en
  el servidor.~~ **Resuelto (2026-10-04)**: `signOut` llama a
  `POST /api/v1/auth/logout` con el token de refresco antes de borrar las
  cookies, y revoca **solo esa sesión**. Limitación que queda: si el token de
  acceso ya expiró, el endpoint exige autenticación y la revocación no ocurre;
  ese token de refresco sigue vivo hasta caducar. Sin `revokeSession` la sesión
  duraba siete días.

## Pendientes de la web pública

1. **Aviso de privacidad aprobado por el despacho.** El texto está redactado y
   la página lo declara pendiente, pero faltan la razón social completa y el
   canal para ejercer los derechos. Sin eso no debe publicarse en producción.
2. ~~**Interfaz de la cola de solicitudes en el portal.**~~ **Construida
   (2026-10-05):** `/admin/solicitudes` lista y filtra por estado, pagina, abre la
   ficha, actualiza estado y notas, y reserva el borrado físico confirmado para
   `consultations:erase`. Verificada sobre Docker: alta pública, lectura, cambio de
   estado y notas, y borrado físico; 390×844 sin overflow ni ids duplicados.
3. **Confirmación por correo.** La API registra y confirma en pantalla, pero no
   envía correo: no hay servicio de correo configurado ni dirección de la firma.
4. **Correo electrónico de la firma**: lo publica protegido por Cloudflare.
5. **Contenido editorial** de actualidad, pendiente de aprobación.
6. **Términos y textos legales** adicionales al aviso de privacidad.

## Immediate

**La superficie de administración está cerrada** y las seis puertas de calidad
pasan: `ruff`, `mypy` estricto, `alembic`, la suite completa con su suelo de
cobertura, las de evidencias y la de documentación. 711 pruebas, 86,30 %, cero
avisos, y los ceilings de dependencias fijados a lo verificado (ADR-063).

El trabajo de producto que queda es de otra clase: la confirmación por correo
(no hay servicio de correo configurado), el contenido editorial de la web pública
y los dos puntos de
`docs/DEPLOY.md` que cuestan datos si se ignoran.

Ninguna de las Fases 0A a 10 del backend está cerrada: todas tienen interfaz y
pruebas, y el formulario público tiene su ciclo completo.

Lo que sigue son decisiones de infraestructura y de proveedor, todas ellas
documentadas en `docs/DEPLOY.md` con su apartado "What is not ready". De los tres
puntos que costaban datos, **uno está cerrado** y los otros dos no se pueden
cerrar desde aquí:

1. ~~Verificación del respaldo de objetos por digest~~ **hecho**: ADR-062.
2. Destino `BACKUP_REMOTE_ENDPOINT` en otra máquina o proveedor. **Proveedor
   decidido el 2026-10-05: bucket S3 de otro proveedor.** Queda solo lo que la
   firma debe crear: la cuenta, el bucket con versionado y la credencial
   dedicada. Pasos en `docs/RESTORE.md`. La inmutabilidad (Object Lock) sigue
   **sin decidir** y anotada como pendiente de política.
   - El código ya **rechaza** que el destino sea el bucket de los documentos, que
     era una regla escrita y no comprobada.
3. ~~Rehearsal de restauración completo con la aplicación caída.~~ **Ejecutado
   (2026-10-05)** con la aplicación detenida: base borrada, `pg_restore` y
   almacenamiento repuesto desde la copia. Los recuentos coinciden antes y
   después, 6 de 6 versiones verificadas por digest, API operativa. Informe en
   `docs/RESTORE.md` sección 9. **Lo que queda:** que lo ejecute una persona
   distinta de quien escribió el sistema, y ejecutar `scripts/backup.sh` entero en
   un host con `bash`.

Después: antivirus para evidencias y rate limiter sobre Redis. El worker de
evidencias ya corre como servicio dedicado de Compose. El versionado del bucket
ya se exige al arrancar cuando
`STORAGE_BACKEND=s3`; el proceso falla si el bucket no existe o no puede
habilitar la protección.

## Technical Debt

1. **Los gates de `ruff` y `mypy` pasan, son reproducibles y el techo de
   SQLAlchemy se levantó a 2.1 (2026-10-04).**
   - **`mypy` no podía pasar en una instalación limpia.** El extra `dev` no
     incluía los stubs de `python-jose` ni de `passlib`. Añadidos.
   - **Los 33 errores con SQLAlchemy 2.1 tienen una sola causa raíz.** No eran
     33 problemas: las anotaciones `Select[tuple[Modelo]]` de los helpers de
     `dashboard.py` envenenaban el tipo de fila y arrastraban a los atributos
     de entidad. Con `Select[Any]` —la convención que el propio archivo ya
     usaba en `_count` y `_rows`— y `Select[Any, Any]` donde se seleccionan dos
     entidades, **`mypy` quedó limpio en 2.1.x**. Se comprobó con `reveal_type`
     antes de reescribir: `.scalars().all()` da `Sequence[Case]` en 2.1, así que
     los errores de atributo eran consecuencia, no causa.
   - `Result.rowcount` no existe en el contrato de 2.1. Resuelto **sin `cast`**:
     el `UPDATE` de revocación usa `RETURNING id` y cuenta las filas.
   - Ceiling final: `sqlalchemy>=2.1,<2.2`, `mypy>=1.17,<1.18`,
     `ruff>=0.12,<0.13`. Verificado en instalación limpia.
   - **Passlib eliminado.** Sustituido por `argon2-cffi`, que es la librería a la
     que passlib delegaba, con los mismos parámetros (`argon2id`, t=3, m=64 MiB,
     p=4). Los hashes existentes siguen validando: hay un hash de passlib
     congelado como contrato en `test_password_hashing.py`, y se comprobó un
     login real sobre un hash escrito por passlib. Passlib ya no está en la
     imagen.
   - Avisos de constantes HTTP obsoletas de Starlette eliminados con
     `app/core/http_status.py`, porque el nombre nuevo no existe en Starlette
     0.4x y el viejo avisa en 1.x; el host tiene 0.47 y el contenedor 1.7.
   - La nota antigua sobre `ASYNC240` estaba **obsoleta**: esa regla no existe
     en ruff 0.12.x.

2. Sustituir el almacenamiento local de objetos por MinIO/S3 en producción.
3. ~~Reemplazar Passlib por un wrapper de Argon2 mantenido.~~ **Hecho**
   (2026-10-04): `argon2-cffi` con los parámetros que passlib usaba, y un hash
   de passlib congelado en `test_password_hashing.py` como contrato.
4. ~~Llevar el estado del rate limiter a Redis antes de ejecutar varios workers.~~
   **Hecho (2026-10-05)**: almacén compartido con ventana deslizante, script Lua y
   degradación ruidosa. Falta quitar `slowapi`, que es dependencia muerta.
5. **Antivirus para evidencias.** Requiere dos decisiones de la firma: dónde se
   analiza y qué se hace con un positivo. El hueco de código existe y está
   localizado: `EvidenceStatus.SCANNING` se asigna y no escanea nada
   (`services/evidence.py:293`).
6. **Cerrar los huecos de la migración a S3** antes de producción. **Arreglado lo
   que era error** (2026-10-05): `--rekey` con clave y extensión correctas e
   idempotente, `--offset`, archivos ausentes reportados y código de salida 4 si
   la migración queda incompleta. **Queda una limitación de alcance**: el CLI solo
   migra `document_versions`, no `evidence_files`, `evidence_derivatives`,
   `message_attachments` ni `media_items`.
   No verificable aquí: la imagen `minio/minio` no se puede descargar en este
   entorno, así que el camino S3 solo se ha probado contra `moto`.
7. Verificación criptográfica de firma digital en PDF.
8. Derivaciones PDF rasterizadas.
9. Podar filas caducadas de `refresh_tokens` periódicamente.
10. Cifrado en reposo específico para el cuerpo de los mensajes.
11. Búsqueda de texto completo, conversaciones grupales y respuestas en hilo.
12. Cache corta para las cifras del panel.
13. Series temporales en el panel y agregados de almacenamiento.
14. Interfaz: falta la **usuario** en la ficha de evidencia de la sección 39.
    Requiere que el endpoint de custody exponga el nombre en vez de `actor_id`.
15. ~~Runner de pruebas de frontend~~ **Hecho (2026-10-05)**: Playwright con
    `npm run test:e2e`. Comprueba ids duplicados y desbordamiento horizontal en
    once rutas de administración a 320, 390, 768 y 1440 px. Requiere
    `E2E_EMAIL` y `E2E_PASSWORD` de una cuenta de administración; sin ellas
    **falla** en vez de saltarse. Queda por cubrir lo que la puerta no ve: foco,
    contraste y teclado real por diálogo.
16. ~~Pantalla de la cola de solicitudes para el personal del despacho.~~
    **Hecha y verificada (2026-10-05)** sobre el stack Docker.
17. **Reactivar y reabrir no existen como operación.** Desactivar un cliente o
    abogado y cerrar un expediente son de una dirección. Si la firma lo pide, es
    una decisión nueva: reactivar necesita endpoint, y reabrir un expediente
    reescribiría su historia.
18. **Comprobación de ids duplicados y de desbordamiento como puerta.** Se
    comprueba a mano al cambiar un listado y ha detectado tres fallos reales esta
    semana. Automatizarla sobre las rutas de administración es barato y evita que
   dependa de que alguien se acuerde.
17. La zona institucional de Agenda está fijada en código a `America/Bogota` y
    UTC-5. Si la firma opera en otra zona, debe pasar a configuración compartida
    antes del despliegue.
