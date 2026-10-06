# CHANGELOG

## [Unreleased] - 2026-10-05
### Added
- **V3 Facturación y V5 IA Jurídica: verificados funcionando** (2026-10-05).
  No estaban bloqueados: ambos tienen backend, permisos sembrados, migraciones y
  pantalla. La memoria que los daba por inertes era **obsoleta** y se había
  propagado a `NEXT_STEPS` y `project_context`. Lo único realmente pendiente de IA
  Jurídica es la generación asistida, y la propia pantalla lo dice en voz alta.
- **Base del pipeline multimedia** (ADR-055), que es el suelo que necesitan las
  cuatro capacidades que faltan:
  - `media_derivatives` y `media_processing_jobs` con la migración
    `f0a1b2c3d4e5`, `upgrade`/`downgrade` verificados.
    `EvidenceProcessingJob` **no** podía alojarlos: su `evidence_id` es NOT NULL
    y un recurso de la biblioteca no es evidencia, que es exactamente la línea que
    ADR-055 dibuja.
  - `build_media_derivative_key` con áreas `thumbnails`, `previews` y
    `transcodes`. El área se **valida** en vez de sanearse: un error tipográfico
    crearía un directorio que ningún listado sabe leer, que es como un derivado
    acaba invisible en vez de equivocado. Un derivado nunca comparte directorio
    con su original.
  - 14 pruebas que fijan el comportamiento, incluido que borrar el recurso borra
    sus derivados y sus trabajos.
- **Puerta automática de maquetación del frontend** (`npm run test:e2e`), que
  era una tarea manual desde hacía semanas y había detectado tres fallos reales:
  - **Ids duplicados** leídos del DOM, no del código. Un id repetido no lanza
    error: la página se ve perfecta y el clic en la etiqueta no hace nada.
  - **Desbordamiento horizontal** en 320, 390, 768 y 1440 px sobre las once rutas
    de administración.
  - El veredicto es `scrollWidth > clientWidth`, que es lo que se siente. La
    primera versión enumeraba elementos que sobresalen y daba **falsos
    positivos**: una tarjeta cuyos hijos son más anchos que la pantalla mientras
    la página no se desplaza no es desbordamiento. El diagnóstico queda solo en
    el mensaje de fallo.
  - `e2e/auth.setup.ts` inicia sesión con `E2E_EMAIL`/`E2E_PASSWORD` y **falla**
    si faltan, en vez de saltarse: una puerta que inspecciona el formulario de
    acceso informa verde sin haber comprobado nada.
  - **Probada en ambos sentidos**: con una sonda `body { min-width: 200vw }`
    falla, y sin ella pasa. Una puerta que nunca falla no es una puerta.
- **El limitador de peticiones cuenta en un almacén compartido (ADR-008).**
  `REDIS_URL` selecciona un contador Redis; sin él sigue el de memoria, que solo
  es correcto con un proceso.
  - `app/services/rate_limit_store.py`: `InMemoryRateLimitStore` (el
    comportamiento anterior) y `RedisRateLimitStore`, con ventana deslizante en
    un *sorted set* y un script Lua. Un conjunto ordenado y no `INCR`+`EXPIRE`
    porque una ventana fija admite el doble del presupuesto en la frontera.
  - **Si el almacén falla se cuenta en memoria y se registra un error**, no se
    abre el límite: un Redis caído no puede convertirse en un presupuesto de
    login ilimitado. `RATE_LIMIT_FAIL_CLOSED=true` invierte la decisión y lo
    niega todo.
  - `redis` y servicios `redis` / `redis-test` en Compose. Sin persistencia a
    propósito: son marcas de tiempo, no datos, y un almacén vacío tras un
    reinicio es el estado correcto.
- 21 pruebas del almacén, **contra un Redis real**: un doble no ejecutaría el
  Lua, no expiraría claves y no fallaría cuando el servidor no está, que son
  justo las tres cosas bajo prueba. Se saltan, no pasan en verde, si no hay
  servidor.
- **Ensayo de restauración completa con la aplicación detenida.** Documentado en
  `docs/RESTORE.md` §9: inventario previo, respaldo verificado, `backend`,
  `frontend` y `evidence-worker` detenidos, base borrada (0 tablas), `pg_restore`,
  almacenamiento vaciado y repuesto. Los recuentos coinciden antes y después
  (9|5|5|4|3|234, revisión `e9f0a1b2c3d4`, 43 tablas, 21 archivos) y
  `verify_integrity --mode full` verifica 6 de 6 versiones por digest, 0 ausentes
  y 0 corruptas.
- **El destino del respaldo externo no puede ser el bucket de los documentos.**
  `RESTORE.md` lo exigía desde que existe el módulo, pero solo en prosa: la
  configuración que más anula la copia se aceptaba sin protestar. Ahora
  `RemoteBackup.from_settings` la rechaza nombrando el bucket, y normaliza el
  endpoint para que una barra final no desactive el control. Un bucket distinto en
  el mismo servidor sigue aceptándose.
- Cuatro pruebas que fijan el comportamiento, incluido el caso legítimo que no
  debe confundirse con el prohibido.
- Decisión de la firma registrada: destino en un bucket S3 de otro proveedor.
  Inmutabilidad (Object Lock) **sin decidir**, anotada como pendiente de política.
- `/admin/solicitudes`, cola interna de consultas enviadas desde la web pública:
  filtro por estado, paginación, ficha completa, actualización de estado y notas,
  y borrado físico confirmado solo con `consultations:erase`.
- Entrada de navegación protegida por `consultations:read` y Server Actions para
  mantener las credenciales fuera del navegador.

### Fixed
- **IDOR en documentos: el camino por identificador no comprobaba el expediente.**
  Hallazgo de la auditoría del 2026-10-05. `browse_documents` filtraba por alcance
  de expediente y `get_visible_document` no: solo miraba `visibility`, que depende
  únicamente de permisos. Un abogado sin expedientes asignados veía un listado
  vacío y aun así podía **leer, editar, ampliar y descargar** cualquier documento
  de la firma adivinando el UUID; un cliente podía leer todo documento `publicada`
  de todos los clientes. Cinco endpoints afectados.
  - `get_visible_document` recibe ahora `scope_clause` como **argumento
    obligatorio sin valor por defecto**: con un `None` por defecto, un endpoint
    nuevo compilaría, pasaría las pruebas y reintroduciría la fuga. Ahora `mypy`
    falla en todo llamador que no decida qué expedientes alcanza.
  - Un único `_visible_document()` en el router, para que una ruta nueva herede la
    comprobación en vez de tener que acordarse.
  - Responde **404** y no 403, porque un 403 confirmaría que el registro existe.
  - Seis pruebas: lectura, edición, descarga, historial, aislamiento entre
    clientes, y **una que comprueba que el llamante legítimo sigue entrando**.
- **`--rekey` del CLI de migración a S3 generaba claves falsas.** Pasaba
  `document_id` como `case_id` y fijaba la extensión a `.bin`, así que escribía
  `cases/<doc>/documents/<doc>/v1-<hex>.bin`. Ahora la extensión sale de la clave
  almacenada y el token se deriva del identificador de la fila: **idempotente**.
- **El CLI de migración devolvía 0 aunque migrara a medias.** Una ejecución
  silenciosa y una rota se veían igual en stdout. Ahora un archivo local ausente,
  un digest discrepante o una escritura rechazada devuelven 4 y dicen que no se
  cambie `STORAGE_BACKEND`.
- `--offset` en ese CLI: con `--limit` solo, repetirlo reprocesaba siempre las
  mismas primeras N filas y nunca avanzaba.
- Un archivo local ausente se saltaba en silencio y no aparecía en `errors`.
- `slowapi` era una dependencia **muerta**: declarada y nunca importada.
- **Un `sorted set` con el timestamp como miembro colapsaba ráfagas.** Dos
  peticiones en el mismo milisegundo se reemplazaban y `ZCARD` se quedaba en 1:
  el limitador admitía un pico ilimitado justo cuando llega uno. El miembro lleva
  ahora un identificador único. Lo detectó la prueba que compara el almacén
  Redis con el de memoria sobre una ráfaga.
- El middleware construía **dos** almacenes en memoria distintos: el que contaba
  y el que `reset()` limpiaba. El estado se filtraba entre pruebas y el síntoma
  era «el limitador es demasiado estricto».
- `count >= limit` con el golpe ya contado admitía `limit - 1` y reducía a la
  mitad el presupuesto de autenticación. Ahora la comparación es estricta.
- `scan_iter` es un generador asíncrono y `reset()` lo trataba como lista.
- **PowerShell 5.1 corrompe la salida binaria nativa.** Un `pg_dump` redirigido con
  `>` produjo un archivo de 373 KB que `pg_restore` rechazaba; con `cmd /c` el
  mismo volcado dio 184 KB y 357 entradas válidas. Documentado para que el
  respaldo de este host no se dé por bueno por existir.
- El borrado de una solicitud redirige desde el Server Action a la cola limpia;
  antes la revalidación desmontaba la ficha y podía dejar su UUID eliminado en la
  URL.
- El test del 360 de expediente crea exactamente los dos eventos que espera: una
  reunión futura y la audiencia. El escenario anterior creaba tres y afirmaba dos.

### Verification
- TypeScript, ESLint y build de producción limpios.
- Flujo Docker real: creación pública, listado, ficha, cambio de estado y notas,
  fecha de atención, confirmación accesible y borrado físico; datos de humo
  retirados.
- 390×844 sin overflow ni ids duplicados; consola sin errores.
- 715 pruebas backend, 86,29 % de cobertura; `ruff` y `mypy` estricto limpios en
  154 archivos. Las cuatro pruebas nuevas fallan sin la comprobación y pasan con
  ella.
- Sobre el stack en ejecución: tres envíos al formulario público pasan y el
  cuarto devuelve 429, y `ratelimit:contact:ip:172.24.0.1` figura en Redis con
  `ZCARD=4` y TTL de ~1 h. El conteo está fuera del proceso.
- **769 pruebas backend, 86,71 %**; `ruff` y `mypy` estricto limpios en 158
  archivos, y `alembic upgrade`/`downgrade -1`/`upgrade` sin fallo.
- Frontend: `tsc`, ESLint y `build` limpios, y la puerta de maquetación
  **56 comprobaciones en verde** sobre once rutas y cuatro anchos.

## [0.34.0] - 2026-10-04
### Added
- **El respaldo de objetos se verifica por digest (ADR-062).** `objects.count` se
  escribía y nadie lo leía, y `MANIFEST.sha256` —que sí tenía el digest de cada
  archivo— tampoco. Un recuento no detecta un archivo truncado, que es el fallo
  que importa.
  - `app/services/backup_manifest.py` relee cada archivo y compara su SHA-256 en
    trozos de 1 MiB, y separa **alterado**, **ausente** y **no listado** porque
    significan cosas distintas. Un manifiesto vacío es fallo.
  - `app/cli/verify_backup_files.py` lo expone al operador, con `--objects-only`,
    `--strict-unlisted` y `--json`.
  - `scripts/backup.sh` lo ejecuta **antes** de la copia externa: subir un
    respaldo corrupto y descubrirlo después deja una copia rota lejos.
  - Separadores POSIX fijados: con `\` en Windows, un respaldo verificado desde
    Windows reportaba todos los objetos ausentes, que se lee como pérdida total.
- **El arranque exige bucket y versionado (ADR-058).** Con `STORAGE_BACKEND=s3`,
  `initialize_storage` comprueba que el bucket exista y que el versionado esté
  habilitado; si algo falla, la API no arranca.
- **`evidence-worker` como servicio de Compose (ADR-059).** Drena la cola de
  evidencias grandes cada 30 segundos. Es un proceso sin HTTP, para no multiplicar
  el rate limiter en memoria.
- **`test_packaging.py`.** Lee el `CMD` del Dockerfile y comprueba que ese binario
  esté declarado, además de que cada módulo de terceros importado tenga su
  distribución. Existe porque borrar `uvicorn` de `pyproject.toml` pasó `ruff`,
  `mypy` y las 678 pruebas, y dejó el servicio muerto.
- `app/core/http_status.py`, con los dos códigos que Starlette renombró en 1.x.

### Changed
- **Passlib sustituido por `argon2-cffi` (ADR-061).** Mismos parámetros, así que
  los hashes existentes siguen validando; uno de ellos queda congelado en
  `test_password_hashing.py` como contrato, y ese test no importa Passlib.
- **Ceilings fijados a lo verificado (ADR-063)**: `ruff>=0.12,<0.13`,
  `mypy>=1.17,<1.18`, `sqlalchemy>=2.1,<2.2`, con el motivo escrito al lado. El
  extra `dev` declara `types-passlib` y `types-python-jose`, sin los cuales una
  instalación limpia no podía pasar `mypy`.
- **Los 33 errores de `mypy` con SQLAlchemy 2.1 eran uno solo.** Las anotaciones
  `Select[tuple[Modelo]]` de ocho helpers en `dashboard.py` fijaban el tipo de
  fila; con `Select[Any]` se resolvieron todos. `rowcount` se sustituyó por
  `UPDATE ... RETURNING`, sin `cast`.
- **Cerrar sesión revoca la sesión de refresco (ADR-060).** Antes solo borraba
  cookies y el token vivía siete días. La justificación que lo excusaba era falsa:
  un Server Action no es un `beforeunload` que el navegador cancela.
- El resumen extractivo sin consulta devuelve las frases en orden de documento.
- El nombre de cliente del Dashboard une `cases` y `clients` explícitamente:
  desaparecen los dos últimos productos cartesianos.

### Verification
711 pruebas, 86,30 % de cobertura, cero avisos. `ruff` y `mypy` estricto limpios en
instalación limpia. Imagen reconstruida sin Passlib, que arranca y autentica con
un hash escrito por Passlib.

## [0.33.0] - 2026-10-04
### Added
- **Centro multimedia construido (V4).** `MASTER_PROMPT.md` lo prohibía bajo «Fases
  futuras, NO implementar aún»; la dirección levantó esa prohibición y queda
  registrado en **ADR-055**, junto al alcance que ADR-054 dejó pendiente decidir.
  `/admin/multimedia` es una biblioteca **interna** de la firma con vídeo, imagen,
  audio y PDF.
  - `MediaItem` y dos revisiones de Alembic: tabla y siembra de los seis permisos
    `media:*`. El rol `cliente` no recibe ninguno, y una prueba lo fija.
  - **Vídeo en la biblioteca, no en las evidencias.** La sección 17 enumera los
    formatos del motor de evidencias y no incluye `video/*`; abrir esa puerta sería
    tocar el contrato de un registro jurídico. `EVIDENCE_MIME_TYPES` queda intacto y
    el dominio nuevo no tiene inmutabilidad, derivados, custodia ni `legal_hold`.
  - **El tipo lo deciden los bytes.** `kind` decide si el navegador ofrece un
    `<video>`, así que se detecta por la cabecera y no se acepta del cliente; un
    MP4 renombrado a `.jpg` se archiva como vídeo. `RIFF` se resuelve por su tipo en
    el offset 8, porque es un contenedor.
  - **Registrar y subir son dos llamadas**: un recurso puede existir sin archivo, que
    es un estado normal, y `has_file` separa los dos.
  - **`DELETE` desactiva y conserva el archivo**, porque una fila sin sus bytes no
    se podría reactivar. El diálogo dice qué sobrevive antes de preguntar y el botón
    destructivo no toma el foco.
  - `GET /media/{id}/content` responde `206 Partial Content` con `Content-Range` para
    que un vídeo se pueda buscar, y `416` cuando el rango no existe.
  - `/api/media/[id]`: ruta de streaming propia con la credencial del lado del
    servidor, en vez de ampliar el proxy compartido, que lee el cuerpo con `text()`
    y aplana lo que un reproductor necesita por partes.
  - `apiFetch` deja pasar un `FormData` intacto y **sin** `Content-Type`: el
    navegador tiene que escribir el límite multipart.

### Fixed
- **`media:delete` se le había concedido por error al rol `abogado`** al escribir la
  matriz de permisos. Lo detectó `test_operational_roles_cannot_delete`.
- **La cabecera «Acciones» no se alineaba a la derecha en ninguno de los siete
  listados.** Llevaba `text-right` y la utilidad no podía ganar a `globals.css`, que
  va sin capas: `.ledger thead th` le gana por especificidad. Corregido con una regla
  `.ledger thead th.text-right` en la hoja, no en los siete marcados.
- El estado vacío del centro multimedia decía «la biblioteca está vacía» incluso
  cuando lo que faltaba era un filtro que no coincidía.

### Verification
- 637 pruebas de backend con 85,89 % de cobertura, incluidas veinticuatro del módulo
  nuevo; `ruff check` limpio en los archivos tocados.
- TypeScript, ESLint y build de producción limpios, con `/admin/multimedia` y
  `/api/media/[id]` en la lista de rutas.
- En el navegador, y **contra la base de datos**: alta con archivo, recurso
  registrado sin archivo, edición, desactivación con el archivo conservado y
  reactivación con los bytes en su sitio, y los cuatro filtros.
- **Reproducción real**: un WAV de 1,5 s suena (`readyState: 4`) y llegó como
  `206 Partial Content`; el PNG se ve a 320×180 servido por la ruta autenticada. A
  390×844 sin desbordamiento horizontal y con la ficha a todo el ancho.
- La base de datos y el volumen de almacenamiento quedan como estaban, sin recursos
  de prueba.

## [0.32.0] - 2026-10-03
### Added
- **Alcance decidido para los tres módulos futuros, sin construir ninguno.**
  `MASTER_PROMPT.md` sitúa el Centro multimedia, la IA jurídica y la Facturación
  bajo «Fases futuras, NO implementar aún», y solo pide que la arquitectura
  quede preparada. La preparación útil no es un endpoint que devuelve 501 ni una
  tabla vacía: es escribir qué se va a decidir y con qué restricciones.
  - **ADR-054** documenta el diseño de V4 —vídeos y biblioteca— y, sobre todo, lo
    que falta por debajo: hoy no se acepta vídeo ni audio en ninguna parte
    (`EVIDENCE_MIME_TYPES` es PDF, PNG y JPEG, y la sección 17 los enumera como
    únicos), no hay transcodificación, y «biblioteca» es un alcance distinto al
    del expediente, lo que por ADR-045 impide un único permiso `multimedia:read`.
    Deja escritas las cinco decisiones que V4 tendrá que tomar y cuál es la
    primera tarea cuando se autorice: decidir el alcance, no escribir la tabla.
  - Lo que V4 **sí** reutiliza queda anotado: niveles `StorageTier` con
    verificación por digest, motor de evidencias con original inmutable y cola
    para archivos grandes, convención `recurso:acción`, `change_logs` y la
    convención de desactivar en lugar de borrar.
  - La ficha de cada módulo inerte dice ahora **qué será y qué le falta**, en vez
    de limitarse a declarar que no está: Multimedial (V4), Facturación (V3) e IA
    Jurídica (V5), con `future: {phase, scope}` en `admin-nav.ts`.
  - Sin backend, sin migración, sin permisos sembrados y sin ningún enlace
    detrás del menú: los tres siguen inertes y con su motivo a la vista.

### Verification
- TypeScript, ESLint y build de producción limpios. Sin cambios de backend, la
  suite no se volvió a ejecutar: 613 pruebas y 85,75 % de cobertura son las de la
  versión anterior.
- Las tres fichas verificadas en el navegador: muestran fase y alcance, sin
  formularios ni botones, y sin desbordamiento horizontal.

## [0.31.0] - 2026-10-03
### Added
- **Configuración terminada en administración.** `/admin/configuracion` cierra el
  noveno y último módulo real de la superficie: con este, los nueve tienen
  pantalla y en el menú solo quedan los tres que `MASTER_PROMPT.md` prohíbe
  construir.
  - `system_settings` agrupada por categoría, con una hoja por bloque que lleva
    clave, valor, tipo y momento del último cambio.
  - Alta y edición en diálogo. El valor se edita como el texto que se guarda, no
    como el valor decodificado, y una columna «tipo» dice con qué se relee: `30` y
    `"30"` son los mismos bytes en esta tabla y solo uno es un número.
  - Búsqueda sobre clave, categoría, descripción y valor, de modo que una palabra
    que aparece en la pantalla encuentra su fila.
  - **Borrado por clave con confirmación**, y es la única excepción a la regla de
    no eliminar: un ajuste del sistema no es un registro jurídico, no guarda
    expedientes ni firmas, y su valor anterior queda en `change_logs`. El botón de
    confirmación no toma el foco inicial.
  - El menú pasa a `ready` con `settings:read`, y las acciones de escritura se
    habilitan por `settings:write` aparte.

### Fixed
- **La segunda escritura de un ajuste devolvía 500.** `updated_at` es
  `onupdate=func.now()`, una expresión SQL que el ORM no puede calcular: tras un
  UPDATE el atributo queda expirado y leerlo pide una carga perezosa. El router
  serializa la respuesta desde una función normal, fuera del greenlet, así que la
  carga saltaba donde no debía (`MissingGreenlet`) y la API contestaba 500 a un
  cambio que ya estaba confirmado. El alta nunca lo sufre porque un INSERT
  devuelve sus columnas: son dos rutas de código y solo se probaba una.
  `SettingsService.upsert` ahora refresca después del UPDATE, que es el patrón del
  proyecto en el resto de servicios.
- **El navegador centraba la primera columna de los ocho listados de
  administración.** Un `<th scope="row">` es un `th`, y la hoja de estilos del
  navegador centra todos los `th`; la regla existente solo corregía `thead`. Con
  columnas estrechas pasaba desapercibido y con una columna ancha era evidente. Se
  corrigió una vez en `globals.css` con `.ledger tbody th`.
- Configuración no mostraba el formulario de filtros sobre una tabla vacía, y
  rotulaba `updated_at` como «Última lectura» cuando es la última escritura.

### Verification
- 613 pruebas de backend con 85,75 % de cobertura, incluida una que escribe la
  misma clave dos veces —se comprobó que falla al quitar el `refresh`—; `ruff check`
  limpio en los archivos tocados (siguen los diez hallazgos preexistentes).
- TypeScript, ESLint y build de producción limpios, con `/admin/configuracion` en la
  lista de rutas.
- En el navegador, y **contra la base de datos**: alta, edición, borrado y los
  cuatro rechazos del backend (clave con credencial, clave inválida, mayúsculas,
  no ASCII) comprobados uno a uno; búsqueda y filtro por categoría; estados vacíos;
  el diálogo a 390×844 con desplazamiento y cierre por Escape; sin desbordamiento
  horizontal. La base queda sin ajustes, como estaba: las migraciones no siembran
  ninguno y ninguna clave se lee todavía en producción.

## [0.30.0] - 2026-10-03
### Added
- **Seguridad terminada en administración.** `/admin/seguridad` son tres vistas
  gobernadas por `?vista=usuarios|roles|auditoria`, cada una con su propio permiso
  (`users:read`, `roles:read`, `audit_logs:read`), y la entrada del menú pasa a
  `ready`.
  - Directorio de usuarios con búsqueda y filtros por rol y estado, alta y edición
    en diálogo, diálogo de roles que calcula la diferencia en el servidor contra lo
    que el servidor ya tiene, desactivación con confirmación y reactivación como
    acción propia. No hay borrar: una cuenta se desactiva porque la auditoría deja
    de ser legible en cuanto desaparece quien aparece en ella.
  - Roles y permisos: los cuatro roles con los permisos que concede cada uno, y el
    catálogo completo agrupado por recurso con su descripción.
  - Auditoría paginada sobre `GET /admin/audit-logs`, con filtros de texto,
    resultado y actor, y `user_email` en cada entrada para que el rastro nombre a
    una persona.
  - Backend: `GET /admin/users` acepta `search`, `role` e `is_active`; se añade
    `GET /admin/users/{id}` para no derivar la ficha de la lista.

### Fixed
- **Las cinco escrituras de identidad no se guardaban.** `admin.py` no tenía un solo
  `session.commit()`: los servicios hacen `flush` y `get_session` cierra la
  transacción sin confirmar, así que «Nuevo usuario» respondía 201, anunciaba el
  alta y la cuenta no existía. Era el único router de escritura del proyecto sin
  confirmar. La prueba nueva cuenta los `commit` en lugar de leer el dato de vuelta,
  porque la fixture comparte sesión y SAVEPOINT entre la petición y la aserción y
  una fila sin confirmar es visible ahí; se comprobó que falla al quitar las
  confirmaciones.
- **El diff de roles estaba invertido**: `toAdd` y `toRemove` intercambiados, de modo
  que se asignaba el rol desmarcado y se retiraba el marcado. Con roles coincidentes
  el error era invisible.
- **Desactivar y reactivar no revalidaban la ruta**: la base se actualizaba y el
  listado seguía mostrando `ACTIVO`.
- **El directorio de usuarios devolvía 500.** `UserBase.email: EmailStr` revalidaba la
  dirección al serializar y una fila con `.local` tumbaba la respuesta entera. La
  entrada valida (`UserCreate.email: EmailStr`) y la salida lee (`str`); el CLI
  `create_admin` valida `ADMIN_EMAIL` igual que la API, porque si no deja entrar por
  la puerta de atrás lo que la puerta bloquea.
- En la auditoría, el filtro de actor mostraba el nombre y cuatro cuentas se llaman
  igual: ahora muestra el correo, que es lo único único, y las filas sin usuario
  registrado dicen «Sin usuario» y llevan el filete de error.

### Verification
- 612 pruebas de backend con 85,74 % de cobertura, y `ruff check` limpio en los dos
  archivos tocados (quedan diez hallazgos preexistentes, ninguno en código reciente).
- TypeScript, ESLint y build de producción limpios, con `/admin/seguridad` en la lista
  de rutas.
- En el navegador, y **contra la base de datos**: alta con rol, edición, cambio de
  roles, desactivación y reactivación comprobadas fila a fila; los cuatro filtros de
  cada vista; paginación; estados vacíos; 390×844 sin desbordamiento horizontal en
  las tres vistas. El único error de consola es la hidratación preexistente del
  `<html className>` de la raíz.

## [0.29.0] - 2026-10-03
### Added
- **Documentos terminado en administración.** `/admin/documentos` es un archivo
  global de la firma: hoy los documentos solo existían dentro de un expediente y
  no había forma de recorrerlos.
  - `GET /api/v1/documents` devuelve `{items, total, skip, limit}` con búsqueda
    sobre título, descripción y número o título del expediente, y filtros por
    expediente, tipo, estado, confidencialidad, visibilidad y `legal_hold`.
  - El alcance se resuelve con el mismo `case_scoped(scope_filter(...))` que usa
    `list_cases`, para que la lista no cruce documentos con expedientes ajenos.
    Quien no tiene permiso de documentos ve la condición `false`, no todo.
  - La ficha abre en un cajón lateral con el historial de versiones, su hash, su
    nivel de almacenamiento y el enlace de descarga tras `documents:download`.
  - Sin borrar en ninguna parte: un documento acaba en `anulado` y una versión en
    ser reemplazada, y ambas siguen legibles.

### Fixed
- El cajón de detalle se abría como una tira del alto de una fila en lugar de
  cubrir la pantalla. La fila lleva la animación `row-enter` y un elemento con
  `transform` es el bloque contenedor de sus descendientes `position: fixed`, así
  que el `inset: 0` se resolvía contra la celda. Se portalla al `body`, y como
  `body > *` de la hoja sin capas anulaba el `fixed` de Tailwind, el overlay
  recupera su posición con `body > .viewport-overlay`.

### Verification
- 606 pruebas de backend con 85,63 % de cobertura, incluidas ocho nuevas para el
  listado: paginación sin perder el total, filtros, búsqueda, alcance de
  expediente ajenos, aislamiento del cliente, el filtro de visibilidad que no
  puede ampliar el acceso, autenticación y página fuera de rango.
- TypeScript, ESLint y build de producción limpios.
- En el navegador: 401 sin sesión, 422 con `limit=500`, 200 con los filtros; el
  cajón cubre 1440×900 con el panel a 576 px y 390×844 a todo el ancho, Escape y
  el fondo lo cierran, y los filtros navegan por URL.

## [0.28.0] - 2026-10-03
### Added
- **Agenda y audiencias terminada en administración.** `/admin/agenda` ofrece
  vistas de día, semana y mes, navegación temporal, filtros por abogado,
  expediente y tipo, cronología agrupada y un panel de vencimientos.
- Alta y edición de eventos y ciclo procesal de audiencias mediante Server
  Actions: programación, registro de estado y resultado, y reprogramación con
  trazabilidad.

### Fixed
- La API genérica de calendario ya no permite crear ni editar audiencias por una
  ruta que omita sus reglas procesales. El listado especializado exige
  `hearings:read`, respeta alcance, visibilidad y actividad, y el alta valida que
  expediente y abogado existan y estén activos.
- Las horas de Agenda se interpretan y presentan en `America/Bogota`. El
  contenedor frontend corre en UTC y antes mostraba `16:00` para una audiencia
  registrada a las `11:00`, aunque el instante persistido fuera correcto.
- El rótulo del periodo muestra solo fechas y trata el final exclusivo como tal;
  ya no expone medianoches UTC ni un día adicional.

### Verification
- Flujo HTTP real: evento creado y editado; audiencia creada, reprogramada y
  realizada; resultado vacío y solapamiento rechazados; una audiencia realizada
  deja de ofrecer reprogramación.
- Sin overflow horizontal ni ids duplicados en 320, 390, 768 y 1440 px; diálogo
  con foco interno y cierre por Escape; cero errores de consola.
- TypeScript, ESLint y build de producción limpios. Backend: 590 pruebas y
  85,72 % de cobertura.

## [0.27.0] - 2026-10-03
### Changed
- **Acciones administrativas con iconografía profesional.** Los listados de
  Expedientes, Clientes y Abogados ya no terminan en verbos desnudos: Editar usa
  un lápiz, Cerrar un expediente sellado y Desactivar una persona retirada.
  - Los cuatro glifos —incluido el signo de alta— son SVG de la misma familia:
    caja de 24 px, trazo 1,7, extremos redondos y color heredado.
  - El icono acompaña al verbo, no lo sustituye. Es decorativo para lectores de
    pantalla y el texto visible conserva el nombre accesible de la acción.
  - Editar y la acción de estado comparten ahora altura, ritmo y respuesta de
    hover/foco; la tabla gana jerarquía sin convertirse en una barra de botones.
  - Los iconos también aparecen en las confirmaciones, para que la consecuencia
    mantenga el mismo lenguaje desde la fila hasta el último clic.

## [0.26.0] - 2026-10-03
### Changed
- **Botón hamburguesa en móvil.** Los doce módulos estaban en una tira
  horizontal de fichas que se desplazaba de lado. La tira era honesta —todo a un
  toque— y estaba mal: había que desplazar un menú para saber qué existía,
  empujaba hacia abajo el contenido de **todas** las pantallas con una barra que
  nadie había pedido, y filtraba fuera los tres módulos «Pronto» precisamente por
  no tener `href`.
  - El panel tiene la misma arquitectura que el raíl de escritorio: los doce
    módulos con su motivo cuando están inertes, y el pie con la persona, su rol,
    «Mi panel», «Web pública» y «Salir», que en móvil no existían.
  - El botón es un `<button>` de verdad, con `aria-expanded` y `aria-controls`, y
    sus tres líneas se convierten en aspa al abrirse.
  - El panel se desmonta al cerrarse: sus enlaces no quedan en el orden de tabulación
    y un lector de pantalla no anuncia un menú que no está.
  - **Escape** cierra y el foco vuelve al botón. Al abrir, el foco entra al
    panel; si no, el tabulador recorre la página por debajo del menú.
  - El fondo deja de desplazarse mientras está abierto, y se cierra solo al
    navegar.
  - El alto de la barra baja de 130 px a 65 px en móvil.

### Fixed
- **Dashboard aparecía resaltado en todas las pantallas.** El ítem activo se
  calcula por prefijo, para que `/admin/clientes` siga encendido mientras se
  edita `/admin/clientes/8f3c…`. Pero la ruta del dashboard es `/admin` y todas
  las pantallas empiezan por `/admin/`, así que la regla lo encendía siempre: el
  menú mostraba dos ítems encendidos a la vez, el dashboard y el módulo que se
  estaba viendo. El índice de la superficie se enciende solo cuando es la
  superficie.

## [0.25.0] - 2026-10-02
### Changed
- **Interfaz de administración revisada** para que se lea de un vistazo y no sea
  un formulario gris sobre papel gris. La paleta no se tocó: papel, tinta, lacre
  y latón ya eran la identidad del portal privado.
  - **Una regla de estado por fila**, en el borde izquierdo y teñida según lo que
    es la fila: verde bosque lo que está vivo, latón lo que está suspendedo, lacre
    lo urgente, gris plano lo cerrado. Antes había que leer cada fila para saber
    cuáles requieren atención; ahora se localizan de un vistazo.
  - **Una sola píldora por fila.** El estado se quedó con la píldora y la
    prioridad pasó a un punto de color: dos píldoras en la misma fila son dos
    gritos, y el color es lo que debe verse de lejos.
  - **Jerarquía en la cabecera**: filete de latón sobre el eyebrow, título más
    presente y descripción más corta.
  - **Tarjetas KPI del Dashboard** con filete superior que distingue volumen de
    trabajo pendiente, y los dos paneles inferiores encerrados en tarjeta. El
    rojo de «Vencimientos abiertos» solo aparece cuando hay algo vencido: una
    regla roja sobre un cero es un panel que llora lobo, y este se lee primero
    cada mañana.
  - Las notas de sistema («un expediente no se elimina…») pasaron de texto suelto
    a filete de latón. No son decoración: son la razón por la que no hay botón de
    borrar, escritas donde su ausencia parecería un descuido.
  - Sombras cálidas y sutiles en las tarjetas: papel sobre papel, no una captura
    pegada en la página.
  - Entrada escalonada de las filas, 12 ms entre ellas y **tope de ocho**: un
    escalonado que crece con el número de filas convierte una tabla en una espera.
  - Lupa dibujada en el campo de búsqueda y variante `quiet` para los botones de
    la fila, que compiten con el enlace «Editar» si ambos llevan caja.

### Fixed
- La regla de estado no se pintaba. Es un `background-image` y no un
  `box-shadow` porque la tabla es `border-collapse: collapse`, y una tabla
  colapsada es justo donde la sombra de una celda deja de pintarse: el estilo
  calculado decía que estaba y la pantalla no mostraba nada.
- `.row-title` y `.row-meta` estaban anidadas bajo `.ledger`, así que no aplicaban
  en el Dashboard y los números de expediente salían en IBM Plex Sans de 16 px en
  vez de la mono de 11 px, partiéndose en dos líneas. Son clases autónomas.

## [0.24.0] - 2026-10-02
### Added
- **CRUD completo desde el listado** en Expedientes, Clientes y Abogados. La
  única acción de cada fila era «Abrir →», así que editar y cambiar el estado solo
  se alcanzaban entrando en la ficha: desde la lista el módulo parecía de solo
  lectura.
  - **Editar** enlaza a la ficha, que es donde vive el formulario.
  - **Cerrar** en cada expediente abierto, con el mismo diálogo de fecha y nota
    que en la ficha; los cerrados solo ofrecen editar.
  - **Desactivar** en cada cliente y abogado activo, con confirmación; los
    inactivos solo ofrecen editar.

### Fixed
- El propio arreglo introdujo **ids duplicados**: el diálogo de cierre se pinta
  ahora una vez por expediente abierto, así que `close-closed_at` se repetía
  tantas veces como expedientes abiertos había. El prefijo del diálogo ahora lo
  fija quien lo monta (`close-WA-2026-000003-closed_at`). Es exactamente el fallo
  que se corrigió una hora antes, reintroducido por el arreglo: por eso la
  comprobación de ids duplicados es una puerta, no una tarea.
- El diálogo de desactivar a un cliente mostraba `**no se borra**` con asteriscos
  literales: markdown dentro de JSX.

### Notes
- **No hay borrado físico.** `PROJECT_RULES.md` lo prohíbe y la firma lo decidió
  así al revisar el CRUD: «Desactivar / archivar». El `DELETE` del backend en
  clientes y abogados ya es una desactivación lógica, no un borrado. La
  consecuencia visible: un cliente desactivado desaparece del listado por
  defecto y solo aparece con «incluir inactivos», y un expediente cerrado no se
  puede volver a abrir desde la interfaz.
- Se cambió una decisión documentada en el código: el botón de desactivar vivía
  solo en la ficha, con el argumento de que veinte filas con veinte botones son
  veinte maneras de destruir algo. El argumento sigue siendo bueno y la
  respuesta fue el diálogo de confirmación, que se conserva.

## [0.23.0] - 2026-10-02
### Added
- **Expedientes completo**: listado con búsqueda, filtros por estado, proceso y
  prioridad, alta en diálogo, ficha 360 y cierre con fecha y nota.
  - La ficha se construye sobre `GET /cases/{id}/360`, que existe exactamente para
    esta pantalla: el expediente, colaboradores, partes y el recuento de cada
    sección. Un abogado abre un archivo y necesita saber de un vistazo si tiene
    documentos, evidencias y audiencia;(fetchear cinco listas para averiguarlo son
    cinco viajes y cinco formas de pintar una pantalla a medias.
  - Recuento de actuaciones, agenda, audiencias, documentos y evidencias, con la
    advertencia de que **las cifras son de lectura**: el detalle de cada sección se
    abre desde su propio módulo.
  - **Cierre** con explicación explícita de que cerrar no borra: documentos,
    evidencias, actuaciones y audiencias se conservan y siguen consultables.
  - Incorporación de abogado con su papel en el expediente y alta de parte
    (demandante, demandado, contraparte o tercero), con cliente vinculado,
    documento y notas.
- El menú lateral muestra **Expedientes** y el CRUD se comprobó de extremo a
  extremo: alta, edición, incorporación de abogado, alta de parte y cierre.

### Fixed
- **Expedientes no aparecía en el menú para nadie.** El módulo exigía un permiso
  `cases:read` que el proyecto no tiene: expedientes se autoriza por **alcance**
  (`cases:read_all`, `cases:read_assigned`, `cases:read_published`) y la API ya
  devuelve solo lo que cada perfil puede ver. Un permiso inventado no es una puerta
  restrictiva, es una puerta cerrada; la puerta correcta es el alcance, y el
  módulo se deja visibles para que el backend filtre.
- **Tras guardar, el formulario contradecía a la página.** React no toca el valor
  de un `<select>` no controlado, así que el selector conservaba la opción previa
  mientras el chip de al lado ya mostraba la nueva: «Prioridad alta» en el
  desplegable y «Prioridad urgente» en la tarjeta. Los campos de texto parecían
  correctos solo porque el usuario acababa de escribirlos. El formulario se
  remonta ahora con `updated_at`, que es la versión que el servidor incrementa en
  cada escritura, en expedientes, clientes y abogados.
- **IDs duplicados en el DOM.** Una ficha de expediente pinta el formulario y tres
  diálogos, y `notes` y `client_id` se repetían; en los listados, los filtros
  compartían id con el diálogo de alta. Repetir un id no es solo HTML inválido:
  rompe en silencio cada `<label htmlFor>` de la página, porque el navegador
  enfoca el primer control que encuentra. `FormField` admite ahora un `idPrefix`
  que cualifica el id sin tocar el `name` enviado, y los filtros llevan prefijo
  `filtro-`. Verificado: cero ids repetidos en las siete pantallas de administración.
- El encabezado de un expediente cerrado decía «Se conserva íntegro» mientras ofrecía
  un formulario editable. El backend sí permite corregir un cerrado —y toda
  corrección queda auditada—, así que el texto era el que mentía.

### Notes
- Un 500 puntual al incorporar abogado resultó ser una conexión obsoleta del pool
  tras un `--force-recreate`: `MissingGreenlet` en el `pre_ping`. El mismo clic
  funcionó a la segunda. No es un fallo del endpoint, pero un 500 sin explicar
  asusta: conviene reconocer el patrón antes de buscar un bug de código.
- Nada de esto amplía la superficie pública de la API.

## [0.22.0] - 2026-10-02
### Added
- **Portal de administración con menú lateral**, con los doce módulos del
  encargo. Es la primera superficie de administración del proyecto: hasta ahora
  solo existían la web pública, el portal del cliente y el gestor de evidencias.
  - `app/(admin)/admin/layout.tsx` hace el control de sesión **una vez** para
    toda la superficie. Antes vivía en cada página, y una página nueva que lo
    olvidara era una puerta abierta.
  - `lib/admin-nav.ts` con tres estados por módulo: `ready`, `building` y
    `planned`. Los tres módulos que `MASTER_PROMPT.md` prohíbe implementar
    aparecen **inactivos y sin enlace**, con etiqueta «Pronto» y la razón.
  - Un cliente que teclee una URL de administración va a su portal, no a un menú
    del que no puede abrir nada.
  - Primitivas de formulario que el proyecto no tenía: botón, campo, selector,
    área de texto, estado del formulario y paginación, con estado de envío y error
    por campo.
  - **Dashboard** que reutiliza `/api/v1/dashboard` en lugar de calcular nada.
  - **Clientes** y **Abogados** completos: listado con búsqueda, filtros y
    paginación, alta en diálogo, ficha con edición e historial de cambios, y
    desactivación con confirmación.
  - Iconos dibujados a mano, coherentes con el resto de la interfaz.
- Escrituras por **Server Actions**, no por el proxy del navegador: la lista
  blanca de `app/api/proxy` no se amplía, así que ninguna credencial llega al
  navegador y la API sigue siendo la única que comprueba permisos.
- Una página por módulo con API lista y pantalla pendiente, que dice qué existe y
  qué falta en lugar de mostrar una tabla vacía.
- **Aviso de salida de sesión** por Server Action.

### Fixed
- **`GET /api/v1/clients` contestaba 500 para todo el mundo.** `document_type` es
  un `Literal` cerrado y la base contenía un cliente con `NIF`. Como el listado
  serializa **todas** las filas, un solo registro no convertible tumbaba el
  endpoint entero y el administrador veía una cartera vacía. Añadidos `NIF` y `CC`
  a los dos esquemas, que son documentos colombianos reales, con dos pruebas de
  regresión: los `Literal` de cliente y abogado deben ser idénticos, y un
  documento inusual no puede volver a tumbar el listado.
- **`ApiRequestError` descartaba `details`**, así que un 422 llegaba como una
  frase que no nombraba ningún campo. Ahora conserva el payload y el formulario
  pinta el mensaje bajo el input que le corresponde.
- **El contenido caía debajo del rail.** El rail es `position: fixed`, así que no
  reserva columna de rejilla y `main` ocupaba la primera: el menú se comía la
  página. Corregido con relleno en `main` que coincide con el ancho del rail.
- **El área de administración paneaba de lado en móvil.** Una tabla de seis
  columnas no cabe en un teléfono; se desplaza dentro de su caja, pero esa caja
  seguía contando al `scrollable overflow` del shell. El shell lleva ahora
  `overflow-x: clip` —`clip` y no `hidden`, que lo convertiría en contenedor de
  desplazamiento— y la tabla usa `overflow-x: auto` con `min-w`, de modo que se
  desplaza ella sola en lugar de recortarse.
- La ficha de un cliente desactivado seguía mostrándolo activo: la acción solo
  invalidaba el listado, no la pantalla abierta. Invalida las dos, en clientes y
  abogados. El diálogo de confirmación también se cierra tras el éxito.
- Las especialidades se guardaban como **un solo bloque de texto**: `getAll`
  devolvía un único elemento con saltos de línea dentro y la API lo habría
  almacenado como una sola especialidad. Ahora se divide por líneas.

### Notes
- Nada de esto amplía la superficie pública de la API: la única escritura sin
  credenciales sigue siendo la del formulario de contacto.
- Los datos de prueba creados durante la verificación quedaron desactivados.

## [0.21.0] - 2026-10-02
### Reverted
- **La escalera de medidas y el escalado de tipografía en pantallas grandes.**
  Cinco tramos de contenedor (1200 / 1380 / 1560 / 2000 / 2360) más un segundo
  juego de overrides que subía titular, títulos, cuerpo y glifos por encima de
  2200 px. Era una idea mía, y empeoró la página: el texto dejó de pertenecer a la
  composición y el diseño se convirtió en una serie de saltos. Sustituido por una
  sola línea, `width: 100%; max-width: 1560px`, que crece con la ventana y se
  detiene.

### Fixed
- **`public-site.css` se truncó a 24 líneas** por una edición con un patrón que
  también aparecía en el comentario nuevo. Reconstruido desde la hoja compilada
  del último build correcto: todas las reglas se recuperaron, los comentarios se
  reescribieron y el archivo queda anotado como recuperado en su cabecera.
- **Un BOM UTF-8 al principio del CSS descartaba la primera regla en silencio.**
  El analizador leía `BOM + primer comentario + primer selector` como un único
  selector, así que la regla `.wrap` desaparecía entera y el minificador emitía un
  `?` suelto delante. Sin error, sin aviso: la página simplemente dejaba de estar
  contenida. Detectado midiendo `getComputedStyle`, no mirando la captura, y
  escrito en la cabecera del archivo para que no se repita.
- **La medida fluida robaba ancho en móvil.** `min(1560px, 100% - 4rem)` quitaba
  64 px de una pantalla de 320 px además del relleno y dejaba 206 px de contenido.
  El aire ya lo dan `margin-inline: auto` y el `padding`.
- **La rejilla de las siete áreas no llenaba la última fila** en cuatro columnas
  (`4 + 3`) ni en dos (`2+2+2+1`). La primera área ocupa la fila completa desde
  `sm` y las rejillas cierran cuadradas en los nueve tamaños probados.
- **El título de la tarjeta principal era ilegible**: `.site-display` lleva su
  propio color, así que el `color` de la tarjeta no llegaba al encabezado y
  «Derecho penal» salía petróleo sobre petróleo.
- **El menú móvil no atenuaba la página ni aceptaba el toque fuera.** El velo
  estaba dentro de la cabecera, que lleva `backdrop-filter`: un elemento con
  filtro se convierte en bloque contenedor de sus descendientes `position: fixed`,
  así que su `inset: 0` se resolvía contra los 91 px de la cabecera y no contra el
  viewport. Ahora es hermano de la cabecera.

### Added
- **Barrido de responsividad de 320 a 3840 px**, de iPhone SE a TV 4K, con
  medición y no con impresión. En los nueve tamaños: cero desbordamiento
  horizontal, `.site-canvas` igual al viewport, contenido útil de 270 a 1496 px,
  rejillas cerradas y titular entre 39 y 65 px.
- **La cabecera responde a la lectura.** Se condensa de 90 px a 66 px al pasar la
  primera pantalla, marca en dorado la sección en lectura y lleva una barra de
  avance de 2 px. Los tres valores se leen en un único
  `requestAnimationFrame` sobre un listener pasivo.
- **Paralaje en la ilustración del hero**, escrito como propiedad personalizada
  `--site-parallax` y no como estado de React: sesenta actualizaciones por
  segundo con un `setState` volverían a renderizar el subárbol entero para mover
  una caja catorce píxeles. Desactivado con movimiento reducido y en punteros
  gruesos.
- La ilustración respira con un flotado de nueve segundos y doce píxeles.
- **Velo en el menú móvil**, toque fuera para cerrarlo, y `max-height` con
  desplazamiento para que en un móvil apaisado el último enlace no quede
  inalcanzable.
- **Anillo de foco en dorado** con `:focus-visible`.
- El orden del menú sigue a la página: **Servicios** antes que **La firma**. Con
  el marcador de sección activa, un menú desordenado hace que el resaltado camine
  hacia atrás.

### Notes
- Todo el movimiento respeta `prefers-reduced-motion`: sin paralaje, sin flotado,
  transiciones a cero, y la página es la misma sin nada oculto.

## [0.20.0] - 2026-10-02
### Added
- **El formulario de la web pública envía de verdad.** Era el hueco que quedaba:
  la página declaraba que no enviaba nada porque no había dónde. Ahora hay una
  fila, una cola y un equipo que la responde.
  - `consultation_requests` con migraciones `f4c5d6e7a8b9` (tabla) y
    `a5b6c7d8e9f0` (permisos `consultations:read`, `:update`, `:erase`). Head
    Alembic: `a5b6c7d8e9f0`.
  - `POST /api/v1/consultations` **público**, y lectura, cambio de estado y
    borrado para el equipo. La ruta pública está en `PUBLIC_PATHS` de
    `test_hardening.py`, que es lo que impide que aparezca una tercera por
    descuido.
  - `frontend/app/api/consultas/route.ts`: una ruta fija, un verbo y un cuerpo
    reconstruido campo por campo. No es el proxy autenticado, porque este
    formulario lo usa alguien sin cuenta.
  - El formulario **solo confirma con un 201** y el texto de confirmación lo
    devuelve la API, no el componente. Si falla o hay 429, **conserva lo escrito**.
  - Consentimiento como columna: `consent_at` y `privacy_notice_version` en cada
    fila, sin valor por defecto, porque una fila que no puede decir qué se
    aceptó no debe poder existir.
  - Trampa anti-bot: un campo invisible que solo un automatismo llenaría. Un 422
    como cualquier campo inválido, y no se guarda nada.
  - **Aviso de privacidad** en un diálogo, redactado con lo que la firma
    publica y marcado en la propia página como pendiente de revisión.
  - `frontend/app/icon.svg`: la W dorada sobre el petróleo. La firma no tiene
    logotipo institucional, y a 16 px un logotipo de texto no se lee.
- Presupuesto más bajo de la aplicación: **tres envíos por IP y por hora**, con
  su propio perfil de limitador.

### Changed
- Las siete áreas de práctica reales sustituyen a las cuatro de la maqueta en el
  selector del formulario, y coinciden con el `Literal` del esquema.

### Fixed
- **La cola no tenía orden total.** `created_at` viene de
  `server_default=now()`, y el `now()` de PostgreSQL es el *inicio de la
  transacción*, no el momento del `INSERT`: todas las filas escritas por una
  misma transacción comparten instante. Sin una segunda clave, el orden de esas
  filas es el que el planificador devuelva y dos páginas de la cola podían
  mostrar la misma solicitud dos veces. Se añadió `id` como desempate.

### Notes
- **Sin `change_logs` a propósito.** El resto de la aplicación deja historial por
  campo; aquí eso escribiría el nombre, el teléfono, el correo y el problema
  legal en una segunda tabla, y quien pidiera su eliminación tendría que ser
  borrado de dos sitios.
- **Borrado real, no lógico.** `PROJECT_RULES.md` prohíbe borrar físicamente
  registros jurídicos. Una solicitud que nunca llegó a ser expediente no lo es,
  y la persona tiene derecho a que desaparezca; un borrado lógico dejaría el
  problema legal en la tabla.
- La auditoría registra método y ruta del `POST` anónimo y de los cambios del
  equipo, nunca el cuerpo.

## [0.19.0] - 2026-10-02
### Added
- **La identidad real de la firma en la web pública.** Estaba toda marcada como
  pendiente; `WABOGADOS_recursos` traía las URL de los originales y el sitio de
  la firma los publica, así que lo pendiente era recuperable.
  - **Equipo con nombre, cargo y fotografía**: William Ruiz Villegas (abogado
    fundador), Faiber Andrés López Ruiz (abogado junior) y Geraldine López Ruiz
    (asesora de negocios). Los tres retratos se recuperaron desde las URL del
    inventario: el paquete traía los accesos, no los archivos.
  - **Las siete áreas de práctica** que la firma lista, con su redacción propia:
    penal, ley familiar, laboral, constitucional, civil, comercial y asesorías
    empresariales. Antes eran cuatro y una de ellas —derecho público— no figura
    en el sitio de la firma.
  - **Aliados estratégicos** con las marcas de Rojas & Ríos Abogados y Wolfgang
    Ramírez.
  - **Dirección, teléfono y horario** en el bloque de contacto y en el pie, con
    el teléfono como enlace `tel:`.
  - **La cita de Francisco de Paula Santander** que la firma usa como firma de su
    declaración de principios, con atribución.
- Los retratos van en escala de grises y recuperan el color al llegar el puntero
  o el teclado. Tres fotos en color seguidas tiraban de la página hacia otra
  firma que no es la que describe la paleta.

### Fixed
- **El logotipo cuadrado de un aliado se salía de su placa.** `.ally-mark` usaba
  `aspect-ratio`, y con `aspect-ratio` la altura de la caja no es una longitud
  resuelta: el `max-height: 100%` de la imagen no tenía contra qué calcularse.
  Las dos placas quedaban a distinta altura y el nombre de una marca se leía
  pegado al lado de la otra marca. Ahora la placa tiene altura definida.
- El pie carece de nombre para la marca de aliados; quedó dentro de la placa
  flexible y se colocaba como columna junto al logotipo.

### Changed
- El correo electrónico sigue siendo «por confirmar», y ahora la página explica
  por qué: `wabogados.co` lo publica detrás de la protección de correo de
  Cloudflare y no está en el código fuente. No se escribe un `@` plausible.
- **Se descartan los tres testimonios** del sitio de la firma. Son relleno de
  demostración del tema: hablan de proyectos de diseño web y de derechos de autor
  de libros. Publicarlos como opiniones de clientes habría sido inventar
  respaldo.

## [0.18.0] - 2026-10-02
### Fixed
- **La web pública no ocupaba todo el ancho del viewport.** El `body` comparte los
  tokens del portal privado, cuyo papel `#f2eee4` es más oscuro que el marfil
  `#f7f5f0` de la web pública, así que en pantallas anchas se veía una franja de
  papel en los laterales: la página parecía una hoja colocada sobre el escritorio.
  Se resuelve con `.site-canvas`, una capa fija que pinta el marfil de principio a
  fin del viewport y va por detrás del contenido. Mide el ancho exacto en 390,
  1280, 1440 y 1920 px, sin desbordamiento horizontal en ninguno.
  - El lienzo se monta **solo** en la portada pública. `/login`, `/estado` y el
    portal privado conservan el papel del documento, porque ahí el papel es la
    señal de "esto no es la web pública".

## [0.17.0] - 2026-10-02
### Changed
- **Ritmo tipográfico continuo** en la web pública: todo el display usa `clamp()`
  en lugar de saltar entre tamaños fijos. El titular mide 39,2 px a 320 de ancho y
  64,8 px a 1440. El diseño de referencia salta entre valores, y eso es lo que
  hace que su versión estrecha se vea apretada: la página ahora está **compuesta
  a cada ancho**, no tolerada en los pequeños.
- Ritmo vertical con `clamp()`: el relleno de sección escala entre 64 y 118 px.
- **Movimiento al desplazarse**: cada bloque llega con un escalonado de 60–90 ms y
  cada sección se abre con un filete dorado que se dibuja. Las tarjetas de
  prácticas responden al ratón y al teclado: el filete se engrana en dorado, el
  glifo se rellena y el subrayado del enlace se traza.
- El hueco reservado del equipo se limita a 300 px de alto en pantallas estrechas:
  a 320 px eran 280 px de vacío apilados tres veces.
- La ilustración del hero lleva una sombra amplia y difusa para leerse como un
  objeto colocado.
- `scroll-behavior: smooth` y `scroll-padding-top: 100px`, para que la
  navegación por anclas no esconda el título bajo la cabecera fija.
- El pie pasa a banda petróleo, alineado con el resto de la paleta.

### Fixed
- **El revelado al desplazar no funcionaba.** El estado vivía en un `useState`
  cuyo inicializador leía `IntersectionObserver`: vale distinto en el servidor
  y en el cliente, y React adopta el valor del servidor al hidratar. Los 50
  bloques salían visibles desde el primer pintado y el efecto quedaba muerto.
  Ahora el estado oculto está en el CSS, condicionado a `html.js`, y el
  componente solo añade `is-in`.
- **`dangerouslySetInnerHTML` en `<html>`** inyecta hijos, no atributos: habría
  sustituido el documento en vez de marcarlo. Ahora es un `<script>` real.
- El tinte del hueco del equipo, en `background` en línea, **reemplazaba todas
  las capas** y se llevaba por delante la trama diagonal. Llega por
  `--portrait-tint`.

## [0.16.0] - 2026-10-02
### Added
- **Web pública de WABOGADOS**, siguiendo `WABOGADOS_web.html` como referencia
  visual y el enunciado de `wabogados.html.md`.
  - Portada en `/` con el orden de secciones de la referencia: hero
    («Su tranquilidad. Nuestra mejor defensa.»), banda de confianza, áreas de
    práctica, la firma, el portal de clientes, equipo, actualidad jurídica,
    contacto y pie.
  - Paleta corporativa incorporada al sistema de diseño: azul petróleo
    `#132c35`, dorado `#b28b55` y marfil `#f7f5f0`, con los valores literales del
    HTML de referencia.
  - Ilustración de columnas y balanza en SVG en línea, conservada mientras no
    exista recurso institucional aprobado.
  - Menú móvil accesible, diálogo nativo con devolución del foco y formulario
    con estados de carga y validación.
  - `app/estado` para la página de estado del sistema, antes en la raíz.
  - Acceso por rol tras autenticarse: cliente a `/portal`, personal a
    `/expedientes`, decidido por permisos y no por el nombre del rol.
  - `specs/web-publica.md` documenta la referencia y cada decisión.

### Security
- «Portal privado» conduce al acceso real de la plataforma, no a una maqueta.
- El `404` en español no revela si un expediente existe, que es lo que el `404`
  del backend esconde a propósito.

### Fixed
- **El botón «Portal privado» era invisible**: `.site-nav-links > a` tiene más
  especificidad que `.site-btn`, así que el enlace heredaba texto petróleo sobre
  fondo petróleo. En la referencia ese elemento era un `<button>` y nunca casaba
  con la regla. Corregido en la regla, no en el botón.

### Content
- **No se inventa nada.** Sin abogados, fotografías, direcciones, teléfonos,
  trayectorias ni credenciales. Los huecos llevan la marca «Pendiente».
- Los artículos de actualidad se identifican como **contenidos de ejemplo** en la
  tarjeta, en el diálogo y en la nota, y llevan etiqueta de aprobación pendiente.
- Las cifras del portal ilustrado son ficticias y el panel lo dice.
- **El formulario no envía y lo declara**: no existe endpoint de contacto en el
  backend, y el estado que muestra describe lo que realmente ocurrió.

## [0.15.0] - 2026-10-02
### Added
- **Interfaz de usuario: panel del cliente y gestor de evidencias**
  (`MASTER_PROMPT` 5, 10 y 39). El frontend pasa de una página de estado a una
  aplicación con sesión, rutas y diseño propio.
  - **Panel del cliente** (`/portal`): saludo, procesos, estado, próxima
    audiencia, vencimientos, documentos publicados, evidencias visibles y
    conversación con el despacho.
  - Detalle de expediente (`/portal/casos/[caseId]`), mensajes
    (`/portal/mensajes`) y documentos (`/portal/documentos`).
  - **Gestor de evidencias** (`/expedientes/[caseId]/evidencias`) con vista de
    tarjetas y vista de tabla, miniaturas, búsqueda, filtros y cajón de cadena
    de custodia.
  - **Subida con las seis etapas** de la sección 39 sobre un riel de progreso, y
    el motivo del rechazo del servidor cuando un archivo no es válido.
  - Sistema visual «instrumento legal»: papel, tinta, lacre y latón; Fraunces,
    IBM Plex Sans e IBM Plex Mono; tablas con renglones de libro contable en
    lugar de zebrado.
  - `404` propio en español, redactado para no revelar si un expediente existe.
  - `specs/interfaz.md` documenta las decisiones.

### Security
- **Los tokens nunca llegan al JavaScript del navegador.** Viven en cookies
  `httpOnly`; los componentes cliente llaman a `/api/proxy/*`, que adjunta la
  credencial en el servidor. El proxy acepta solo los prefijos que la interfaz
  usa y cinco verbos.
- **Las descargas ya no llevan el token en la URL.** Un enlace con
  `?access_token=…` mete una credencial viva en el historial del navegador, en
  el `Referer` de cada petición y en el log de la API. La ruta
  `/api/descarga/*` transmite los bytes con la credencial adjunta.
- El 404 en español no dice «no tiene acceso»: confirmaría la existencia del
  expediente, que es justo lo que el 404 del backend esconde.

### Fixed
- **La sesión moría a los 30 minutos.** El token de refresco se guardaba pero
  nada lo usaba. Ahora `proxy.ts` lo renueva antes de renderizar. No se puede
  hacer dentro del render: un Server Component no puede escribir cookies, así
  que el reintento usaba el token caducado, y como el backend **rota** el token
  de refresco, el segundo intento destruía la sesión recién renovada.
- **Bucle de redirección ante cualquier fallo de la API.** El panel redirigía
  al acceso cuando el dashboard fallaba por un 429 o un tiempo de espera; la
  página de acceso veía la cookie y lo devolvía. Ahora `session-guard.ts`
  distingue sesión ausente de servicio caído.
- **`/api/descarga/*` perdía el prefijo `/api/v1/`** al refactorizar, y toda
  descarga fallaba con `Failed to parse URL`.
- Una barra de scroll vertical aparecía en la navegación: `overflow-x`alone
  hace que el otro eje compute a `auto`, y el subrayado de la pestaña activa se
  salía un píxel.
- El nodo «Listo» quedaba dibujado como etapa en curso cuando el proceso ya
  había terminado.
- `primera_instancia` llegaba a la pantalla con guion bajo. `humanise()` y las
  etiquetas por trámite lo traducen.
- La tabla del gestor recortaba la columna de acciones, dejando el cajón de
  custodia inalcanzable.
- El riel de etapas se completaba con un salto temporizado, animando un
  estado que ya había ocurrido.

### Design
- `compression_ratio` del backend es un **porcentaje**, no una fracción: su
  docstring decía `0..1` mientras multiplicaba por 100, y el frontend lo
  multiplicaba otra vez, pintando «1224 %» de un 12 % de ahorro. Docstring
  corregido y test que fija la unidad.
- Cuando un derivado pesa **más** que el original, la tabla dice `mayor` y el
  cajón «mayor que el original», en lugar de recortar a `0 %` y presentarlo
  como ahorro.
- Una evidencia sin original ya no muestra una caja verde de «SHA-256
  registrado»: no hay hash porque el archivo no llegó a almacenarse, y un panel
  de integridad no puede afirmar una verificación que no ocurrió.
- Una raya en la tabla significa «sin medir», nunca «cero».

## [0.14.0] - 2026-10-01
### Added
- **QA, hardening y despliegue (Fase 10, MASTER_PROMPT 34, 37, 41, 43 y 44)**:
  - **`system_settings`**, la única tabla de la sección 37 que faltaba:
    clave, valor, descripción, categoría y autor del cambio. Servicio con
    validación de clave, tipos JSON y rechazo de claves con aspecto de
    credencial.
  - Endpoints de administración: `GET/PUT/DELETE /api/v1/admin/settings/{key}`
    y `GET /api/v1/admin/settings`.
  - **Observabilidad de la sección 43**: `GET /api/v1/admin/metrics/evidence`
    mide cantidad de evidencias, MB originales, MB optimizados, MB ahorrados,
    ratio de compresión, tiempo medio de procesado, fallos, archivos en
    cuarentena y uso de almacenamiento. Los recuentos y sumas se hacen en SQL.
  - `GET /api/v1/admin/metrics/evidence/derivatives` con el desglose por tipo.
  - Permisos `settings:read`, `settings:write` y `metrics:read`, con las
    migraciones `d2e3f4a5b6c7` (tabla) y `e3f4a5b6c7d8` (permisos).
  - `JobStatus` como enum, en lugar de cuatro cadenas mágicas en el servicio.
  - `.github/workflows/quality-gates.yml`: escaneo de secretos, lint, tipos,
    migraciones reversibles, suite con techo de cobertura, construcción de la
    imagen y gates del frontend.
  - `docs/DEPLOY.md`: runbook de despliegue, configuración obligatoria por
    entorno, verificación, routine, rollback e incidentes.

### Security
- **Un ajuste no puede contener credenciales.** Cualquier fila de
  `system_settings` es legible por todo administrador, entra en cada `pg_dump` y
  su valor anterior se escribe en `change_logs`. Las claves que parecen
  credenciales se rechazan con 422.
- `test_only_login_and_refresh_are_public` recorre las 92 rutas y falla si alguna
  no está autenticada y no deriva su alcance de un permiso.
- `test_a_user_without_permissions_reads_nothing` afirma que ningún endpoint de
  lectura devuelve una UUID a un usuario sin permisos.

### Fixed
- **Borrar un ajuste no dejaba rastro en la auditoría.** `record_changes` omite
  un campo cuyo valor no cambió, y el borrado pasaba `after={}`, así que no se
  registraba ninguna entrada. Ahora el valor ausente de cada campo se registra
  explícitamente.
- `ADMINISTRATOR_PERMISSIONS` no incluía los permisos de ajustes y métricas, lo
  que rompía la invariante de que el administrador posee todo el catálogo.
- **Los permisos nuevos no los sembraba ninguna migración.** Los endpoints de
  ajustes y métricas habrían respondido 403 en producción. Repetía el fallo de
  Fase 8, y el test de regresión anterior no lo detectaba porque comparaba
  catálogo contra matriz, nunca contra la base de datos.

## [0.13.0] - 2026-10-01
### Added
- **Dashboards por alcance (Fase 9, MASTER_PROMPT sección 10)**:
  - `services/dashboard.py` con cifras y listas ya filtradas por alcance.
  - `schemas/dashboard.py` y `api/v1/dashboard.py`.
  - Dos endpoints: `/api/v1/dashboard` (panel completo, con `days` y `limit`)
    y `/api/v1/dashboard/summary` (solo los contadores de la cabecera).
  - Cifras: clientes y abogados activos, expedientes activos y cerrados,
    actuaciones del mes, audiencias próximas, actuaciones pendientes,
    vencimientos por llegar y vencidos, documentos recientes, evidencias,
    mensajes pendientes y notificaciones sin leer.
  - Permiso `dashboard:read` en los cuatro roles, con la migración
    `c1d2e3f4a5b6`.
  - Vencimientos vencidos se informan **aparte** de los por llegar.
  - 25 tests en `test_dashboard.py`, con regresión del producto cartesiano en
    los agregados.

### Fixed
- **Los agregados contaban filas de más.** `_count` aplicaba los filtros fuera
  del subquery, lo que hacía que SQLAlchemy reincorporara la tabla de origen y
  el resultado fuera el producto cartesiano: contar dos expedientes devolvía
  cuatro en cuanto existía cualquier otra fila. Es la misma forma de fallo que
  documenta `case_scoped`. Los filtros van ahora dentro de la consulta.

### Design
- No hay un endpoint por rol. La diferencia entre administrador y abogado no es
  qué cifras existen, sino qué filas puede ver el llamante; el panel se deriva
  del alcance, no del nombre del rol.
- `dashboard:read` da acceso al agregado, no a datos nuevos. Un cliente sin
  expedientes recibe ceros en lugar de un error.

## [0.12.0] - 2026-10-01
### Added
- **Mensajería interna y con clientes (Fase 8, MASTER_PROMPT 33, 35 y 37)**:
  - Cinco tablas: `conversations`, `conversation_participants`, `messages`,
    `message_attachments` y `notifications`.
  - Migraciones reversibles `a9b0c1d2e3f4` (tablas) y `b0c1d2e3f4a5` (permisos).
  - Conversaciones de tipo `interna` y `cliente`, ligadas a expediente, a cliente
    o a ambas.
  - Estado leído por participante (`last_read_at`), silenciado (`is_muted`) y
    baja (`left_at`).
  - Trece endpoints bajo `/api/v1/conversations`, `/api/v1/messages` y
    `/api/v1/notifications`, con 404 anti-enumeración.
  - Adjuntos sobre `StorageBackend`: validación por magic bytes, SHA-256
    verificado en cada descarga y clave derivada de identificadores del
    servidor.
  - Ocho permisos `messages:*` y `notifications:*`. El cliente lee, envía y
    recibe avisos; no abre hilos, no adjunta y no archiva.
  - Perfil de límite de tasa propio para la escritura de mensajes.

### Security
- **Una conversación interna no puede filtrarse al portal.** Añadir un usuario
  de cliente a un hilo interno se rechaza con error en lugar de ignorarse en
  silencio, y el listado filtra por tipo además de por participación.
- **La visibilidad es por participación, no por rol.** Ser administrador ya no da
  acceso a conversaciones en las que no se participa.
- **El cuerpo de un mensaje no se escribe en `change_logs`.** La auditoría
  registra el envío sin convertirse en una copia de la correspondencia.
- Adjuntos de chat siempre servidos como `attachment`, nunca `inline`.

### Fixed
- `get_permission_definitions()` no incluía `MESSAGE_PERMISSIONS`, por lo que la
  migración de permisos insertaba cero filas y toda petición autenticada de
  mensajería respondía 403 sin causa visible. Cubierto por
  `test_every_role_permission_exists_in_the_catalog`.
- `messages.sent_at` solo tenía `server_default=func.now()`. En PostgreSQL
  `now()` es tiempo de transacción, así que los mensajes escritos en una misma
  petición compartían instante y el hilo se mostraba en orden arbitrario.
- `_add_participant` recorría y modificaba la colección perezosa
  `conversation.participants`, provocando `MissingGreenlet`.
- `_message_response` validaba filas (`result.all()`) en lugar de entidades
  (`result.scalars().all()`), con `ValidationError` en la respuesta de mensajes
  con adjunto.
- `build_message_key` conservaba puntos del nombre de extensión, de modo que
  una extensión manipulada podía introducir `..` en la clave de almacenamiento.
- `messages:delete` contradecía el invariante de que los roles operativos no
  poseen permisos `*:delete`. Renombrado a `messages:archive`; el borrado sigue
  siendo lógico.

## [0.11.0] - 2026-10-01
### Added
- **Motor Profesional de Evidencias (Fase 7, MASTER_PROMPT 17-32 y 40)**:
  - Seis tablas: `evidences`, `evidence_files`, `evidence_derivatives`,
    `evidence_processing_jobs`, `evidence_access_logs` y `evidence_events`.
  - Migraciones reversibles `e7f8a9b0c1d2` (tablas) y `f8a9b0c1d2e3` (permisos).
  - Restricción `uq_evidence_single_original`: la base de datos garantiza un
    solo original por evidencia.
  - Validación reforzada con detección de políglotos y bombas de descompresión.
  - Procesado de imágenes con Pillow: EXIF antes de redimensionar, proporción
    preservada, sin ampliar, alfa conservado y perfiles por tipo de evidencia.
  - Procesado de PDF con pikepdf: páginas, metadatos, texto y **detección de
    firma digital con comprobación del ByteRange**.
  - Diez permisos `evidences:*`; el cliente nunca recibe `download_original`.
  - Cadenas de claves según `MASTER_PROMPT` sección 28.
  - API con alcance de expediente y 404 anti-enumeración.
  - `GET /evidences/{id}/custody` con la cadena de custodia completa.
  - CLI `evidence_worker` con `FOR UPDATE SKIP LOCKED`.
  - Sección `evidencias` disponible en la ficha 360º.
  - `Pillow` y `pikepdf` como dependencias.

### Rules
- **El original nunca se altera.** `MUTABLE_FIELDS` no incluye el hash, la fecha
  de carga ni la clave de almacenamiento, y ningún schema puede expresarlos.
- **Un PDF firmado se copia byte a byte.** Reoptimizarlo destruiría la firma.
- **Un derivado nunca sustituye jurídicamente al original.**
- **Una descarga que no coincide con su hash se bloquea**, no se sirve.
- **Lectura por identificador exige visibilidad Y alcance**, con el alcance
  dentro de la consulta para que ningún endpoint pueda omitirlo.

### Fixed
- **Fuga de alcance en evidencias**: `get_visible_evidence` comprobaba solo la
  visibilidad, así que un abogado con `evidences:view` sin expedientes
  asignados podía leer por UUID la evidencia de cualquier expediente. Ahora el
  alcance es un parámetro del método, no una responsabilidad de cada endpoint.
- `/custody` no aplicaba alcance: cualquiera con `evidences:audit` leía la
  custodia de toda la firma.
- Los derivados PNG se etiquetaban como `image/jpeg` por un ternario que solo
  contemplaba WebP.
- La detección de políglotos buscaba la firma ZIP solo en el offset cero.
- `MissingGreenlet` al leer colecciones no cargadas tras el commit.

### Verified
- 440 tests, 85.18% de cobertura, Ruff y mypy strict limpios en 108 archivos.
- Migración `upgrade` → `downgrade` → `upgrade` sin errores; head `f8a9b0c1d2e3`.
- Flujo HTTP real con 0 fallos: original inmutable, segundo original rechazado
  con 409, descarga auditada con hash en cabecera, PDF de 3 páginas detectado y
  ficha 360º con evidencias.
- 70 tests del motor de evidencias, incluidos polígloto, bomba de dimensiones,
  firma digital detectada y copia byte a byte.

## [0.10.0] - 2026-09-30

## [0.9.0] - 2026-09-30
### Added
- **Verificación de integridad del bucket** (`MASTER_PROMPT` 44):
  - `IntegrityService` de solo lectura que compara el SHA-256 almacenado con el
    registrado en la base de datos.
  - Hallazgos `corrupted`, `missing`, `size_mismatch`, `unreadable` y `orphaned`.
  - Detección de objetos huérfanos mediante listado del almacenamiento: la única
    forma de demostrar que no se ha añadido nada al bucket.
  - `iter_keys` y `stat` añadidos a `StorageBackend`, con paginación en S3.
  - Verificación por lotes con concurrencia acotada, sin compartir la sesión
    asíncrona entre tareas.
  - Modos `full` y `sample` (muestra determinista, para uso nocturno).
  - Tablas `integrity_scans` e `integrity_findings` con la migración reversible
    `d6e7f8a9b0c1`. Solo se persisten los problemas.
  - `GET /api/v1/documents/integrity/latest` para auditorías.
  - CLI `verify_integrity` con código de salida para el monitoreo.

- **Respaldo y verificación de restauración**:
  - `BackupService`: `pg_dump` en formato custom comprimido, con SHA-256 y
    manifiesto que registra digest, revisión de Alembic y configuración.
  - `verify_backup` restaura en una base de datos temporal, comprueba el digest,
    la revisión, las tablas críticas y los recuentos, y la borra. La base real
    nunca se toca.
  - `scripts/backup.sh` cubre los cuatro puntos de `MASTER_PROMPT` 44:
    configuración, PostgreSQL, originales y derivados críticos.
  - `docs/RESTORE.md`: procedimiento de restauración documentado y probado.
  - CLI `backup_database` y `verify_backup`.
  - Cliente PostgreSQL 17 en la imagen, necesario para respaldar.
  - `enable_versioning` en `S3Storage`.
  - `change_logs.change_reason` ya cubría la trazabilidad de los cambios
    automáticos.

### Rules
- **Base de datos antes que objetos.** El contenido se escribe antes de que su
  fila haga commit, así que respaldo invertido puede dejar filas apuntando a
  objetos ausentes.
- **La verificación nunca repara.** No existe ruta de escritura ni borrado desde
  el verificador, y hay un test que falla si alguien la introduce.
- **Un respaldo sin restaurar es una hipótesis.** Por eso cada generación
  verifica la restauración y sale con código 4 si falla.
- Ninguna credencial llega a un volcado ni a un log: `redact` la elimina de la
  URL y `PGPASSWORD` la pasa por entorno.

### Fixed
- `compose.test.yaml` sobrescribía `PATH` con el valor del host, lo que ocultaba
  `/usr/bin` y rompía `pg_dump`.
- `pg_dump` recibía `postgresql+asyncpg://...`, driver que ignora y caía al
  socket local. Ahora se normaliza a `postgresql://`.
- `createdb`/`dropdb` conectaban como el usuario del SO (`root`) por no pasar
  `--username`.
- `IntegrityScanResponse` no validaba: `from_attributes` no se propaga a modelos
  anidados en Pydantic v2.

### Verified
- 334 tests, 84.90% de cobertura, Ruff y mypy strict limpios en 96 archivos.
- Restauración real comprobada: 25 tablas, revisión `d6e7f8a9b0c1`, salida 0.
- `backup_database` y `verify_backup` ejecutados de extremo a extremo en Docker.
- 27 tests de integridad y 20 de backup, incluidos digest manipulado, base
  temporal eliminada y base de producción intacta.

## [0.8.0] - 2026-09-30

## [0.7.0] - 2026-09-30
### Added
- **Fase 6 — Gestor documental versionado**:
  - `Document` ligado a un expediente con tipo, estado, confidencialidad y visibilidad.
  - `DocumentVersion` con contenido inmutable, SHA-256, autor y unicidad por documento.
  - `DocumentDownload` como registro de auditoría de cada descarga.
  - Migraciones reversibles `a3b4c5d6e7f8` y `b4c5d6e7f8a9`.
  - Validación de subidas por *magic bytes*, con bloqueo de ejecutables y discrepancias MIME.
  - Almacenamiento local con claves generadas en servidor y volumen Docker persistente.
  - Cinco permisos documentales; el cliente solo lee lo publicado de sus expedientes.
  - La sección `documentos` de la ficha 360º pasa a estar disponible.
### Rules
- Una versión existente nunca se sobrescribe ni se elimina.
- Publicar un documento no concede permiso de descarga.
- Un documento fuera del alcance responde 404, no 403.
### Fixed
- El CLI de bootstrap fallaba con `MissingGreenlet` al asignar el rol del administrador.
- Las colecciones ya cargadas devolvían grafos obsoletos tras crear una versión.
- La descarga devolvía base64 en JSON; ahora responde binario con cabeceras de integridad.
- El volumen de documentos heredaba permisos de root y impedía escribir al usuario no root.
- El bloqueo por palabras `import `/`from ` rechazaba texto legítimo; se usa el shebang.
### Verified
- 211 tests, 85.50% de cobertura, Ruff y mypy strict limpios.
- `upgrade` → `downgrade -2` → `upgrade head` sin errores.
- Flujo HTTP real: versionado, duplicados, ejecutable disfrazado, descarga auditada y 360º.

## [0.6.0] - 2026-09-30
### Added
- **Fase 5 — Agenda, audiencias y vencimientos**:
  - `CalendarEvent` ligado a un expediente con seis tipos de evento.
  - `Hearing` con juzgado, sala, juez, etapa procesal, asistencia y resultado.
  - Migraciones reversibles `e1f2a3b4c5d6` y `f2a3b4c5d6e7`.
  - Vistas día, semana, mes, abogado y expediente con filtros.
  - Ocho permisos de agenda y audiencias.
  - Vencimientos que combinan eventos `vencimiento` y próximas actuaciones.
  - Las secciones `agenda` y `audiencias` de la ficha 360° pasan a estar disponibles.
### Rules
- Una audiencia realizada exige resultado registrado.
- Una audiencia realizada o cancelada no se puede reprogramar.
- Se bloquea el solapamiento: un abogado no puede tener dos audiencias a la vez.
- La reprogramación deja traza y queda reservada al administrador.
### Verified
- 172 tests, 84.65% de cobertura, Ruff y mypy strict limpios en 68 archivos.
- Migraciones: upgrade, downgrade y upgrade hasta `f2a3b4c5d6e7`.
- Ejecución real: evento, audiencia, conflicto detectado, reprogramación y vencimientos.

## [0.5.0] - 2026-09-30
### Added
- **Fase 4 — Actuaciones y timeline**:
  - Modelo `Action` ligado a un expediente con tipo, fecha, resultado y responsable.
  - Próxima acción con su fecha de vencimiento, validada como pareja.
  - Visibilidad `interna`, `equipo` y `publicada`.
  - Migraciones reversibles `c9d0e1f2a3b4` y `d0e1f2a3b4c5`.
  - Cuatro permisos de actuación, incluida la lectura solo de lo publicado.
  - Timeline cronológica por expediente con estado del caso y marca de pendiente.
  - Reporte de próximas acciones vencidas dentro del alcance del usuario.
  - La sección `actuaciones` de la ficha 360° pasa a estar disponible.
### Security
- Las actuaciones heredan el alcance de su expediente: nunca son más visibles.
- El rol `cliente` solo alcanza lo publicado dentro de sus propios expedientes,
  resueltos por `Client.user_id`, y sin posibilidad de ampliar el filtro.
### Verified
- 149 tests, 85.09% de cobertura, Ruff y mypy strict limpios en 62 archivos.
- Migraciones: upgrade, downgrade y upgrade hasta `d0e1f2a3b4c5`.
- Ejecución real: registro de actuaciones, timeline, pendientes y ficha 360°.

## [0.4.0] - 2026-09-30
### Added
- **Fase 3 — Expedientes (núcleo funcional)**:
  - Modelo `Case` con cliente, abogado responsable, área, tipo de proceso,
    jurisdicción, juzgado, radicado, estado, prioridad, fechas, cuantía y notas.
  - Numeración `WA-AAAA-000001` con contador por año protegido con `FOR UPDATE`.
  - `CaseLawyer` con roles responsable y colaborador; cambiar el responsable
    degrada al anterior.
  - `CaseParty` para demandante, demandado, contraparte y tercero.
  - Migraciones reversibles `a7b8c9d0e1f2` y `b8c9d0e1f2a3`.
  - Seis permisos de expediente y división de alcance de lectura.
  - Ficha 360° con colaboradores, partes, historial y secciones pendientes.
  - Baja lógica, historial por campo y filtro `open_only`.
### Security
- Un abogado solo ve expedientes donde es responsable o colaborador.
- Los expedientes fuera de alcance responden 404 para impedir enumeración.
- Cerrar un expediente queda reservado al administrador.

### Verified
- 127 tests, 85.51% de cobertura, Ruff y mypy strict limpios en 56 archivos.
- Migraciones: upgrade, downgrade y upgrade hasta `b8c9d0e1f2a3`.
- Ejecución real: apertura de expedientes numerados, partes, cierre y vista 360°.

## [0.3.0] - 2026-09-30
### Added
- **Fase 2 — Clientes y abogados**:
  - Modelo `Client` para persona natural y jurídica con documento único y soft delete.
  - Modelo `Lawyer` con documento, tarjeta profesional, especialidades, estado y áreas.
  - Catálogo `LegalArea` con 12 áreas jurídicas sembradas.
  - Tabla `ChangeLog` con historial de cambios por campo y usuario responsable.
  - Migraciones reversibles `e5f6a7b8c9d0` y `f6a7b8c9d0e1`.
  - Nuevos permisos `clients:*`, `lawyers:*` y `legal_areas:read`.
  - abogado y asistente leen, crean y actualizan, pero nunca eliminan.
  - Endpoints CRUD de clientes y abogados con permiso explícito por operación.
  - Listados con paginación, búsqueda, filtros y activos por defecto.
  - Historial de modificaciones por cliente y por abogado.
### Fixed
- El middleware de auditoría ya no consume el cuerpo de la petición, lo que provocaba
  `400 There was an error parsing the body` de forma intermitente.
- `AuditLogResponse.entity_id` alineado con la columna UUID, que devolvía 500 al listar auditoría.
- Los errores de validación con `ctx` no serializables ya no convierten un 422 en 500.
- Los errores de dominio en la actualización de abogados devuelven 409 en vez de 500.

### Verified
- 102 tests, 86.14% de cobertura, Ruff y mypy strict limpios en 50 archivos.
- Migraciones: upgrade, downgrade y upgrade hasta `f6a7b8c9d0e1`.
- Ejecución real: alta de clientes y abogados, historial, baja lógica y auditoría.

## [0.2.0] - 2026-09-30
### Added
- **Fase 1 — Seguridad e identidad completa**:
  - Modelos `User`, `Role`, `Permission`, `UserRole`, `RolePermission`, `AuditLog` y `RefreshToken`.
  - Migraciones reversibles `c3d4e5f6a7b8` (sesiones) y `d4e5f6a7b8c9` (semilla RBAC).
  - Matriz de permisos canónica en `app/security/permissions.py`.
  - Dependencia `require_permission` aplicada a cada endpoint administrativo.
  - Endpoints `/api/v1/admin/*` para usuarios, roles, permisos y auditoría.
  - Sesiones de refresh persistentes con rotación, revocación y logout selectivo o total.
  - `GET /auth/me` expone roles y permisos; `/auth/me/sessions` lista sesiones activas.
  - CLI `python -m app.cli.create_admin` que crea o actualiza el administrador inicial.
  - Rate limiting por usuario autenticado o IP, con límites más estrictos en autenticación.
- **Auditoría**: saneado de secretos, derivación correcta de entidad e identificador, y
  fábrica de sesiones inyectable; los fallos de persistencia quedan registrados.
- **Correcciones**: carga explícita del grafo de autorización con `selectinload`,
  `Authorization` leído como cabecera, logout con cuerpo opcional, healthcheck IPv4 del frontend.
- **Tests**: 64 pruebas, 83.89% de cobertura, Ruff y mypy strict limpios en 39 archivos.

### Verified
- Migraciones: upgrade, downgrade y upgrade hasta `d4e5f6a7b8c9`.
- Ejecución real: login, `/me`, sesiones, refresh, logout, CRUD administrativo y auditoría.
- Aislamiento de tests: PostgreSQL efímero con savepoints y rollback por test.

## [0.1.0] - 2026-09-30
### Added
- **Backend**: FastAPI 0.116 application structure with `/api/v1` prefix.
- **Configuration**: Pydantic Settings v2 loading from `.env`.
- **Database**: SQLAlchemy 2 async engine + session factory with asyncpg.
- **Migrations**: Alembic initialized with async support.
- **Health endpoints**: `/api/v1/health/live` (liveness) and `/api/v1/health/ready` (readiness with DB check).
- **Error handling**: Uniform error format `{error: {code, message, details}}` for 404, 422, 503.
- **Tests**: pytest + httpx + pytest-asyncio with 95% coverage (target >=80%).
- **Lint**: Ruff (E, F, I, UP, B, ASYNC, RUF) with line-length 100.
- **Typecheck**: mypy strict mode with pydantic plugin.
- **Dockerfile**: Non-root user, `cap_drop: ALL`, `no-new-privileges:true`.
- **Frontend**: Next.js 16 App Router, React 19, TypeScript strict, Tailwind 4.
- **Status page**: Server-side rendered page at `/` consuming `/api/v1/health/ready` with accessible UI.
- **Frontend quality**: ESLint 9 flat config, `tsc --noEmit`, `next build` successful.
- **Docker Compose**: Three services (postgres:17-alpine, backend, frontend) with healthchecks and dependency ordering.
- **Environment**: `.env.example` documenting all required variables without real secrets.

### Verified
- Backend: pytest (4/4 passed), coverage 95%, Ruff clean, mypy clean.
- Frontend: lint clean, typecheck clean, build clean.
- Docker: `docker compose config` validates.
