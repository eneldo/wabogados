# Última sesión

Fecha: 2026-10-21 (continuación) y 2026-10-22

## Restauración de la base real desde el disco externo (2026-10-22)

Fuente: `Seagate Expansion Drive/RESPALDO_PC_ANTIGUO/Docker/`, con
`inventario_sha256_final.csv` que firma cada artefacto. Los dos digests
salieron idénticos antes de escribir nada.

1. **La base era un cluster dump de pg_dumpall 17.6**, no un dump de una base:
   reconstruye roles (con la contraseña SCRAM del PC antiguo) y dos bases, una
   basura (`wabogadoes`). Se restauró **solo la sección de `wabogados`**
   (líneas 193–4395, con su par `\restrict`/`\unrestrict` propio) con
   `ON_ERROR_STOP=1`: el rol mantiene la contraseña local del compose y el
   backend autentica sin cambios. Verificación TCP del rol: `wabogados|wabogados` OK.
2. **Inventario restaurado = documentado**: 43 tablas · 9 usuarios · 5 clientes
   · 5 expedientes · 4 eventos · 3 documentos · 246 filas de auditoría
   (el dump es del 17 de octubre, doce más que el ensayo del 5).
   Alembic: `e9f0a1b2c3d4` en el dump → `upgrade head` (`b2c3d4e5f6a7`,
   46 tablas) → downgrade y re-upgrade verificados sobre los datos.
3. **El almacén de objetos era otro artefacto**: `Volumenes/wabogados_evidencias.tar.gz`,
   digest verificado contra el inventario. Extraído al volumen
   `wabogados_v1_master_storage_data`: **21 archivos**, uid 10001 = `app` del
   contenedor. `verify_integrity --mode full`: 0 ausentes · 0 corruptas · OK.
4. **PostgreSQL 5432 del host lo ocupa el servicio systemd de Fedora
   (postgresql 18.6)** — no se tocó; el contenedor del proyecto mapea 5433
   (el mapeo solo es de host, el backend interno no cambia). Recordado para
   herramientas del host que quieran ver la base: puerto `5433`.
5. **Stack levantado y sano sin MinIO**: `backend·frontend·postgres·redis·
   evidence-worker` todos healthy; `health/ready` = `{"status":"ready",
   "database":"up"}` y frontend 200. Los dos servicios `minio*` quedaron fuera
   a propósito (ver KNOWN_ISSUES: las imágenes oficiales ya no se publican en
   ningún registry, el pin de compose apuntaba a una etiqueta muerta y el
   almacenamiento real es `STORAGE_BACKEND=local`).

## Respaldo programado activo (2026-10-22, cierre de la recomendación #1)

Circuito completo ya en marcha, **con datos reales y verificado end-to-end**:

- `scripts/backup.sh` reutilizado como motor (dump custom, objetos,
  manifiesto, digest, prueba de restauración en la base de producción) con dos
  ajustes para el Compose 5.6.1 de este host (`run --no-deps` en vez de
  `exec -v`, `RUN_DIR` absoluto) y el delegado arreglado en la revisión
  de alembic de `config.json`.
- `scripts/backup_host.sh` nuevo: copia secundaria al Seagate con comparación
  de dump byte a byte, retención (14 local / 30 externa), exclusión mutua con
  `flock` y entorno reproducible para cron.
- La primera corrida real: **los 95 ficheros del manifiesto verificados,
  restauración probada en base raíz (`users 9 · documents 3 · resultado OK`),
  copia externa idéntica** en
  `Seagate/RESPALDO_WABOGADOS/20261022T020735Z`.
- Programado: crontab del usuario (no versionado, contiene la ruta del host)
  `45 3 * * *` diario a las **03:45 UTC**. `vaner` ya está en el grupo docker
  de `/etc/group`, así que lo lanza aunque su sesión gráfica no refleje el grupo.
- Nota del host: el PostgreSQL 18.6 de systemd ocupa el 5432; el proyecto
  mapea **5433** en host (más en session_summary §restauración).

## Auditoría y migración Windows → Fedora: normalización y cierre del alcance de mensajes (2026-10-21)

**Contexto nuevo del entorno:** todo el código anterior se escribió en Windows;
desde hoy el entorno de trabajo es Linux Fedora. Eso explica el estado que
encontró la auditoría: 24 ficheros tracked en CRLF y los mensajes de
`NEXT_STEPS`/`session_summary` asumiendo PowerShell 5.1 y WSL.

Se aplicaron las correcciones de la auditoría, en tres commits:

1. **`cf7dd56` — Normaliza fin de línea a LF.** `.gitattributes` nuevo con
   `* text=auto eol=lf` y exclusiones binarias explícitas. El truco: con el
   atributo en vigor, los 20 ficheros "modificados" solo por EOL desaparecieron
   del diff — el índice y HEAD ya estaban en LF y el estado `M` que quedó
   después de convertir el árbol físicamente era solo caché de stat, refrescada
   con `git add -u`. El árbol, el índice y HEAD quedan en LF verificados.
2. **`128881f` — Alcance de expediente en la mensajería.** El fix de
   `messaging.py` (el pendiente más grave de la auditoría previa: un abogado que
   salió del expediente seguía leyendo hilos y descargando adjuntos) estaba
   escrito en el disco sin confirmar y **enterrado bajo ~6.500 líneas de churn
   de EOL**. Quedó aislado como commit propio con sus 167 líneas de pruebas.
3. **Memoria corregida** (exactamente el patrón de "dato escrito y nunca
   releído"): `project_context` creía que no había CI (existe `quality-gates.yml`
   desde octubre) y que el rate limiter seguía en memoria (Redis se cerró el
   2026-10-05); `AGENTS.md`/maestro referenciaban `known_issues.md` cuando el
   fichero es `KNOWN_ISSUES.md` y en un host Linux sensible a mayúsculas la
   referencia estaría rota; y la nota "el repo no es git" quedó fechada como
   errata histórica.

Copia de seguridad del estado previo en `.tmp/pre-audit-backup-2026-10-21.patch`.

## Verificación de los gates en Fedora (2026-10-21, segunda parte)

Docker instalado en el host (29.9.2 + Compose v5.6.1). La suite corrió contra
`compose.test.yaml` con PostgreSQL y Redis reales:

- **`815 pruebas, 86,99 % de cobertura`**, incluidas las 5 nuevas de alcance de
  mensajería — la puerta de seguridad del fix `128881f` está en verde.
- `ruff` y `mypy` estricto: **2 hallazgos en los ficheros del fix** (imports sin
  ordenar, dos líneas >100) y **1 preexistente** en esta instalación
  (`EMAIL` sin anotación en `create_admin.py`). Corregidos en `e2c705e`:
  ruff limpio, mypy sin errores en 161 ficheros, migraciones
  `upgrade → downgrade → upgrade` verificadas.
- Pendiente en este entorno: **gates de frontend** (`tsc`, ESLint, build de
  Next.js) y conectar el remoto para que `quality-gates.yml` corra de verdad.

## Gates de frontend en verde (2026-10-21, tercera parte)

Sobre `frontend/node_modules` heredado de la instalación Windows (con binarios
plataforma-específicos), `npm ci` reinstaló todo desde el lockfile — la lección:
no arrastrar `node_modules` entre sistemas operativos.

Resultado: `npm run lint` limpio, `tsc --noEmit` limpio, `next build` completo
con las 19 rutas generadas. Los **cuatro gates de frontend pasan en Fedora**;
el ciclo de migración de entorno queda cerrado. Solo queda conectar el remoto
GitHub para la primera corrida real de `quality-gates.yml`.

Nueva entrada en `KNOWN_ISSUES.md`: 5 avisos high de `npm audit`, todos en la
cadena de lint (`eslint-config-next`→`fast-glob`→`micromatch`→`braces`),
devDependencies sin impacto productivo; se resuelven con el próximo upgrade de
Next, no con `--force`.

**Pendientes de esta migración de entorno**: instalar Docker y el toolchain de
backend en Fedora, ejecutar la suite completa contra `compose.test.yaml`, y
decidir el destino de la capa documental de agentes (`agents/`,
`orchestration/`, `roles/`) que sigue como documentos muertos sin instalación
real en OpenCode.

---

Fecha: 2026-10-02, 2026-10-03, 2026-10-04, 2026-10-05 y 2026-10-06

## Multimedia sin alcance, y la pérdida de un fichero (2026-10-06, segunda parte)

**Alcance en `media.py`, que quedaba fuera de la lista original.** Ninguna de sus
rutas tomaba `get_user_scope`, y `media_items.case_id` está poblado: el expediente
estaba ahí para filtrar y no se usaba. Un abogado sin asignaciones listaba la
biblioteca entera, abría recursos ajenos, sustituía sus archivos y descargaba los
bytes. Aplicado con el criterio ya fijado en facturación, y con la escritura protegida
contra un `case_id` ajeno.

**Perdí `backend/app/tests/test_messaging.py` y lo recuperé de una foto vieja.**
Encadené `-replace` con `| Out-Null`; la tubería devolvió `$null` y el `WriteAllText`
siguiente vació el fichero: **960 de 1309 líneas**. La red de seguridad falló
porque **aún no existía git**; se inicializó el 2026-10-06 y hoy el comando
siguiente ya no es un riesgo de pérdida. Lo recuperé de
`wabogados_v1_master-backend:latest`, que conservaba una copia de 13 horas antes, y
reapliqué a mano las cuatro pruebas de adjuntos de la sesión.

La suite completa pasa en **810 pruebas, 86,95 %**, `ruff` y `mypy` limpios. **Pero el
fichero recuperado no es byte a byte el que había y eso no se puede demostrar con una
suite en verde.** Es lo único que se perdió, y es la parte que no tiene arreglo. Lo que
sí lo tiene es la causa: **inicializar git**.

**Pendiente y no arreglado: el alcance de `messages.py`.** `create_conversation` resuelve
el alcance —por eso su prueba pasa— pero **nada lo vuelve a comprobar al salir**. La
participación es la única puerta de las lecturas: un abogado que estuvo en un hilo y
luego salió del expediente sigue leyéndolo, con su `case_number`, y descarga los
adjuntos. Es el mismo fallo por quinta vez y el más grave, porque entrega bytes.
`messaging.py` además no acepta ningún `scope_clause`, al contrario que los seis
services ya corregidos, y `_visibility_clause` tiene un docstring que promete un
alcance que la implementación no tiene. Detalle en `NEXT_STEPS.md`.

## Cierre de la Fase 1 de la auditoría (2026-10-06)

Siete puntos cerrados, **804 pruebas, 86,93 % de cobertura**, `ruff` y `mypy`
limpios, y las dos migraciones nuevas verificadas con `downgrade` + `upgrade`.

1. **`SECRET_KEY`**: la aplicación se niega a arrancar en producción con la clave
   conocida.
2. **`X-Forwarded-For`**: solo se cree si el peer está en `trusted_proxies`, y se
   toma la entrada más a la derecha.
3. **`TrustedHost`**: los hosts se derivan de `CORS_ORIGINS`, no de URLs completas.
4. **Adjuntos de mensajes**: se rechaza con `413` antes de leer, por cantidad y por
   tamaño.
5. **`evidences:update`**: el permiso que `PATCH /evidences/{id}` exigía desde que
   el módulo se escribió **nunca estuvo en el catálogo**, así que la ruta respondía
   `403` para todos. Ahora está en el catálogo, en la matriz y en la base.
6. **Alcance**: facturación no tenía `get_user_scope` en ninguna de sus diez rutas,
   y `create_evidence` llamaba `scope_filter(session, actor, CaseScope.ALL)`, que
   devuelve `None` por definición — la comprobación era código muerto.
7. **Auditoría de descargas de multimedia**: `GET /media/{id}/content` servía bytes
   sin escribir nada. Nueva tabla `media_access_logs` con `bytes_served` real, para
   que una lectura con `Range` no anote el tamaño completo.

**Dos hallazgos nuevos salieron de los seis primeros.**

- El punto 2 solo llegó al limitador. `audit.py` y las seis llamadas de evidencias
  seguían usando `get_client_ip(request)` sin proxies, así que detrás de un proxy
  real **toda la auditoría registraba la IP del proxy**. Seguro frente a falsificación
  e inútil para peritaje. Corregido con `_trusted_proxies()` leído de settings en
  tiempo de llamada.
- Las facturas sin `case_id` son de alcance firm'swide. Al filtrarlasStrictamente,
  `test_staff_drafts_but_neither_issues_nor_voids` pasó de `422` a `404`: recepción
  redacta una factura sin expediente y recibía «no existe» en lugar de «un borrador
  no admite pagos». Es peor respuesta que la que reemplazaba. La excepción queda
  **fijada por `test_a_firm_wide_invoice_is_not_case_scoped`**, para que endurecerla
  sea una decisión y no un accidente.

**`/portal` no es una fuga.** Es el panel propio de cada rol, no una vista
administrativa: `dashboard:read` más `get_user_scope` lo cubren, y hay 21 pruebas de
alcance, incluidas «el cliente solo ve lo suyo publicado» y «el abogado sin
asignaciones no ve nada».

## Dos formas de pasar una prueba sin probar nada (2026-10-06)

Las dosValen por sí solas para cualquier revisión futura.

**Una prueba que envía el campo equivocado no falla: desaparece.** Al probar el
límite de adjuntos, envié los ficheros bajo el nombre `file` y el parámetro del
endpoint se llama `files`. FastAPI recibió **cero** ficheros, creó el mensaje sin
adjuntos y devolvió `201`, así que mi `assert 413` falló… por la razón equivocada.
Si no hubiera leído el `DEBUG files= 0`, habría «arreglado» el endpoint para seguir
con una prueba que nunca lo ejercía. Lo que evita esto no es mirar el estado, es la
prueba **de resultado**: ahora existe también `test_a_valid_attachment_reaches_the_service`,
que exige `201` con un adjunto y falla si el campo no llega. Una prueba de éxito es
la que convierte el silencio en un error.

**Cambiar un helper sin cambiar a quien lo llama deja la mitad del sistema como
estaba.** El arreglo de `X-Forwarded-For` hizo el helper seguro por defecto y
actualizó solo el limitador. Nadie lo notó porque el nuevo default nunca es
inseguro —ignora la cabecera—, así que los 769 tests pasaron mientras la auditoría
registraba la IP del proxy. La lección es sobre *degradación*, no sobre seguridad:
un cambio de contrato silencioso se propaga solo a los sitios que se tocan. La
prueba que faltaba no era sobre seguridad sino sobre **cableado**, y por eso
`test_the_audit_trail_uses_the_declared_proxies` parchea settings y afirma el
resultado, no la firma.

## Auditoría completa, y el primer hallazgo arreglado: IDOR en documentos (2026-10-05)

Pediste una auditoría completa. Repartí el trabajo: dos exploradores leyeron
seguridad y coherencia documental mientras yo ejecutaba las puertas. Las puertas
estaban verdes —y eso es precisamente la lección.

**El hallazgo grave: un IDOR que las 769 pruebas no veían.** El listado de
documentos filtraba por expediente; el detalle por identificador no. Un abogado sin
expedientes asignados veía un **listado vacío** y aun así podía leer, editar,
ampliar y **descargar** cualquier documento de la firma adivinando el UUID. Un
cliente podía leer todos los documentos `publicada` de todos los clientes. Cinco
endpoints.

**Lo verifiqué yo antes de creérmelo**, y era exacto: `documents.py:184-192` solo
comprobaba `visibility`, que depende únicamente de permisos, mientras
`browse_documents` usaba `case_scoped`. No era un olvido suelto: era una
**excepción dentro de un patrón que el proyecto ya aplicaba bien** en evidencias,
acciones, agenda y en el propio listado de documentos.

**El arreglo tiene una decisión que merece explicarse.** Podía copiar la firma de
`get_visible_evidence`, donde `scope_clause` es opcional con valor `None`. Con ese
valor por defecto, un endpoint nuevo compila, pasa todas las pruebas y
**reintroduce la fuga sin delatar nada**. Lo hice obligatorio y sin valor por
defecto: ahora `mypy` falla en cualquier llamador que no decida qué expedientes
alcanza. Y centralicé la comprobación en un `_visible_document()` del router,
porque cinco llamadores que arman la cláusula son cinco sitios donde el
siguiente endpoint se olvidará.

**Seis pruebas**, y la que más importa es la última: una que comprueba que **el
llamante legítimo sigue entrando**. Un filtro demasiado estrecho también es un
fallo, y así es como un arreglo de seguridad se convierte en una pérdida de
servicio.

**769 pruebas, 86,71 %**, `ruff` y `mypy` limpios en 158 archivos.

**Queda de la auditoría, sin arreglar:** `SECRET_KEY` con valor por defecto
conocido y sin validación en producción; `X-Forwarded-For` confiado sin proxy
(evade los límites de login y del formulario); `TrustedHostMiddleware` alimentado
con URLs con esquema, que daría 400 en producción; `evidences:update` exigido por
un endpoint y ausente del catálogo; adjuntos leídos sin límite de cantidad. Y
**46 discrepancias documentales**, con un patrón que ya conocía: correcciones
propagadas a medias y la referencia canónica (`MASTER_PROMPT.md`) que nunca se
corrige, de modo que el error se regenera en cada sesión.

## «Desbloquea Facturación e IA jurídica»: ya estaban desbloqueadas (2026-10-05)

Pediste desbloquear dos módulos. Los verifiqué en el navegador antes de tocar
nada y **funcionan los dos**: `/admin/facturacion` con una factura real, cliente,
estado, total, saldo y pagos, y `/admin/ia-juridica` con búsqueda literal y
resumen extractivo.

**La premisa venía de la memoria, y la memoria estaba mal.** Decía que eran los
«dos módulos que el brief todavía prohíbe, inertes con su motivo». Llevaba varias
sesiones propagándose por `NEXT_STEPS` y `project_context` sin que nadie la
comprobara. Esto es el aprendizaje de *un dato escrito y nunca leído* aplicado a
las notas: una afirmación repetida en tres sitios se vuelve más creíble, no más
cierta. Corregida en los tres ficheros, con la evidencia de que funcionan.

Lo único realmente pendiente de IA Jurídica es la **generación asistida**, y la
propia pantalla lo dice en voz alta: «Este módulo no llama a ningún modelo».

## Multimedia: el suelo del pipeline, no el pipeline entero (2026-10-05)

Las cuatro capacidades que faltaban están **ausentes por completo**, y eso no es
un botón: no hay `ffmpeg` en la imagen, ni tabla de derivados, ni worker, y
`StorageBackend.write()` solo acepta bytes completos —con un tope de 500 MB, eso
significa el archivo entero en memoria—.

Entregué **el suelo que las cuatro necesitan**: `media_derivatives` y
`media_processing_jobs` con migración `f0a1b2c3d4e5` verificada en
`upgrade`/`downgrade`/`upgrade`, y `build_media_derivative_key` con áreas
`thumbnails`, `previews` y `transcodes`. La cola de evidencias **no** podía
alojarlos: su `evidence_id` es NOT NULL, y un recurso de la biblioteca no es
evidencia —justo la línea que dibuja ADR-055—.

**El detalle que evitó un fallo futuro:** el área del derivado se **valida** en
vez de sanearse. Sanear un área mal escrita crearía un directorio que ningún
listado sabe leer, y así es como un derivado acaba invisible en lugar de
equivocado.

**Lo que queda, y por qué en ese orden:** miniaturas es lo más cercano a cerrar y
**no necesita `ffmpeg`** (reutiliza Pillow, que ya genera miniaturas de 400 px para
evidencias). Duración y transcodificación necesitan `ffprobe`/`ffmpeg`. Archivos
grandes necesita el worker y un contrato de streaming.

**Y un agujero que conviene cerrar antes que nada:** `MediaUpdate.duration_seconds`
permite que el **cliente** escriba la duración, lo que contradice el comentario del
modelo («it stays null until it is measured»). Hoy es un dato que acepta cualquiera.

**Verificación.** **763 pruebas, 86,57 %**, `ruff` y `mypy` limpios en 158
archivos, migraciones en los tres sentidos.

## Errores corregidos y puerta de maquetación automatizada (2026-10-05)

**«Arregla todos los errores» lo acoté a lo que las puertas y eluso reportan**,
porque ClamAV y el destino de respaldo no son errores sino decisiones de
infraestructura, y decirlo es parte del trabajo.

**Errores reales corregidos, todos con prueba:**
- El CLI de migración a S3 construía **`--rekey` con claves falsas**: pasaba
  `document_id` como `case_id` y fijaba `.bin`. Escribía
  `cases/<doc>/documents/<doc>/v1-<hex>.bin`. Ahora la extensión sale de la clave
  almacenada y el token se deriva del identificador de la fila, con lo que la
  operación es **idempotente** (antes cada corrida acuñaba una clave nueva y
  multiplicaba objetos).
- **Devolvía 0 aunque migrara a medias.** En stdout, una ejecución silenciosa y
  una rota se ven igual. Ahora un ausente local, un digest discrepante o una
  escritura rechazada devuelven 4 y advierten que no se cambie `STORAGE_BACKEND`.
- `--offset` añadido: con `--limit` solo, repetir reprocesaba las mismas N filas
  para siempre.
- Un archivo local ausente se saltaba **en silencio**, sin aparecer en `errors`.
- `slowapi` era una dependencia **muerta**: declarada, nunca importada. Fuera.

**La puerta de maquetación, automática y con la prueba de que sirve.** Tres fallos
inmediatos en 320/390 px que resultaron ser **falsos positivos de mi propia
detección**: `scrollWidth` era igual al viewport, la página no se desplazaba. El
síntoma que se siente es «arrastrar la página», no «un hijo sobresale»; así que
el veredicto es `scrollWidth > clientWidth` y la lista de culpables queda solo
como explicación del fallo.

**Lo que la hace una puerta y no un adorno:** con `body { min-width: 200vw }`
inyectado, **falló**; revertido, pasó. Una comprobación que nunca ha fallado no
ha sido probada. Y sin `E2E_EMAIL`/`E2E_PASSWORD` **falla** en vez de saltarse,
porque saltarse dejaría verde una puerta que solo miró el formulario de acceso.

**Verificación.** **749 pruebas backend, 86,48 %**, `ruff` y `mypy` limpios en
156 archivos, 13 pruebas nuevas del CLI. Frontend: `tsc`, ESLint y build limpios,
y **56 comprobaciones de maquetación en verde** sobre once rutas y cuatro anchos.
La cuenta de pruebas y su contraseña se borraron al terminar.

## Limitador compartido sobre Redis: cerrado, con tres defectos que solo dio el servidor real (2026-10-05)

Puse los tres puntos de infraestructura delante y el estado era desigual: **S3
estaba casi listo**, **Redis no existía en absoluto** (ni servicio, ni
dependencia, ni ajuste; `slowapi` estaba declarada y sin usarse), y ClamAV tenía
un estado `EvidenceStatus.SCANNING` que se asigna y no escanea nada. Cerré
Redis, que es el único de los tres que se puede verificar aquí.

**Un almacén, no un `dict` dentro del middleware.** `services/rate_limit_store.py`
con `InMemoryRateLimitStore` (el comportamiento anterior, intacto) y
`RedisRateLimitStore`: ventana deslizante en un *sorted set* y un script Lua, en
una sola ida y atómico. Sorted set y no `INCR`+`EXPIRE` porque una ventana fija
admite el doble del presupuesto justo en la frontera.

**Las decisiones que importaban estaban en lo que pasa cuando Redis cae.** Ni
«sin límite» ni «negarlo todo» era honesto: la primera abre el freno de
`/auth/login` justo cuando alguien adivina contraseñas, la segunda convierte un
incidente de Redis en una caída del despacho. Se **cuenta en memoria** —un
presupuesto más débil, pero un presupuesto— con error registrado, y el criterio
contrario queda como configuración (`RATE_LIMIT_FAIL_CLOSED`).

**Las pruebas van contra un Redis real, y eso no fue opcional.** Un doble no
ejecuta Lua, no expira claves y no falla cuando el servidor no está: son
exactamente las tres cosas bajo prueba. Si no hay servidor, se saltan; no pasan
en verde.

**Tres defectos que encontró el servidor y que un doble no habría visto:**
- El *sorted set* usaba el **timestamp como miembro**: dos peticiones en el
  mismo milisegundo se reemplazaban y `ZCARD` se quedaba en 1. El limitador
  admitía una ráfaga ilimitada. Lo cazó **una** prueba: la que compara Redis con
  el almacén de memoria sobre una ráfaga.
- El middleware construía **dos** almacenes en memoria distintos, el que contaba
  y el que `reset()` limpiaba. El síntoma era «el limitador es demasiado
  estricto» en pruebas ajenas al limitador.
- `count >= limit` contando el golpe ya registrado admitía `limit - 1`: la mitad
  del presupuesto de autenticación, en silencio.

**Verificación.** **736 pruebas, 86,45 %**, `ruff` y `mypy` estricto limpios en
156 archivos. Sobre el stack en ejecución: tres envíos al formulario público
pasan y el cuarto da 429, y `ratelimit:contact:ip:172.24.0.1` está en Redis con
`ZCARD=4` y TTL de ~1 h. El conteo vive fuera del proceso.

**Lo que queda de los tres, y por qué:** **ClamAV** necesita dos decisiones de
la firma que no son mías —dónde se analiza y qué se hace con un positivo— y el
hueco de código está localizado. **S3 en producción** no es verificable aquí:
la imagen `minio/minio` da `pull access denied`, así que el camino S3 solo se ha
probado contra `moto` en proceso; además el CLI de migración solo mueve
`document_versions` y su `--rekey` está roto.

## Ensayo de restauración con la aplicación detenida (2026-10-05)

La memoria llevaba dos sesiones diciendo que este punto «requiere otro operador».
Revisé el procedimiento antes de aceptarlo, y **la mitad de esa frase era una
excusa**: los comandos sí se pueden ejecutar desde aquí. Lo que no se puede
simular es **quién** los ejecuta, y eso queda escrito como lo que es.

**Se hizo el ensayo de verdad, no una simulación.** Inventario previo: 9 usuarios,
5 clientes, 5 expedientes, 4 eventos, 3 documentos, 234 filas de auditoría,
revisión `e9f0a1b2c3d4`, 43 tablas, 21 archivos. Respaldo verificado. Después:
`backend`, `frontend` y `evidence-worker` **detenidos**; base borrada y **0 tablas**
antes de restaurar; `pg_restore`; almacenamiento **vaciado** y repuesto con 21
archivos; aplicación levantada.

**Resultado: los mismos números en las dos columnas.** 9|5|5|4|3|234, la misma
revisión, 43 tablas, 21 archivos. `verify_integrity --mode full` verificó **6 de 6
versiones documentales por digest**, 0 ausentes, 0 corruptas. Los 15 `orphaned`
son objetos de evidencias de pruebas anteriores: **ya estaban antes del ensayo**,
y aquí son la prueba de que el almacenamiento volvió tal cual. API `ready`,
frontend 200 y los 5 expedientes listados con sus clientes.

**El hallazgo del día no fue el ensayo: fue PowerShell.** El primer volcado salió
de **373 KB y `pg_restore` lo rechazó**. Repetido con `cmd /c`, el mismo comando
dio **184 KB y 357 entradas válidas**. PowerShell 5.1 corrompe la salida binaria
nativa, y el síntoma es el peor: el archivo existe, pesa más que el bueno y no
avisa. El digest lo detectó, que es justo lo que hace el paso previo.

**Lo que el ensayo NO cubre, y no se presenta como cerrado:** lo ejecutó el mismo
agente que escribió el sistema —un ensayo busca probar que *otra persona* puede
recuperar el servicio— y este host no tiene `bash`, así que `scripts/backup.sh`
siguió sin probarse entero: sus pasos se replicaron uno a uno.

## Destino del respaldo externo: decidido, y la regla pasó de prosa a control (2026-10-05)

Pediste continuar con el segundo punto que cuesta datos de `docs/DEPLOY.md`. Antes
de escribir nada comprobé el estado real: el mecanismo está completo y verificado
por digest, `--status` responde, y lo único que falta es una decisión de la firma.
Pregunté, porque el módulo entero existe para eso.

**La decisión es de la firma, no del código:** destino en un **bucket S3 de otro
proveedor**, con credenciales propias. La **inmutabilidad frente a un ransomware
que robe esas credenciales queda sin decidir**, y así se anota: es política, no
configuración, y no se da por supuesta.

**Lo que sí cerré fue un agujero real que apareció al mirar la restricción.**
`RESTORE.md` afirma desde hace meses que el destino no puede ser el bucket de los
documentos, con la razón correcta: uno de los dos borrados se lleva ambos. Eso
**no lo comprobaba nadie**. La configuración que más anula la función —copiar las
credenciales de `STORAGE_BACKEND` a `BACKUP_REMOTE_*`— pasaba sin protesta.

Se cerró con TDD. **Dos pruebas rojas por `DID NOT RAISE`**, que es la forma
bonita de decir «nadie lo comprobaba». La comprobación vive en
`from_settings`, antes de construir el cliente, y nombra el bucket en el error.
Dos detalles que importaron:

- **La barra final no puede decidir.** `https://host` y `https://host/` son el
  mismo servidor; hay una prueba que lo fija.
- **El caso legítimo también está escrito.** Un bucket distinto en el mismo
  servidor se acepta. Si el control lo cubriera, acabaría siendo un error al que
  se aprende a responder sin leer, y entonces no protegería nada.

Lo que **queda del lado del proveedor** está en `RESTORE.md`: crear el bucket en
otra cuenta con versionado, una credencial con permiso solo sobre ese bucket, los
valores de endpoint/región/estilo según el proveedor, y comprobar con `--status`.

**715 pruebas, 86,29 %, `ruff` y `mypy` estricto limpios en 154 archivos.**

## Cola administrativa de solicitudes (2026-10-05)

Se construyó `/admin/solicitudes` sobre la API ya existente. El módulo aparece
solo con `consultations:read`, lista las consultas públicas con filtro por estado
y paginación, y abre una ficha sin poner datos personales en la URL. La ficha
muestra contacto, consulta, consentimiento y atención; `consultations:update`
permite cambiar estado y notas mediante Server Action, y `consultations:erase`
expone un borrado físico separado, confirmado y descrito como una acción exclusiva
para una petición de supresión del titular.

No se amplió el proxy del navegador ni se duplicó información sensible en otro
historial. TypeScript, ESLint y el build de producción pasan. Sobre el stack Docker
se creó una solicitud pública, apareció en la cola, se abrió la ficha, se cambió a
«En revisión» con notas y fecha de atención, y se eliminó con la confirmación cuyo
foco inicial queda en «Cancelar». El flujo descubrió que el borrado dejaba el UUID
en la URL; la navegación pasó al Server Action y ahora termina en
`/admin/solicitudes`. A 390×844 no hay overflow ni ids duplicados, y la consola
queda limpia. Los datos de humo se eliminaron.

La regresión completa encontró un test de calendario que creaba tres eventos y
esperaba dos. Se corrigió el escenario para crear exactamente una reunión futura y
una audiencia; **711 pruebas pasan, 86,30 % de cobertura**, y Ruff queda limpio.

## Los objetos del respaldo, por fin verificados (2026-10-04)

Elegí este pendiente por un criterio, no por comodidad. `docs/DEPLOY.md` lista
tres puntos que **cuestan datos**, y dos no son míos: el destino externo en otra
máquina requiere un proveedor y el ensayo de restauración requiere otro
operador. El tercero —verificar el respaldo de objetos por digest y no por
recuento— sí se podía cerrar, y era el único.

**Lo que había era peor que un recuento inútil:** `objects.count` se escribía y
**nadie lo leía**, y `MANIFEST.sha256` —que sí tenía el digest de cada archivo—
tampoco lo leía nadie. El dato existía; la comprobación no.

**La demostración que lo cierra,** hecha sobre el contenedor y no solo en tests:
con dos archivos en el respaldo, truncar uno deja `archivos: 2` —el recuento
intacto— y produce `ALTERADOS: 1` y `resultado: FALLO`. Ese es exactamente el
fallo que el recuento no puede ver.

`app/services/backup_manifest.py` + `app/cli/verify_backup_files.py` releen cada
archivo y comparan el SHA-256, en trozos de 1 MiB porque un original puede pesar
cientos de megabytes. Distinguen **alterado**, **ausente** y **no listado**, y un
manifiesto vacío es fallo: no verifica nada y no puede avalar un respaldo. Las
rutas con `..` se rechazan. `backup.sh` lo ejecuta **antes** de enviar nada al
destino externo: subir un respaldo corrupto y descubrirlo después deja una copia
rota en el otro extremo que parece una copia de seguridad.

**Tres defectos que encontraron las pruebas que yo escribí,** no una revisión:
- El informe podía ser `healthy: False` **sin decir por qué**, y un archivo no
  listado invalidaba el respaldo pese a estar documentado como inocuo. Ahora el
  veredicto lo llevan los contadores y el vacío explica su fallo.
- `--json` imprimía también la línea humana final: la salida no era parseable.
  Eso es justo para lo que se pide JSON.
- **El manifiesto usaba el separador del sistema.** Se escribe en la máquina que respaldó y se lee en la que restaura; con `\` en
 Windows, un respaldo
  verificado desde Windows reportaba **todos los objetos ausentes**, que se lee
  exactamente como pérdida total. Ahora es POSIX y hay una prueba que lo fija.

**711 pruebas, 86,30 %, ruff y mypy limpios, cero avisos.** 20 de las pruebas son
de este módulo. `scripts/backup.sh` no se pudo ejecutar entero: este host no
tiene `bash` (WSL sin `/bin/bash`), así que verifiqué el comando exacto que
invoca, dentro del contenedor, contra un directorio montado.

## Cero errores y cero avisos (2026-10-04)

Pedido: «corrige todos los errores». Lo acoté a lo que las puertas del proyecto
reportan, porque ClamAV y Redis no son errores sino infraestructura por decidir,
y decirlo es parte del trabajo.

**Los 33 errores de SQLAlchemy 2.1 eran uno solo.** Eso fue lo importante. Antes
de reescribir nada pregunté al comprobador qué declara 2.1 para
`.scalars().all()` con `reveal_type`, y la respuesta fue `Sequence[Case]`, sin
error. Los errores de atributos de fila eran consecuencia, no causa: las
anotaciones `Select[tuple[Modelo]]` de los helpers de `dashboard.py` fijaban el
tipo de fila y todo lo demás se arrastraba. Con `Select[Any]` —que ya era la
convención del propio archivo en `_count` y `_rows`— y `Select[Any, Any]` para el
select de dos entidades, **`mypy` quedó limpio**. El teach: 33 errores contados
uno a uno son 33 veces el mismo trabajo inútil.

**Passlib fuera, sin dejar a nadie fuera.** Sustituido por `argon2-cffi`, que es
la librería a la que passlib delegaba, con los mismos parámetros. El riesgo no
es compilar: es que los hashes ya escritos en la base dejaran de validar y nadie
pudiera entrar. Eso se congeló como contrato —un hash de passlib guardado en
`test_password_hashing.py`, sin importar passlib— y se comprobó además con un
**login real** sobre una cuenta cuyo hash lo escribió passlib: 200. El test de
guardia que escribí para «el módulo ya no importa passlib» falló al principio
porque buscaba la palabra en el texto y la encontraba en la documentación que explica la
migración; se resolvió leyendo el AST.

**Un descuido mío, de nuevo en `pyproject.toml`.** Al añadir el comentario del
ceiling borré la línea `pytest>=8.4,<9` del extra `dev`. Lo detecté al releer el
archivo, no lo dijo ninguna puerta: sin `pytest` el gate de pruebas simplemente
no se ejecuta. Suma a la misma lección del incidente de `uvicorn`.

**Resultado, en instalación limpia:** SQLAlchemy 2.1.1, mypy 1.17.1,
ruff 0.12.12, argon2-cffi 25.1.0, passlib ausente de la imagen. `ruff` limpio,
`mypy` sin errores en 151 archivos, **691 pruebas, 86,05 % y ni una sección de
avisos**. La imagen reconstruida arranca y autentica.

Lo que queda abierto no es un error: falta ClamAV, Redis, el respaldo en otra
máquina y el ensayo de restauración. Y los 33 errores ya no están pendientes.

## Un corte de servicio que ningún gate vio (2026-10-04)

Al añadir los ceilings borré por accidente la dependencia `uvicorn[standard]` de
`pyproject.toml`. **La imagen se construyó, `ruff` pasó, `mypy` pasó y las 678
pruebas pasaron.** Nada en la suite importa uvicorn, así que el único que se dio
cuenta fue `docker compose up`:

```
exec: "uvicorn": executable file not found in $PATH
```

Es la forma de fallo que más cuesta: build verde, tests verdes, servicio muerto.
`test_packaging.py` lo convierte en puerta — lee el `CMD` del Dockerfile y
comprueba que ese binario esté declarado, y además que cada módulo de terceros
que la aplicación importa tenga su distribución en `dependencies`. El incidente
es la evidencia roja: la prueba falla si `uvicorn` desaparece.

## Cerrar sesión ahora revoca la sesión en el servidor

`signOut` solo borraba cookies. El comentario explicaba por qué no revocaba, y
la explicación era **falsa**: decía que la alternativa era un `beforeunload` que
los navegadores cancelan. Un Server Action es una petición que el servidor
espera antes de redirigir; no hay nada que cancelar. Mientras tanto, el token de
refresco vivía siete días en la base y una sesión «cerrada» seguía emitiendo
tokens.

Ahora `revokeSession()` en `lib/session.ts` llama a `POST /api/v1/auth/logout`
con ese token y **solo esa sesión** — cerrar un portátil no debe terminar el
trabajo del teléfono. Nunca bloquea el cierre: si la API no responde, las cookies
se borran igual.

**Verificación sobre el stack real, y una prueba que casi no vale nada.** Lo
primero que hice fue comprobar que el `revoked_at` de la fila pasara de nulo a
valor, y pasó. **Eso no probaba nada:** la rotación de tokens también escribe
`revoked_at` al gastarse, así que un 401 o una fila revocada son compatibles con
que la revocación no ocurriera. Lo decisivo fue `audit_logs`:
`POST /api/v1/auth/logout | success` en el instante exacto del clic. Y una
comprobación negativa que sí importa: de las tres sesiones del usuario, la
cerrada quedó revocada y **otra siguió activa**.

También apareció una falsa alarma: el navegador acabó autenticado de nuevo, con
un `jti` nuevo, y parecía una sesión resucitada. Los logs dijeron otra cosa: era
un `POST /auth/login` dos segundos después, no un `refresh`. La causa probable es
mi propia automatización, y **no se ha establecido**; queda anotado para no
reportar como defecto del producto lo que no se ha reproducido.

## Ceilings fijados, y dos afirmaciones que había que corregir (2026-10-04)

Al fijar los ceilings apareció un problema más serio que los ceilings: **los
gates no eran reproducibles**. El extra `dev` no declaraba `types-passlib` ni
`types-python-jose`, así que `mypy` solo pasaba en máquinas donde esos stubs ya
estaban instalados —en este host, por casualidad—. En un contenedor limpio
fallaban. Eso no es estilo: es un gate que depende del recuerdo de quien lo
instaló.

**La corrección que importa: mi afirmación anterior era falsa a medias.** Dije
que los gates estaban verdes. Lo estaban **con SQLAlchemy 2.0.43**, que es lo que
tenía el host. Docker resolvía 2.1.3 por el rango abierto `<3`, y contra 2.1.x
`mypy` da **33 errores en 5 archivos**. No lo había comprobado porque el comando
que ejecuté corría en el host. Un gate verificado en un entorno no es un gate
verificado.

**Y `mypy` refutó una afirmación mía.** Para `revoke_all_for_user` anoté el
resultado como `CursorResult[Any]`, razonando que un `UPDATE` devuelve eso. El
comprobador dijo que `execute` devuelve `Result[Any]` y que la anotación era
falsa. La opción fácil era un `cast`, que es exactamente lo que el aprendizaje de
esa misma sesión desaconseja. La correcta resultó ser mejor que las dos:
`UPDATE ... RETURNING id` y contar las filas. El número es tipado, exacto, y lo
dice PostgreSQL en vez del driver. Un test afirma el mensaje con texto exacto
(`«Se revocaron 1 sesiones activas»`), así que el cambio está verificado.

**Lo que quedó deliberadamente sin hacer.** No subí el techo a `<2.2`. Levantar
SQLAlchemy a 2.1 exige arreglar 33 errores de tipado en `dashboard.py` (29),
`security/__init__.py` y `api/deps.py`. Los de `dashboard.py` son los
interesantes: 2.1 tipa `select(Model)` como `Select[Model]` y declara que
`.scalars().all()` devuelve `Sequence[tuple[Model]]`, así que los atributos de
fila dejan de existir para el anotador. **Las 678 pruebas pasan en 2.1.x**: es un
problema de tipos, no de ejecución, y está enumerado archivo por archivo en
`NEXT_STEPS.md` para quien quiera pagarlo.

**Verificado en contenedor limpio:** SQLAlchemy 2.0.54, mypy 1.17.1, ruff
0.12.12. `ruff` limpio, `mypy` sin errores en 148 archivos y **678 pruebas con
85,96 % de cobertura**. El ruff instalado resolvió 0.12.12 en vez de 0.12.11 del
host, lo que confirma que un techo `<0.13` admite parches sin romper el gate.

## Gates de calidad restaurados (2026-10-04)

La memoria afirmaba que `ruff` y `mypy` no pasaban. Se revisó y se corrigió el
código, no las versiones. **Hoy los seis gates de `MASTER_PROMPT` sección 41
pasan**: `mypy` estricto sin errores en 148 archivos, `ruff` limpio, y
`pytest` con **678 pruebas y 85,98 % de cobertura**.

**Lo que mypy enseñó, más allá de los tipos.** Tres de los siete errores de
servicio eran el mismo error de diseño: `conditions` en facturación era
`list[object]`, y `else True` en dos consultas de IA. Ninguno fallaba en
ejecución —los cuatro gastricamente predijeron el mismo fallo— pero los tres
obligaban al anotador a mentir sobre lo que la lista realmente contiene. El
`cast` de `media_type_label` era el mismo caso: una afirmación de tipo que
tapaba una inferencia que mypy no podía verificar. La regla que sale de aquí:
**un `cast` o un `list[object]` es un punto ciego, y el anotador que obliga a
escribirlo está diciendo que el tipo se estrecha en algún sitio que nadie
escribió.**

En los tests eran 33 firmas de fixtures sin anotar. Había dos formas de
resolverlo y solo una es honesta: `Any` en todas, o el tipo real. Se puso el
tipo real, y al hacerlo apareció un bug de test real: `storage_key` es
`str | None` porque una fila registrada puede no tener archivo, y dos tests
lo pasaban a `exists()` sin narrowing. Esos tests pasaban por la razón
equivocada; ahora narrowean con `assert ... is not None`.

**Una corrección de memoria que importa.** La nota anterior atribuía siete
avisos `ASYNC240` a `backup.py` y `remote_backup.py`. Al ejecutarlo resultó
que **el Ruff instalado es 0.12.11** y esa regla no existe en esa versión:
nunca estuvo rota aquí, la nota describía otro entorno. No se corrigió nada en
esos dos archivos. La lección queda en `NEXT_STEPS.md` con el riesgo real, que
es que `ruff>=0.12,<1` permite instalar 0.16 y devolver el problema.

## Protección S3 al arrancar (2026-10-04)

Se cerró el bloqueo de versionado del bucket: cuando `STORAGE_BACKEND=s3`, el
lifespan comprueba que el bucket exista —o lo crea únicamente con
`S3_CREATE_BUCKET=true`— y exige habilitar versionado. Si cualquiera de esas
operaciones falla, la API no arranca y no acepta archivos con una protección
incompleta. Las 21 pruebas específicas de S3 pasan y Ruff está limpio en los
archivos modificados.

La regresión Docker descubrió un defecto ajeno al cambio: el resumen extractivo
sin consulta elegía por relevancia y también presentaba en ese orden, alterando la
secuencia del documento. Ahora selecciona las frases informativas y, cuando no
hay consulta, las devuelve en el orden original; con consulta conserva el orden
de relevancia. Resultado final: **678 pruebas pasan y 85,98 % de cobertura**.
Persisten solo avisos conocidos de Passlib, constantes HTTP deprecadas y el
producto cartesiano de dos pruebas del Dashboard. Mypy mantiene deuda
preexistente en billing, legal_ai y media.

## Worker continuo de evidencias (2026-10-04)

Compose incorpora `evidence-worker`, un proceso dedicado que ejecuta
`app.cli.evidence_worker --loop` cada 30 segundos, procesa hasta diez trabajos por
vuelta, comparte la base y el volumen de almacenamiento con la API y reinicia con
`unless-stopped`. No añade otro worker HTTP, por lo que no multiplica el estado
del rate limiter en memoria. `docker compose config` valida el servicio y el
contenedor quedó activo contra PostgreSQL. Ruff limpio y regresión final:
**678 pruebas, 85,98 % de cobertura**.

## Producto cartesiano del Dashboard eliminado (2026-10-04)

`_client_names` seleccionaba columnas de `cases` y `clients` sin unir las tablas;
PostgreSQL producía todas las combinaciones y SQLAlchemy emitía dos `SAWarning`
en cada regresión. La consulta usa ahora el `JOIN` por `Case.client_id`. Las 25
pruebas del Dashboard pasan con `SAWarning` convertido en error, Ruff está limpio
y la regresión completa mantiene **678 pruebas y 85,98 % de cobertura**, con los
avisos totales reducidos de 14 a 12.

## Centro multimedia, V4 construido (2026-10-04)

Anular la prohibición del brief se decidió en esta sesión: la dirección vio el
ADR-054 y dijo «contruirlo». Queda registrado en **ADR-055**, porque una
instrucción anulada que sigue escrita en el documento rector sin ninguna nota al
lado es una contradicción esperando a que alguien la lea.

**El alcance, que era la primera tarea pendiente de ADR-054:** una biblioteca
**interna** de la firma con vídeo, imagen, audio y PDF. Y una decisión que resultó
la más importante del módulo: **vídeo en la biblioteca, no en las evidencias.** La
sección 17 del encargo enumera los formatos del motor de evidencias y no incluye
`video/*`; abrir esa puerta es tocar el contrato de un registro jurídico. Así que
`EVIDENCE_MIME_TYPES` quedó intacto y el dominio nuevo no tiene inmutabilidad, ni
derivados, ni custodia, ni `legal_hold`. La ficha lo dice en pantalla para que
nadie confunda «material de trabajo» con «evidencia».

**Backend.** `MediaItem` y dos revisiones (tabla y siembra de los seis permisos
`media:*`). El tipo lo deciden los bytes: `kind` decide si el navegador ofrece un
`<video>`, así que se detecta por la cabecera y no se acepta del cliente, y hay una
prueba que archiva como vídeo un MP4 que se anuncia como imagen. `RIFF` se resuelve
por su tipo en el offset 8, porque es un contenedor. Registrar y subir son dos
llamadas porque un recurso puede existir sin archivo y eso es normal. `DELETE`
desactiva y **deja el archivo**, porque una fila sin sus bytes no se podría
reactivar. La API responde `206` con `Content-Range` para que un vídeo se pueda
buscar, y `416` cuando el rango no existe.

**Frontend.** `/admin/multimedia` con filtros por texto, tipo, confidencialidad y
estado; la ficha reproduce vídeo, audio e imagen por una ruta de streaming propia
(`/api/media/[id]`) en lugar del proxy compartido, que lee el cuerpo con `text()` y
aplana justo lo que un reproductor necesita por partes. `apiFetch` ahora deja pasar
un `FormData` intacto y **sin** `Content-Type`: el navegador tiene que escribir el
límite multipart y cualquier cabecera puesta aquí lo deja ilegible.

**Un fallo de seguridad propio, que la suite cazó.** Al añadir los permisos di
`media:delete` también al rol `abogado`, por un error al copiar la lista.
`test_operational_roles_cannot_delete` lo detectó inmediatamente; el primero que lo
vió fue un test de la suite, no una lectura. Y debajo había un segundo hecho: la
base de pruebas **persiste entre invocaciones** —`docker compose run --rm test`
reutiliza el contenedor `postgres-test`—, así que la migración ya había concedido
el permiso con el código defectuoso y `ON CONFLICT DO NOTHING` no lo revierte. La
corrección no surtió efecto hasta que se recreó `postgres-test`. Un arreglo de
permisos que no se verifica sobre una base limpia no está verificado.

**Un defecto visual que llevaba semanas.** La cabecera «Acciones» de los **siete**
listados llevaba `text-right` y ninguno la conseguía: `globals.css` va sin capas y
`.ledger thead th` le gana a la utilidad de Tailwind. Es el mismo mecanismo que ya
había costado dos bugs en esta hoja, y lo arreglé una vez en vez de siete.

**Verificación.** 637 pruebas de backend con 85,89 % de cobertura, incluidas
veinticuatro del módulo; `ruff` limpio en lo tocado. TypeScript, ESLint y build
limpios. En el navegador: alta con archivo, recurso registrado sin archivo, edición,
desactivación con el archivo conservado y reactivación con los bytes en su sitio;
los cuatro filtros; y **reproducción real**: un WAV de 1,5 s suena (`readyState: 4`)
y llegó como `206 Partial Content`, y el PNG se ve a 320×180 por la ruta
autenticada. 390×844 sin desbordamiento y con la ficha a todo el ancho. La base y el
almacenamiento quedaron como estaban, sin recursos de prueba.

## Módulos futuros: alcance decidido (2026-10-03)

Se pidió «continuar con el módulo de Multimedia». **No se construyó**, y la razón
es que `MASTER_PROMPT.md` lo prohíbe de forma explícita: lo lista bajo «Fases
futuras, NO implementar aún» (línea 35) y solo pide que «la arquitectura debe
quedar preparada para integrarlos posteriormente» (línea 38). En la hoja de ruta es
la fase **V4 — Vídeos y biblioteca** (línea 1504). Se dijo antes de escribir nada
y se acordó escribir el diseño, que es lo que el encargo pide de verdad.

**ADR-054 — se prepara el diseño, no se construye el módulo.** La preparación útil
no es un endpoint que devuelve 501 ni una tabla vacía: es saber qué se va a decidir
y con qué restricciones. El ADR deja escrito lo que ya existe y que V4 reutiliza
(niveles `StorageTier` con verificación por digest, motor de evidencias con
original inmutable y cola para archivos grandes, convención `recurso:acción`,
`change_logs`, desactivar en lugar de borrar), y lo que falta de verdad:

1. **No se acepta vídeo ni audio en ninguna parte.** `EVIDENCE_MIME_TYPES` es
   exactamente `application/pdf`, `image/png`, `image/jpeg`, y la sección 17 los
   enumera como los únicos. Ampliarlo es una decisión sobre el motor de evidencias.
2. **No hay transcodificación**: `evidence_processing.py` usa Pillow, no hay
   `ffmpeg`, y `app/workers/` está vacío salvo `.gitkeep`.
3. **No existe el concepto de biblioteca**: toda evidencia pertenece a un
   expediente con `case_scoped`. Una colección de la firma es otro alcance, y por
   ADR-045 eso impide un único `multimedia:read`.
4. **No hay modelo de dominio** ni ruta de descarga con `Range`.

Quedan escritas también las cinco decisiones que V4 tendrá que tomar (alcance,
formatos, derivados, retención, descarga) y, para cuando se autorice, cuál es la
primera tarea: **decidir el alcance, no escribir la tabla**.

**Lo único que se tocó en el código** es la ficha de los módulos inertes:
`admin-nav.ts` admite `future: {phase, scope}` y `modulo/[slug]` lo muestra. Los
tres —Multimedial V4, Facturación V3 e IA Jurídica V5— dicen ahora qué serán y qué
les falta, en vez de limitarse a declarar que no están. Sin backend, sin migración,
sin permisos: el menú sigue mostrando «Pronto» y no hay nada detrás del enlace.

## Configuración (2026-10-03)

Noveno y último módulo real de la administración. Con este, **la superficie de
administración está completa**: Dashboard, Clientes, Abogados, Expedientes,
Agenda, Mensajes, Documentos, Seguridad y Configuración. En el menú solo quedan
los tres módulos que `MASTER_PROMPT.md` prohíbe construir, inactivos con su motivo.
`/admin/modulo/config` da 404 ahora con la página de «no existe» del propio
proyecto, porque un módulo `ready` no debe abrir la pantalla de «en construcción».

**Frontend.** `system_settings` agrupada por categoría, con una hoja por bloque
que lleva clave, valor, tipo y momento del último cambio. Alta y edición en
diálogo, y una búsqueda que cubre clave, categoría, descripción y valor: si una
palabra aparece en la pantalla, tiene que encontrar su fila.

El valor se edita **como el texto que se guarda**, no como el valor decodificado, y
una columna «tipo» dice con qué se relee. No es un detalle de forma: `30` y `"30"`
son los mismos bytes en esta tabla y solo uno es un número para quien lo lea
después.

**El borrado es la excepción, y la pantalla lo dice.** En el resto de la
administración una fila se desactiva o se archiva porque es un registro jurídico.
Un ajuste del sistema no lo es —no guarda expedientes, evidencias ni firmas— y el
backend ya lo borra dejando el valor anterior en `change_logs`. La comprobación se
hizo en la base, no confiando en la frase: `value` y `category` quedan anotados
con `change_reason = "Ajuste eliminado"` y actor. El botón de confirmación no toma
el foco inicial.

**Dos defectos reales, ambos de los que solo aparecen usándola.**

1. **La segunda escritura de una clave devolvía 500.** `updated_at` es
   `onupdate=func.now()`, una expresión SQL que el ORM no puede calcular: tras un
   UPDATE el atributo queda expirado, y el router serializa la respuesta desde una
   función normal, fuera del greenlet, así que la carga perezosa saltaba en el
   sitio equivocado (`MissingGreenlet`). El alta funcionaba porque un INSERT
   devuelve sus columnas: **son dos rutas y solo se probaba una**. `settings.py`
   era el único servicio mutante sin `refresh()`, que es el patrón de la casa en
   treinta y tantos sitios. La prueba nueva escribe la misma clave dos veces; se
   comprobó que falla al quitar el `refresh`.
2. **El navegador centraba la primera columna de los ocho listados.**
   `<th scope="row">` es un `th`, y la hoja del navegador centra todos los `th`;
   la regla del proyecto solo corregía `thead`. En columnas estrechas pasaba
   desapercibido y en una columna ancha con descripción era evidente. Se corrigió
   una vez en `globals.css` y se verificaron los ocho listados.

También se corrigió el formulario de filtros, que se mostraba sobre una tabla
vacía, y la etiqueta «Última lectura», que mentía: `updated_at` es la última
escritura.

**Verificación.** 613 pruebas de backend con 85,75 % de cobertura y `ruff` limpio
en lo tocado. TypeScript, ESLint y build limpios, con `/admin/configuracion` en la
lista de rutas. En el navegador: alta, edición, borrado y los cuatro rechazos del
backend (credencial, clave inválida, mayúsculas, no ASCII) comprobados contra la
base de datos; búsqueda y filtro por categoría; estados vacíos; 390×844 sin
desbordamiento, con el diálogo a 342 px, desplazable y cerrable con Escape. La
base quedó como estaba: sin ajustes, porque las migraciones no siembran ninguno y
**ninguna clave se lee todavía en producción** (`get_value` solo aparece en las
pruebas), así que los valores inventados no habrían tenido efecto pero tampoco
tenían por qué quedarse.

## Seguridad (2026-10-03)

Se cerró el quinto módulo de administración. `/admin/seguridad` son tres vistas
gobernadas por `?vista=usuarios|roles|auditoria`, cada una con su propio permiso
(`users:read`, `roles:read`, `audit_logs:read`), y la entrada del menú pasó a
`ready` con `users:read`.

**Backend.** `GET /admin/users` acepta `search`, `role` e `is_active`; se añadió
`GET /admin/users/{id}`, que evita derivar la ficha de la lista, y
`GET /admin/audit-logs` devuelve `{items, total, skip, limit}` con `search`,
`user_id` y `result`, donde cada entrada lleva `user_email` para que el rastro
nombre a una persona y no un identificador.

**Frontend.** Directorio con alta y edición en diálogo, diálogo de roles que
calcula el lado servidor la diferencia contra lo que el servidor tiene, desactivación
con confirmación y reactivación como acción propia. Vista de roles con los cuatro
roles y los permisos que concede cada uno, más el catálogo completo agrupado por
recurso. Auditoría con paginación y filtros que navegan por URL.

**Tres defectos reales, los tres encontrados usando la pantalla.** Ninguno habría
salido de las pruebas:

1. **`admin.py` no confirmaba nada.** Los cinco endpoints de escritura llamaban a
   `flush` y respondían 2xx, pero `get_session` cierra la transacción sin
   `commit`: la cuenta se creaba, se anunciaba y desaparecía. Era el único router
   de escritura del proyecto sin un solo `commit`. Las 611 pruebas pasaban porque la
   fixture comparte una sesión y un SAVEPOINT entre la petición y la aserción, y una
   fila sin confirmar es visible ahí. La prueba nueva cuenta los `commit` en lugar de
   leer el dato de vuelta; se comprobó que **falla** al quitar las confirmaciones.
2. **El diff de roles estaba invertido**: `toAdd` y `toRemove` intercambiados, de
   modo que se asignaba el rol desmarcado y se retiraba el marcado. Con cuatro
   llamadas 200 y la tabla sin cambios, parecía un no-op.
3. **`deactivateUser` y `reactivateUser` no revalidaban.** La base se actualizaba y
   el ledger seguía mostrando `ACTIVO`, es decir, la pantalla mentía.

También se corrigió un 500 del directorio: `UserBase.email: EmailStr` revalidaba la
dirección al serializar y una fila con `.local` tumbaba la respuesta entera. Ahora la
entrada valida (`UserCreate.email: EmailStr`) y la salida lee (`str`), y el CLI
`create_admin` valida `ADMIN_EMAIL` como la API.

**Verificación.** 612 pruebas de backend con 85,74 % de cobertura; `ruff check`
limpio en los dos archivos tocados (quedan diez hallazgos preexistentes en otros
módulos). `tsc --noEmit`, ESLint y `next build` limpios. En el navegador: alta, edición,
cambio de roles, desactivación y reactivación comprobadas **contra la base de datos**,
no contra la pantalla; los cuatro filtros de cada vista; paginación; estados vacíos;
390×844 sin desbordamiento horizontal en las tres vistas. El único error de consola
sigue siendo la hidratación preexistente del `<html className>`.

## Documentos (continuación del 2026-10-03)

Se cerró el cuarto módulo de administración. `/admin/documentos` es ahora un
archivo global de la firma: antes los documentos solo existían dentro de un
expediente y no había forma de recorrerlos.

**Backend.** `GET /api/v1/documents` devuelve `{items, total, skip, limit}` sobre
un helper compartido `_base_filters` que reutiliza `case_scoped(scope_filter(...))`
— el mismo mecanismo que `list_cases`, porque sin él la lista cruza `documents`
con `cases` y filtra mal. Añade tipo, estado, confidencialidad, visibilidad,
`legal_hold` y búsqueda sobre título, descripción y número/título del expediente.
La visibilidad no ensancha el alcance: para quien no tiene permiso de documentos,
`visible_visibilities()` devuelve vacío y el filtro es `func.false()`, no «todo».
Ocho pruebas nuevas, entre ellas una que demuestra que el filtro de visibilidad no
puede ampliar el acceso y otra que rechaza una página fuera de rango.

**Frontend.** Listado con formulario de filtros, chips de estado/tipo/
confidencialidad, filete de estado por fila (anulado y reemplazado en gris,
`legal_hold` con el suyo), paginación y estado vacío que explica el filtro y no la
base de datos. La ficha abre en un cajón lateral con el historial de versiones,
su hash y el enlace de descarga tras `documents:download`. No hay borrar: el
documento acaba en `anulado` y la versión en ser reemplazada. El menú pasó a
`ready` con `documents:read`.

**Un defecto real encontrado usándolo.** El cajón abría como una tira del alto de
una fila en lugar de cubrir la pantalla. La fila lleva la animación `row-enter` y
**un elemento con `transform` es el bloque contenedor de sus descendientes fijos**
— el `inset: 0` se resolvía contra la celda, no contra la ventana. Se corrigió con
`createPortal` hacia `body`, que es cuando apareció el segundo: `body > * { position:
relative; z-index: 1 }` de `globals.css` anulaba el `fixed` de la utilidad de
Tailwind porque esta hoja es **sin capas** y las utilidades de Tailwind no. El
cajón se quedaba abajo del todo, en flujo. Solución: `body > .viewport-overlay`,
una regla sin capa que le devuelve `position: fixed; inset: 0; z-index: 50`.

**Verificación.** 606 pruebas de backend con 85,63 % de cobertura (objetivo ≥ 80 %).
`tsc --noEmit`, ESLint y `next build` limpios, con `/admin/documentos` en la lista de
rutas. Sobre el stack en ejecución: 401 sin sesión, 422 con `limit=500`, 200 con
los filtros y la forma esperada; en el navegador, el cajón cubre 1440×900 con el
panel a 576 px y 390×844 a todo el ancho, Escape lo cierra y el fondo lo cierra
también, los filtros navegan por URL y el limpiar muestra el estado vacío. El único
error de consola es la hidratación preexistente del `<html className>` de la raíz,
que también aparece en `/admin/expedientes`.

## Objetivo trabajado
Portal privado de administración con CRUD real por módulo. En la continuación del
2026-10-03 se cerró **Mensajes administrativos**: bandeja personal del despacho,
filtros y métricas, creación de conversaciones internas o de cliente, lectura,
respuesta, adjuntos, archivado lógico de mensajes propios y cierre confirmado.
La pantalla respeta la regla de confidencialidad: ni siquiera un administrador ve
hilos en los que no participa.

Al abrir un hilo, su indicador de no leído se limpia localmente; al enviar, la fila
se actualiza sin esperar otra navegación. Los adjuntos informan máximo de 5 y 10 MB
por archivo, filtran extensiones admitidas y validan cantidad y tamaño antes de
subir, sin sustituir la validación del backend. El cierre dejó de ejecutarse con un
clic directo y exige una confirmación que explica que nada se borra.

`tsc --noEmit`, ESLint y `next build` quedaron limpios. No se pudo realizar la
prueba HTTP ni visual porque Docker Desktop no estaba activo.

Portal privado de administración con CRUD real por módulo. En esta sesión se
cerraron **Expedientes** y **Agenda y audiencias**, se completó el CRUD desde los
listados, se revisó la interfaz de administración y se sustituyó la tira
horizontal de módulos en móvil por un botón hamburguesa.

El 2026-10-03 se refinó además la columna de acciones de los tres listados: Editar,
Cerrar y Desactivar tienen ahora iconos SVG lineales de una misma familia, texto
visible y controles de altura coherente. Las altas y las confirmaciones reutilizan
el mismo lenguaje. Se comprobó en 320, 390, 768 y 1440 px: cero desbordamiento de
página, cero ids duplicados y cero errores de consola.

También se entregó `/admin/agenda`: Día/Semana/Mes, navegación, filtros,
cronología, métricas, vencimientos, eventos y ciclo de audiencias. Antes de
exponerla se cerraron cuatro brechas: permiso y alcance al listar audiencias,
validación de abogado activo y expediente, y bloqueo de creación o edición de
audiencias por el calendario genérico.

El ciclo real creó y editó un evento, creó y reprogramó una audiencia, rechazó
resultado vacío y solapamiento, y la marcó realizada. Esta prueba descubrió que
el contenedor mostraba UTC; entrada y salida quedaron fijadas a
`America/Bogota`, y 11:00 vuelve a leerse como 11:00.

## Qué se construyó

**Expedientes**, el módulo central:

- Listado con búsqueda y filtros por estado, proceso y prioridad.
- Alta en diálogo: cliente, tipo de proceso, responsable, área, prioridad,
  juzgado, número de proceso, jurisdicción, cuantía, descripción y notas.
- **Ficha 360** sobre `GET /cases/{id}/360`, con el recuento de actuaciones,
  agenda, audiencias, documentos y evidencias, y la advertencia de que las cifras
  son de lectura: el detalle se abre en su propio módulo.
- **Cierre** con fecha y nota, y un diálogo que explica que cerrar no borra.
- Incorporación de abogado con su papel, y alta de parte.

## CRUD completo en los listados

La única acción de cada fila era «Abrir →»: editar y cambiar el estado solo se
alcanzaban entrando en la ficha, así que desde la lista los tres módulos parecían
de solo lectura. Ahora cada fila ofrece **Editar** siempre, **Cerrar** en
expedientes abiertos y **Desactivar** en clientes y abogados activos. Un registro
ya cerrado o inactivo solo ofrece editar.

**Decisión de la firma sobre eliminar**: pidió CRUD completo con eliminación y
`PROJECT_RULES.md` regla 5 lo prohíbe. Preguntado, eligió **desactivar /
archivar**. No hay botón de borrar; el `DELETE` del backend en clientes y abogados
ya es desactivación lógica. Consecuencia visible: un cliente desactivado desaparece
del listado por defecto y solo aparece con «incluir inactivos», y un expediente
cerrado no se puede reabrir desde la interfaz porque la API tampoco lo permite.
Queda en ADR-051.

## Revisión visual

La paleta no se tocó: papel, tinta, lacre y latón ya eran la identidad del portal
privado. El trabajo fue de jerarquía.

- **Regla de estado por fila**, en el borde izquierdo: verde bosque lo que está
  vivo, latón lo suspendido, lacre lo urgente, gris plano lo cerrado. Antes había
  que leer cada fila para saber cuáles requieren atención.
- **Una sola píldora por fila**: el estado la lleva; la prioridad es un punto de
  color. Dos píldoras en la misma fila son dos gritos.
- Cabecera con filete de latón, título más presente y descripción más corta.
- Las tarjetas KPI distinguen volumen de trabajo pendiente, y los paneles
  inferiores del Dashboard van encerrados en tarjeta. El rojo de vencimientos solo
  aparece cuando hay algo vencido.
- Las notas de sistema llevan filete de latón: explican por qué no hay botón de
  borrar, que si no parece un descuido.
- Sombras cálidas y sutiles, lupa en el buscador, botones `quiet` en la fila y
  entrada escalonada con tope de ocho filas.

## Botón hamburguesa en móvil

La tira horizontal de fichas era honesta pero estaba mal: había que desplazarla
para saber qué existía, empujaba el contenido de todas las pantallas con una barra
que nadie pidió, y filtraba los tres módulos «Pronto» justamente por no tener
`href`. El panel nuevo tiene la misma arquitectura que el raíl de escritorio: los
doce módulos con su motivo cuando están inertes, y el pie con la persona, su rol y
las dos salidas, que en móvil no existían.

Cumple lo que cuesta más que el botón: es un `<button>` real con `aria-expanded`
y `aria-controls`, el panel se desmonta al cerrarse, Escape cierra y devuelve el
foco, al abrir el foco entra y el fondo deja de desplazarse, y se cierra solo al
navegar. La barra baja de 130 px a 65 px.

## Cinco defectos reales encontrados usándolo

1. **Expedientes no aparecía en el menú para nadie.** El módulo exigía
   `cases:read`, un permiso que el proyecto no tiene: expedientes se autoriza por
   alcance (`read_all`, `read_assigned`, `read_published`). Un permiso inventado no
   restringe, esconde. ADR-052.
2. **Tras guardar, el formulario contradecía a la página.** El chip decía
   «Prioridad urgente» y el desplegable «Alta». React no toca el valor de un
   `<select>` no controlado tras un Server Action; los campos de texto solo
   parecían bien porque el usuario acababa de escribirlos. Los formularios se
   remontan ahora con `updated_at`.
3. **IDs duplicados en el DOM.** La ficha monta el formulario y tres diálogos y
   `notes` y `client_id` se repetían; en los listados, los filtros compartían id
   con el diálogo de alta. No rompe nada visible: hace que cada `<label
   htmlFor>` enfoque el control equivocado. `FormField` admite ahora `idPrefix`.
   Y el arreglo posterior **reintrodujo el mismo defecto** al montar el diálogo de
   cierre una vez por expediente abierto: por eso la comprobación es una puerta.
4. **La regla de estado por fila no se pintaba.** Es `background-image` y no
   `box-shadow` porque la tabla es `border-collapse: collapse`, y ahí una celda
   deja de pintar su sombra aunque el estilo calculado diga que está.
5. **El dashboard aparecía resaltado en todas las pantallas.** El ítem activo se
   calcula por prefijo para que `/admin/clientes` siga encendido en
   `/admin/clientes/8f3c…`, pero la ruta del dashboard es `/admin` y toda pantalla
   empieza por `/admin/`. El índice se trata ahora como caso exacto.

También se corrigió el texto del encabezado de un expediente cerrado, que
prometía «se conserva íntegro» mientras ofrecía un formulario editable: el backend
sí permite corregir un cerrado y todo queda auditado, así que el que mentía era el
texto. Y `.row-title` / `.row-meta` estaban anidadas bajo `.ledger`, por lo que no
aplicaban en el Dashboard y los números de expediente salían en la fuente
equivocada, partiéndose en dos líneas.

## Verificación

- **Cierre desde la fila**: `WA-2026-000003` pasó a «Cerrado» y su botón desapareció
  en el sitio, sin recargar.
- **Desactivación desde la fila**: un cliente de humo confirmó «Inactivo» con
  «incluir inactivos».
- La desactivación de abogado se comprobó abriendo el diálogo y cancelando, sin
  confirmar: confirmarla habría dejado a la firma con un solo abogado activo. El
  camino de confirmación es el mismo componente que en clientes.
- Cero IDs duplicados, cero desbordamiento horizontal y cero errores de consola en
  las siete pantallas de administración, en 320, 390, 768 y 1440 px.
- `tsc --noEmit`, `eslint` y `next build` limpios.
- 590 pruebas del backend pasan, 85,72 % de cobertura.
- Las 36 pruebas específicas de calendario pasaron antes de la regresión total.
- Agenda: cero ids duplicados y cero desbordamiento en 320, 390, 768 y 1440 px;
  foco dentro del diálogo, Escape cierra y cero errores de consola.
- `tsc --noEmit`, ESLint y build de producción limpios después de fijar la zona.

## Datos de prueba en la base de desarrollo

Quedan, sin borrar porque son registros jurídicos:

- `WA-2026-000005` «Prueba de interfaz admin» y `WA-2026-000003`, ambos
  **cerrados**; el primero con un colaborador y una parte externa.
- Tres clientes de prueba **desactivados** y un abogado de prueba inactivo.
- Evento `Revisión de agenda completada` y audiencia `Audiencia de conciliación
  administrativa`, realizada tras una reprogramación y conservada como registro
  jurídico de la verificación.

## Un 500 que no era un bug

Al incorporar abogado apareció un 500 con `MissingGreenlet` en el `pre_ping` del
pool: era una conexión obsoleta tras el `--force-recreate` de los contenedores. El
mismo clic funcionó a la segunda. Queda como aprendizaje: un 500 único e inmediato
a un `recreate` se lee en el dialecto y el pool antes que en el endpoint.

---

# Sesión anterior

## Objetivo trabajado
Web pública de WABOGADOS, con `WABOGADOS_web.html` como referencia visual, y en
la segunda parte de la sesión: rellenar la identidad real de la firma con los
recursos de `WABOGADOS_recursos` y `wabogados.co`.

## Qué se construyó

La portada pasa a ser la web pública, con el orden de secciones de la
referencia: hero («Su tranquilidad. Nuestra mejor defensa.»), banda de
confianza, áreas de práctica, la firma, el portal de clientes, equipo,
actualidad jurídica, contacto y pie.

- **Paleta corporativa** del HTML de referencia: azul petróleo `#132c35`, dorado
  `#b28b55`, marfil `#f7f5f0`. Vive **aparte** de la del portal privado, y en la
  especificación se explica por qué: son dos audiencias, no un descuido.
- **Tipografía compartida**: Fraunces e IBM Plex Sans, que la aplicación ya
  carga. Sin descargas nuevas.
- **Ilustración de columnas y balanza** en SVG en línea, con los `id` prefijados
  para no colisionar.
- Menú móvil accesible, diálogo nativo con devolución del foco, formulario con
  estados.
- La página de estado pasa a `/estado`.
- **Acceso por rol**: cliente a `/portal`, personal a `/expedientes`, decidido
  por permisos.

## Decisiones

- «Portal privado» enlaza al acceso real, no a la maqueta del diseño de
  referencia. La plataforma existe.
- **No se inventa nada**: sin abogados, fotografías, direcciones, teléfonos,
  trayectorias ni credenciales. Cada hueco lleva la marca «Pendiente».
- Los artículos se identifican como contenidos de ejemplo en la tarjeta, en el
  diálogo y en la nota.
- **El formulario declara que no envía.** No existe endpoint de contacto, y el
  estado que muestra describe lo que realmente ocurrió.

## Problemas encontrados

- **El botón «Portal privado» era invisible.** `.site-nav-links > a` tiene
  especificidad (0,1,1) y gana a `.site-btn` (0,1,0), así que el enlace heredó
  texto petróleo sobre fondo petróleo. En la referencia era un `<button>` y
  nunca casaba con la regla. Corregido en la regla con `a:not(.site-btn)`, no
  en el botón.

## Verificación

En escritorio (1440) y móvil (390), sobre la aplicación en ejecución:

- `tsc --noEmit`, `eslint` y `next build` sin avisos.
- `/`, `/login`, `/estado` y una ruta inexistente responden.
- **Sin desbordamiento horizontal** en ninguno de los dos anchos.
- Botón legible: blanco sobre petróleo.
- Menú móvil con `aria-expanded` correcto.
- Diálogo: abre, cierra con `Escape` y **devuelve el foco** al botón de origen.
- Acceso por rol comprobado con dos cuentas reales.
- «Portal privado» conduce a `/login`.
- **El lienzo público ocupa todo el ancho del viewport.** `.site-canvas` mide
  exactamente el ancho en 390, 1280, 1440 y 1920 px, y el desbordamiento
  horizontal es cero. El portal privado conserva su propio papel y **no**
  monta el lienzo.
- Con la identidad real: sin desbordamiento horizontal en 390, 768 y 1440, sin
  imágenes rotas, las tres fotografías y las dos marcas cargadas, y las dos
  placas de aliado a la misma altura.
- **El sitio corre en Docker**, no en `next dev`. Un cambio de frontend no se ve
  hasta `docker compose up -d --build --force-recreate frontend`; con `--build`
  a secas el contenedor se declara «Running» y **no** se recrea, así que sigue
  sirviendo la imagen anterior.
- **El formulario envía de verdad**, comprobado contra el contenedor desplegado:
  201 con referencia y fila creada, lectura sin credenciales → 401, rol cliente →
  403, `PATCH` escribe `handled_by` y `handled_at`, `DELETE` → 204 y la fila
  desaparece, y `audit_logs` registra el POST anónimo sin ningún dato personal.
  En el navegador: tres envíos aceptados y el cuarto rechazado por el freno.
- 584 pruebas pasan con 85,66 % de cobertura. Ruff limpio.

## La identidad real

`WABOGADOS_recursos` traía las URL de los originales, y la descarga binaria
**sí funciona** desde este entorno (el README del paquete decía lo contrario).
Se recuperaron los cinco archivos y, para el equipo, se pidió la versión sin
sufijo de tamaño, que es el original más grande.

Lo publicado en la web viene verificado en `wabogados.co/team`: tres
profesionales con nombre, cargo y fotografía; siete áreas con la redacción de la
firma; dirección, teléfono y horario; la cita de Santander; y las dos marcas de
aliados.

Lo que se dejó fuera a propósito: el correo (protegido por Cloudflare, no está
en el código fuente), los testimonios del sitio —son relleno de demostración
del tema, hablan de diseño web y de derechos de autor—, y el precio de la
consulta, que es un compromiso comercial.

## Pendientes

- **Aviso de privacidad**: redactado y declarado pendiente en la propia página,
  pero falta que el despacho lo revise y apruebe. Faltan la razón social completa
  y el canal para ejercer los derechos.
- **Interfaz de la cola de solicitudes**: el backend la expone, no hay pantalla.
- **Confirmación por correo**: no hay servicio de correo ni dirección de la firma.
- **Correo electrónico de la firma**: lo publica protegido por Cloudflare y no
  se puede leer del código fuente. No se escribe uno plausible.
- Textos legales de privacidad y términos.
- Contenido editorial aprobado.
- Recurso institucional aprobado para la ilustración.

## Un hallazgo que hay que reportar

**`ruff` y `mypy` no están limpios, y el registro anterior decía que sí.** No es
culpa de ningún cambio de esta sesión: los rangos de `pyproject.toml` permiten
versiones que añadieron reglas y endurecieron tipos.

- `ruff` 0.16.10 trae `ASYNC240`, una regla nueva: 7 avisos en `backup.py`,
  `remote_backup.py` y `test_documents.py`.
- `sqlalchemy` 2.1.1 endureció el tipado de `select(Model)` y **mypy estricto
  falla con 42 errores en 11 archivos**.

Ningún archivo afectado es nuevo. Hay que fijar versiones y adaptar el código.
Queda en `NEXT_STEPS.md`. `pytest` sí pasa: 586 pruebas, 85,68 %.
