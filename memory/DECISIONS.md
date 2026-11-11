# DECISIONS

## ADR-001 — Expediente como núcleo
Todo flujo jurídico converge en el expediente.

## ADR-002 — Evidencia original inmutable
Nunca se reemplaza el archivo original; la compresión produce derivados.

## ADR-003 — Memoria explícita
Los agentes mantienen continuidad mediante archivos de memoria versionados.

## ADR-004 — Matriz RBAC en código con semilla por migración
Los permisos se declaran en `app/security/permissions.py` y la migración `d4e5f6a7b8c9` los siembra.
Motivo: una única fuente de verdad verificable y migraciones reversibles.
Impacto: cambiar la matriz exige siempre una nueva migración.

## ADR-005 — Superusuario salta la matriz de permisos
`is_superuser` permite recuperación administrativa; el resto de roles debe poseer el permiso.
Impacto: auditar cuidadosamente cualquier promoción a superusuario.

## ADR-006 — Sesiones de refresh persistentes con rotación
Cada refresh token se guarda como hash SHA-256 con `jti`; al refrescar se revoca y reemplaza.
Motivo: permite revocación real, detección de reutilización y logout efectivo.
Impacto: `refresh_tokens` crece y requiere limpieza de registros expirados.

## ADR-007 — Auditoría con fábrica de sesiones inyectable
El middleware de auditoría recibe su `session_factory` para poder participar de la transacción
de la petición o de la transacción del test.
Motivo: evita conexiones cross-loop y hace verificable el INSERT real.
Impacto: los tests inyectan la sesión del test mediante `SessionAdapter`.

## ADR-008 — Rate limiting en memoria con límite estricto en autenticación
Límite global por usuario autenticado o IP, y límite más restrictivo en `/auth/login` y `/auth/refresh`.
Motivo: protección local sin infraestructura adicional.
Impacto: obligatoria migración a Redis antes de múltiples workers.

## ADR-009 — Historial de cambios genérico (`change_logs`)
MASTER_PROMPT exige historial de modificaciones; se almacena una vez por campo
(`entity`, `entity_id`, `field_name`, `old_value`, `new_value`, `changed_by`).
Motivo: evita duplicar tablas de historial en cada módulo y permite consultas uniformes.
Impacto: las entidades nuevas deben invocar `record_changes` en sus servicios.

## ADR-010 — El middleware de auditoría nunca lee el cuerpo de la petición
Consumir el stream en un `BaseHTTPMiddleware` puede dejar al manejador sin payload
(observado como `400 There was an error parsing the body`).
Motivo: evitar pérdida silenciosa de datos en producción y filtrado de secretos.
Impacto: el `after` de `audit_logs` guarda método, ruta y estado; el detalle antes/después
vive en `change_logs`, que además registra el usuario responsable.

## ADR-011 — Baja lógica con filtro activo por defecto
Clientes y abogados nunca se eliminan físicamente: `is_active`, `deleted_at`, `deleted_by`.
Los listados devuelven solo registros activos salvo que se solicite `include_inactive`.
Motivo: preservar información jurídica y evitar exposición accidental de registros dados de baja.

## ADR-012 — Numeración de expediente con contador bloqueado por año
`WA-AAAA-000001` se genera desde `case_number_sequences` con `SELECT ... FOR UPDATE`.
Motivo: garantiza unicidad ante aperturas concurrentes sin depender de advisory locks.
Impacto: la apertura de expedientes serializa por año; el número no es reutilizable.

## ADR-013 — Alcance de lectura de expedientes dividido en dos permisos
`cases:read_all` para administrador y asistente, `cases:read_assigned` para abogado.
Motivo: el abogado solo accede a expedientes asignados o autorizados, como exige MASTER_PROMPT.
Impacto: el filtrado ocurre en SQL mediante `scope_filter`; un abogado sin asignaciones ve cero casos.

## ADR-014 — 404 en vez de 403 para expedientes fuera de alcance
Un expediente no accesible responde `404` y no `403`.
Motivo: evita que un usuario pueda enumerar identificadores existentes.
Impacto: el cliente no puede distinguir "no existe" de "sin permiso", decisión deliberada.

## ADR-015 — Cerrar expediente reservado al administrador
`cases:close` no se otorga a abogado ni asistente.
Motivo: el cierre es un acto jurídico con consecuencias procesales.
Impacto: el asistente puede abrir y actualizar, pero no cerrar.

## ADR-016 — Las actuaciones heredan el alcance de su expediente
Una actuación nunca es más visible que el expediente que la contiene; el filtro se
aplica sobre los expedientes visibles del usuario.
Motivo: evita fugas por autorización inconsistente entre módulos.
Impacto: toda operación sobre actuaciones reutiliza `CaseService.can_view`.

## ADR-017 — Visibilidad de actuaciones en tres niveles
`interna`, `equipo` y `publicada`. El personal con `actions:read` ve los tres; el
cliente solo `publicada`, y solo dentro de sus propios expedientes vía `Client.user_id`.
Motivo: MASTER_PROMPT exige que el cliente solo vea lo publicado y sin acceso cruzado.
Impacto: un cliente que pide `visibility=interna` obtiene una lista vacía, no un 403,
para no revelar la existencia de información interna.

## ADR-018 — Todo evento de agenda pertenece a un expediente
`calendar_events.case_id` es obligatorio.
Motivo: hace el alcance de acceso inequívoco y evita eventos huérfanos sin dueño.
Impacto: los recordatorios personales sin expediente no son posibles en V1; si hacen
falta, requieren un modelo aparte con su propia política de acceso.

## ADR-019 — Audiencias con reglas de integridad propias
Una audiencia realizada exige resultado, no se reprograma si está realizada o
cancelada, y no se solapa con otro evento del mismo abogado.
Motivo: son errores con consecuencias procesales reales.
Impacto: el alta y la reprogramación devuelven 409 en esos casos.

## ADR-020 — La reprogramación de audiencias es exclusiva del administrador
`hearings:reschedule` no se otorga a abogado ni asistente.
Motivo: la fecha la dispone el juzgado, no la firma.
Impacto: el personal registra el resultado pero no mueve la fecha.

## ADR-021 — Los vencimientos no aplican límite inferior de fecha
`/calendar/deadlines` incluye eventos y actuaciones ya vencidos.
Motivo: lo vencido es exactamente lo que la firma necesita ver primero.
Impacto: el endpoint marca `overdue` en cada elemento.

## ADR-022 — Versionado documental con contenido inmutable
Cada carga crea una `document_version` nueva; el contenido anterior nunca se sobrescribe ni se borra.
Motivo: es la regla central de MASTER_PROMPT sobre documentos y coincide con ADR-002.
Impacto: el almacenamiento crece sin límite y necesita una política de retención; solo una
versión puede ser `is_current` a la vez.

## ADR-023 — Tipo de archivo detectado por contenido
La extensión y el `Content-Type` declarado solo sirven para detectar discrepancias; el tipo
almacenado se decide por *magic bytes*.
Motivo: un `.pdf` renombrado no puede convertirse en un vector de ejecución por su nombre.
Impacto: se rechaza lo que no se puede identificar, salvo texto plano UTF-8. La detección es
por firmas para evitar depender de `libmagic`; Fase 7 puede migrar a `python-magic`.

## ADR-024 — Claves de almacenamiento generadas en el servidor
`storage_key` se construye con UUID y bytes aleatorios; el nombre enviado por el usuario se
conserva solo como metadato.
Motivo: el nombre de archivo es entrada no confiable y no debe influir en la ruta en disco.
Impacto: los archivos en disco no son legibles por nombre y su localización depende de la BD.

## ADR-025 — Publicar no equivale a autorizar la descarga
El rol `cliente` puede ver que existe un documento publicado en su expediente, pero
`documents:download` no forma parte de su matriz.
Motivo: separar la visibilidad del expediente del acceso al contenido del archivo.
Impacto: si el negocio exige que el cliente baje el PDF, hay que otorgarse un permiso explícito
y auditado, no ampliar `read_published`.

## ADR-026 — Almacenamiento local detrás de una clase única
`LocalStorage` encapsula lectura, escritura y borrado; MinIO/S3 se sustituye por otra
implementación sin tocar servicios ni endpoints.
Motivo: el almacenamiento local no sirve para producción multi réplica, pero no debe
contaminar el dominio.
Impacto: la deprecación de Fase 6 es deliberada y está anotada como deuda técnica.

## ADR-027 — El dominio depende de una interfaz, no de un backend
`StorageBackend` en `app/services/storage.py` es el único contrato; `LocalStorage` y
`S3Storage` no se importan entre sí.
Motivo: mantener el almacenamiento como decisión de infraestructura y poder cambiarla sin
tocar servicios ni endpoints.
Impacto: todos los métodos de E/S son `async` incluso en local, para que el dominio nunca
ramifique según el backend. `boto3` es síncrono y se ejecuta con
`anyio.to_thread.run_sync`: bloquear el event loop en una ida y vuelta de red detendría
todas las peticiones concurrentes.

## ADR-028 — La retención de versiones nunca elimina contenido
`RetentionService` solo mueve versiones superadas al tier `archive`. No existe ninguna
ruta de código que llame a `delete` desde la política, y hay un test que falla si alguien
la introduce.
Motivo: PROJECT_RULES regla 5 prohíbe eliminar registros jurídicos, y perder una versión
superada de un contrato firmado es un problema peor que una factura de almacenamiento.
Impacto: el almacenamiento crece de forma indefinida. El ahorro viene del tier, no del
borrado. Una versión archivada sigue siendo descargable durante toda su vida.

## ADR-029 — El tier de archivo debe seguir siendo legible de inmediato
La clase de almacenamiento por defecto es `STANDARD_IA`. `GLACIER`, `DEEP_ARCHIVE` y
`GLACIER_IR` se rechazan en el constructor de `S3Storage`.
Motivo: esas clases dejan el objeto ilegible hasta completar una restauración, lo que
rompería la garantía de que cualquier versión puede descargarse en cualquier momento.
Impacto: el ahorro es menor que con Glacier. A cambio no existe ninguna ventana en la que
un documento archivado sea inaccesible. Si algún día se acepta esa ventana, hace falta un
flujo de restauración completo.

## ADR-030 — La base de datos es la fuente de verdad del tier
El tier se registra siempre en `document_versions.tier`. La clase de almacenamiento remota
es un reflejo del mismo hecho.
Motivo: MinIO en un solo nodo no puede transicionar clases de almacenamiento, solo con
erasure coding. Sin la columna en base de datos, el tier quedaría invisible en el entorno
de desarrollo y en cualquier despliegue sin ese soporte.
Impacto: `native_tier_applied` devuelve `false` cuando el backend solo admite tier lógico.
No se debe prometer un ahorro que el backend no aplica.

## ADR-031 — La retención legal congela la política
`documents.legal_hold` impide mover cualquier versión de ese documento mientras esté
activa. Exige un motivo y queda en el historial.
Motivo: un requerimiento judicial o una disputa suspende el tratamiento automático del
expediente entero, no de un documento suelto.
Impacto: un documento con retención legal activa nunca se archiva automáticamente. Levantar
la retención es una decisión explícita del administrador y queda auditada.

## ADR-032 — Los cambios automáticos se explican
`change_logs.change_reason` registra por qué ocurrió un cambio que nadie ordenó. La
retención escribe `document_retention` / `tier` con el motivo y la antigüedad.
Motivo: sin motivo, una traza de meses atrás no permite responder por qué una versión está
archivada.
Impacto: `ChangeLog` gana una columna nullable, y todo consumidor del historial debe
saber que puede ser nula.

## ADR-033 — Un predicado sobre `cases` nunca se aplica a una entidad hija sin unir
`scope_filter` produce condiciones sobre `cases`. Para Consultar una entidad con
`case_id` se usa `case_scoped(columna_case_id, clausula)`, que la envuelve en
`subconsulta(select(Case.id).where(clausula))`.
Motivo: aplicada sin unir, SQLAlchemy añade `cases` como producto cartesiano. El
predicado se cumple si *cualquier* caso de la tabla coincide, el filtro se convierte en un
no-op y se filtran datos de otros expedientes. Ocurrió en agenda y audiencias, y ningún
test lo detectó porque ninguno afirmaba que un evento de un expediente no asignado
estuviera oculto.
Impacto: PostgreSQL lo planifica como semijoin. Es un patrón que cualquier servicio nuevo
que herede el alcance de un expediente debe seguir.

## ADR-034 — Cambiar el backend de almacenamiento no mueve bytes
`STORAGE_BACKEND=s3` no reubica nada: la `storage_key` guardada seguiría apuntando al disco
local. `python -m app.cli.import_documents_to_s3` copia, verifica el SHA-256 de lo copiado
y solo entonces repunta la fila.
Motivo: sin este paso, cambiar la variable de entorno en producción deja inaccesible todo
el histórico documental.
Impacto: la migración es una operación explícita, dry-run por defecto e idempotente.

## ADR-035 — Base de datos primero, objetos después
El respaldo toma PostgreSQL antes que el almacenamiento de objetos.
Motivo: el contenido se escribe antes de que su fila haga commit, así que un objeto puede
existir sin fila pero nunca al revés. Respaldar la base primero y los objetos después solo
puede dejar un objeto de más en la copia; al revés produciría una base restaurable con
filas apuntando a objetos ausentes.
Impacto: el orden está escrito en `scripts/backup.sh` con su porqué, para que nadie lo
"optimice".

## ADR-036 — El verificador de integridad no repara
`IntegrityService` no tiene ruta de escritura ni de borrado hacia contenido documental, y hay
un test que falla si alguien introduce una.
Motivo: un hash que no coincide es un hecho que hay que documentar, no un problema que
"arreglar". Sobrescribir un documento corrupto destruye la prueba de qué se perdió.
Impacto: la recuperación es una decisión humana que restaura desde una copia. El
verificador informa y sale con código distinto de cero.

## ADR-037 — Una copia sin restaurar no es un respaldo
`verify_backup` restaura el volcado en una base de datos temporal, la inspecciona y la
borra. Comprueba el digest, la revisión de Alembic, la presencia de tablas críticas y el
recuento de filas.
Motivo: `MASTER_PROMPT` sección 44 exige que la restauración esté documentada y probada. Un
dump cuyo tamaño parece correcto no demuestra nada.
Impacto: cada respaldo cuesta el doble que un `pg_dump`. Es el coste que hace que un
respaldo sea un respaldo. La base de producción nunca se toca.

## ADR-038 — La verificación es de solo lectura y siempre queda registrada
`integrity_scans` e `integrity_findings` guardan cada ejecución. Solo se persisten los
problemas, no los aciertos.
Motivo: una firma tiene que poder demostrar que la verificación ocurrió, cuándo y con qué
resultado. Guardar los aciertos llenaría la tabla sin aportar nada.
Impacto: un escaneo limpio no genera filas de hallazgo; la historia se consulta en
`GET /api/v1/documents/integrity/latest`.

## ADR-039 — El modo muestra existe porque la verificación completa es cara
`full` descarga todos los bytes del bucket. `sample` toma un subconjunto determinista de las
versiones más recientes.
Motivo: una nightly no puede pagar la lectura completa del bucket cada día, y una auditoría
mensual sí.
Impacto: la muestra es reproducible a propósito. Dos ejecuciones distintas pueden
compararse, que es lo que hace útil un informe de integridad.

## ADR-040 — La interfaz de almacenamiento incluye listar y consultar tamaño
`iter_keys` y `stat` se añadieron a `StorageBackend`.
Motivo: sin listar no se puede demostrar que no se ha añadido nada al bucket, y sin `stat`
no se puede detectar un archivo truncado sin descargarlo. Ambos hacen falta para una
verificación que valga.
Impacto: los objetos parciales de una escritura interrumpida se ignoran al listar, para
que no parezcan objetos intrusos.

## ADR-041 — Una subida exitosa no es una copia válida
`RemoteBackup.push_file` relee el objeto subido y compara su SHA-256 antes de informarlo
como correcto.
Motivo: `mc mirror` y `put_object` devuelven éxito si los bytes salieron del proceso, no
si llegaron intactos. Un corte de red a mitad de la subida o un bucket mal configurado se
descubren el día de la restauración, que es el peor momento.
Impacto: la subida cuesta el doble de E/S. `BACKUP_REMOTE_VERIFY_UPLOAD=false` existe
para quien lo acepte, y la salida declara explícitamente que ese modo es más débil.
Sustituye a `mc mirror`, que además no se podía probar en este entorno.

## ADR-042 — Sin destino externo, avisar; con destino obligatorio, fallar
`scripts/backup.sh` avisa en tres líneas cuando `BACKUP_REMOTE_ENABLED` está apagado y
continúa, porque la copia local sigue siendo válida. `BACKUP_REMOTE=required` convierte
el aviso en fallo.
Motivo: bloquear todas las ejecuciones hasta que alguien configure el destino hace que
la gente desactive la comprobación, que es peor que un aviso ruidoso.
Impacto: la ausencia de copia externa es visible en cada ejecución, pero no impide
respaldar.

## ADR-043 — La retención remota solo toca lo que este módulo escribió
`prune` exige la marca `wabogados-backup=1` en los metadatos y rechaza `keep=0`.
Motivo: un bucket compartido puede contener objetos de otro sistema. Borrarlos por antigüedad
sería un dato ajeno destruido.
Impacto: los objetos sin marca se acumulan sin que nadie los limpie; es un coste menor que
el riesgo de borrar lo que no es nuestro.

## ADR-044 — Una descarga no verificada no se escribe
`RemoteBackup.fetch` compara el digest **antes** de escribir el archivo en disco.
Motivo: un dump corrupto en disco puede restaurar sin darse cuenta, y el nombre del
archivo sugiere que es bueno.
Impacto: una copia con digest incorrecto no deja rastro en el sistema de ficheros, solo el
error. Hay un test que lo comprueba.

## ADR-045 — Un permiso sin alcance es una fuga
Toda lectura de una evidencia por identificador exige visibilidad **y** alcance de expediente,
y el alcance viaja dentro de la consulta.
Motivo: `get_visible_evidence` comprobaba solo la visibilidad. Un abogado con `evidences:view`
sin expedientes asignados podía leer por UUID la evidencia de cualquier expediente. Es la
tercera vez que este patrón aparece en el proyecto (agenda, hearings, evidencias).
Impacto: el alcance es un parámetro obligatorio del método de servicio, no una responsabilidad
de cada endpoint. Un endpoint nuevo no puede olvidarlo sin que mypy falle.

## ADR-046 — Un PDF firmado se copia, no se optimiza
`optimise_pdf` devuelve los bytes originales cuando detecta una firma digital.
Motivo: reescribir un PDF firmado invalida su firma. Una firma rota en una evidencia es peor
que un archivo más grande, y es un problema que el cliente descubriría tarde.
Impacto: un PDF firmado conserva su tamaño original. A cambio el derivado es idéntico al
original, lo cual es exactamente lo que un firmado necesita.

## ADR-047 — La inmutabilidad se expresa, no se valida
`MUTABLE_FIELDS` es la lista de lo que un usuario puede cambiar, y los schemas de actualización
no tienen campo para el hash, la fecha de carga ni la clave de almacenamiento.
Motivo: una validación que se pueda saltar no es una garantía. Si el campo no existe en la API,
no hay forma de cambiarlo.
Impacto: añadir un campo inmutable a un schema de entrada es un error visible en revisión.

## ADR-048 — Un solo original, garantizado por la base de datos
`uq_evidence_single_original (evidence_id, is_original)`.
Motivo: tener dos originales de la misma evidencia es un error jurídico, no un bug de aplicación.
Impacto: la base lo impide aunque una futura ruta de código lo intente.

## ADR-049 — Los archivos grandes van a una cola, no a un hilo en la petición
Superar `INLINE_LIMIT_BYTES` registra un trabajo y devuelve. `evidence_worker` lo reclama con
`FOR UPDATE SKIP LOCKED`.
Motivo: `MASTER_PROMPT` sección 27 prohíbe bloquear peticiones HTTP pesadas. El bloqueo de
filas también impide que dos workers tomen el mismo trabajo.
Impacto: en desarrollo no hay planificador ejecutando el worker. El CLI existe y funciona;
falta el cron o el servicio, y está anotado como pendiente.

## ADR-050 — La validación de evidencia detecta políglotos y bombas
Un archivo que encaja en varios formatos se rechaza, y las dimensiones de una imagen se
comprueban antes de decodificarla.
Motivo: dos filtros de contenido pueden discrepar sobre un polígloto y uno de los dos está
equivocado. Un PNG de 40 kB que declara 40000x40000 píxeles agota la memoria al abrirse.
Impacto: se rechazan archivos legítimos en formats que no se pueden identificar de forma
inequívoca. Preferible a admitir un archivo que dos motores interpretarán de forma distinta.

## ADR-051 — No existe borrado físico; se desactiva, se cierra o se archiva
El encargo pedía el CRUD completo, incluida la eliminación. `PROJECT_RULES.md`
regla 5 dice: *no eliminar registros jurídicos físicamente*. Preguntado, la firma
eligió **desactivar / archivar**.
Motivo: un expediente con documentos, evidencias, actuaciones y audiencias es un
registro jurídico; borrarlo destruye cadena de custodia. Un cliente o abogado
puede estar citado en un expediente ya cerrado, y borrarlo deja una referencia
rota.
Impacto:
- El `DELETE /clients/{id}` y `DELETE /lawyers/{id}` del backend **no borran**: son
  desactivaciones lógicas que conservan expedientes, documentos e historial.
- Un cliente desactivado sale del listado por defecto y solo reaparece con
  «incluir inactivos»; sigue siendo editable y su ficha sigue abierta.
- Un expediente se cierra con `POST /close` y **no se puede reabrir** desde la
  interfaz, porque la API tampoco lo permite. Si el cierre fue un error, el camino
  es un registro nuevo: reabrir reescribiría su historia, que es justo lo que un
  expediente debe impedir.
- Si en el futuro se exige el borrado físico, hay que anular la regla 5 de
  `PROJECT_RULES.md` y `MASTER_PROMPT.md` **por escrito**, y avisar del riesgo.

## ADR-052 — El menú no filtra por permiso cuando la autorización es por alcance
`lib/admin-nav.ts` oculta un módulo solo si su `permission` es un permiso que la
persona tiene. Expedientes no lleva permiso: el backend lo autoriza por alcance
(`cases:read_all`, `cases:read_assigned`, `cases:read_published`) y `GET
/cases/{id}` resuelve la visibilidad con `get_user_scope`.
Motivo: un primer intento puso `cases:read`, un nombre de permiso que el proyecto
no tiene. El módulo **desapareció del menú para todo el mundo**: una puerta
construida con una llave que nadie tiene cierra igual que una cerradura rota, y
ambas se ven igual.
Impacto: antes de escribir un `permission` hay que confirmar que el nombre existe
en la tabla de permisos. Si la autorización es por alcance, el módulo se deja
visible y quien filtra es la API, que ya lo hace.

## ADR-053 — Las acciones de la fila se confirman, pero están en la fila
El botón de desactivar vivía solo en la ficha, con el argumento de que veinte
filas con veinte botones son veinte maneras de destruir algo. La firma pidió el CRUD
completo desde el listado, y el argumento se respondió con el diálogo de
confirmación, que se conserva: el botón abre un diálogo que dice qué pasa y por qué
nada se borra, y el botón destructivo nunca recibe el foco inicial.
Motivo: la preocupación era la destrucción accidental, y el diálogo la contiene. La
preocupación no era la visibilidad del botón.
Impacto: `DeactivateButton` y `CloseCaseButton` aceptan `variant` (`quiet` dentro de
la fila) y `idPrefix` (`close-<case_number>`), porque el diálogo de cierre se
monta una vez por expediente abierto y un prefijo fijo repetiría los ids. Y el
comentario del código que sostenía la decisión contraria quedó actualizado para
que nadie lo lea como norma vigente.
## ADR-054 - Centro multimedia: se prepara el diseño, no se construye el módulo

`MASTER_PROMPT.md` lista «Centro multimedia» bajo **«Fases futuras, NO implementar
aún»** y pide solo que «la arquitectura debe quedar preparada para integrarlos
posteriormente». La hoja de ruta lo sitúa como **V4 — «Videos y biblioteca»**.
Pedido expresamente por la dirección, se decidió escribir esta decisión y **no** el
módulo.

Motivo: hay dos formas de leer «preparada» y una es construirlo a medias. Un
endpoint que devuelve 501, una migración con la tabla vacía o un permiso
sembrado y sin uso no es arquitectura preparada: es deuda con forma de
funcionalidad, y este proyecto ya ha pagado por esa interpretación dos veces (un
endpoint que existía y nunca se expos, y un formulario que decía enviar y no
enviaba). La preparación que sí sirve es saber **qué se va a decidir y con qué
restricciones**, escrito donde se lee.

### Lo que existe hoy y que V4 reutiliza

- **Almacenamiento por niveles**: `StorageTier.HOT`/`ARCHIVE` con `set_tier`,
  verificación por digest al escribir y al mover (ADR-040, ADR-041, ADR-042,
  ADR-043). Una biblioteca de vídeo es, ante todo, un problema de niveles.
- **Motor de evidencias**: original inmutable, derivados con su propio tipo,
  cola para archivos grandes en lugar de un hilo en la petición (ADR-049), y
  retención que nunca borra contenido (regla 5 de `PROJECT_RULES.md`).
- **Convención de permisos** `recurso:acción`, con el renombrado ya hecho de
  `evidencias.view` a `evidences:view` al pasar a nombres en inglés.
- **Trazabilidad**: `change_logs` con antes y después por campo, middleware de
  auditoría para toda escritura, y la convención de desactivar en lugar de
  borrar (ADR-051).
- **Cáscara de administración**: `admin-nav.ts` con tres estados y la pantalla
  `modulo/[slug]`, que admite un módulo y declara lo que le falta.

### Lo que NO existe y por eso V4 no es una pantalla

1. **No se acepta vídeo ni audio en ninguna parte.** `EVIDENCE_MIME_TYPES` es
   exactamente `application/pdf`, `image/png`, `image/jpeg`, y la sección 17 del
   encargo —obligatoria desde V1— enumera solo esos formatos. Ampliarlo es una
   decisión sobre el motor de evidencias, no sobre un centro multimedia.
2. **No hay transcodificación.** `evidence_processing.py` trabaja con Pillow;
   no hay `ffmpeg`, ni worker de vídeo, ni política de bitrate, resolución o
   códec. `app/workers/` está vacío salvo `.gitkeep`.
3. **No existe el concepto de biblioteca.** Toda evidencia pertenece a un
   expediente y se resuelve con `case_scoped(scope_filter(...))`. Una colección
   de la firma es otro alcance, y por ADR-045 un permiso sin alcance es una
   fuga: el diseño de permisos de V4 no puede ser un `multimedia:read` y ya.
4. **No hay modelo de dominio.** Ni `media`, ni `collection`, ni etiquetas, ni
   gestor de derechos, ni una relación con expedientes o clientes que lo justifique.

### Decisiones que V4 tendrá que tomar, y con qué restricciones

- **Alcance**: biblioteca de la firma, vídeos como tipo de evidencia, o ambas
  cosas con alcances separados. La opción «ambas» es la única que no autoriza un
  permiso único, porque son dos permisos con dos alcances.
- **Formatos**: cualquier ampliación empieza por una sección 17 que hoy cierra la
  puerta a `video/*` y `audio/*`.
- **Derivados**: un vídeo produce más de un derivado (miniatura, previsualización
  con `Range`), y el modelo actual de `DerivativeType` tiene un tipo por salida.
- **Retención**: el vídeo es el primer formato cuyo peso no acorta una retención por
  días. La regla 5 impide borrar, así que la pregunta es de niveles y de coste, no
  de purga.
- **Descarga**: hoy la descarga de documentos fluye por un route handler para no
  exponer el token. El vídeo por HTTP necesita `Range`; esa ruta no existe.

### Impacto en el código

Ninguno. Este ADR no crea migraciones, ni rutas, ni permisos, ni pantallas, y
el módulo sigue `planned` en el menú, inerte y con su motivo a la vista. Lo
único que se añade es la descripción del alcance en la ficha del módulo, para
que la dirección vea qué se decidió y no una página que se limita a decir que
no está. Cuando V4 se autorice, este documento es el punto de partida y su
primera tarea es decidir el alcance, no escribir la tabla.
## ADR-055 - Se construye el centro multimedia (V4); el brief queda anulado por la dirección

`MASTER_PROMPT.md` список el Centro multimedia bajo «Fases futuras, NO implementar
aún» y pidió solo que la arquitectura quedara preparada. **ADR-054** escribió esa
preparación. La dirección, vista la decisión, ordenó construir el módulo.

Se registra el cambio porque la instrucción anulada está en el documento rector y
en ninguna parte del código queda rastro de que dejó de aplicar: dentro de seis
meses, un lector encontrará «NO implementar aún» junto a un módulo en producción y
no sabrá cuál de las dos cosas manda. Este ADR es el que responde, y la regla que
lo acompaña es que una anulación se escribe donde estaba la norma, no solo donde se
implementa.

### El alcance, que era la primera tarea pendiente

ADR-054 cerró diciendo que lo primero era **decidir el alcance, no escribir la
tabla**. Se decidió esto:

- **Una biblioteca interna de la firma.** Grabaciones, fotografías, audio y
  documentos propios. No es un módulo de evidencias y no se publica en el portal.
- **Vídeo como material de la biblioteca, no como tipo de evidencia.** La sección
  17 enumera los formatos del motor de evidencias y no incluye `video/*`; abrir
  esa puerta es una decisión sobre el contrato de un registro jurídico y no sobre
  este módulo. `EVIDENCE_MIME_TYPES` sigue intacto.
- **Un solo archivo por recurso, reemplazable.** El archivo se retira al
  sustituirlo porque la fila conserva su historial y solo se va el objeto
  anterior; la fila nunca se borra (ADR-051).

### Por qué esto no debilita la evidencia

Es la objeción que había que responder antes de escribir una línea. La separación
es total y verificable: `media_items` no tiene inmutabilidad, ni derivados, ni
cadena de custodia, ni `legal_hold`, y su clave de almacenamiento es un UUID
generado. Un material que pertenece a un expediente se sigue registrando como
evidencia y llega por su camino. Lo que se archiva aquí es material de trabajo, y
la ficha de la biblioteca lo dice en pantalla para que nadie lo confunda.

### Las tres decisiones quetook el código y conviene no perder

1. **El tipo lo deciden los bytes.** `kind` decide si el navegador ofrece un
   `<video>`, así que se detecta por la cabecera y no se acepta del cliente. Un
   MP4 renombrado a `.jpg` se archiva como vídeo, y hay una prueba que lo
   comprueba. `RIFF` se resuelve por su tipo en el offset 8 porque es un
   contenedor: tomarlo por audio archivaría como sonido cada `.webp`.
2. **Registrar y subir son dos llamadas.** Un recurso puede existir sin archivo: la
   secretaria lo registra y el archivo llega después. `has_file` separa los dos
   estados, que son normales los dos. Una sola llamada que llevara ambos tendría
   que inventar qué hacer con la fila cuando la subida falla a medias, y la fila es
   la parte que importa.
3. **`DELETE` desactiva y no borra, archivo incluido.** Una fila desactivada sin
   sus bytes no se podría reactivar, que es justo la razón por la que las filas se
   desactivan en lugar de eliminarse. El diálogo dice qué sobrevive antes de
   preguntar.

### Lo que este módulo no tiene, y sigue pendiente

- **Sin transcodificación.** El navegador reproduce el original. Un códec que el
  navegador no reproduce no se ve, y no hay conversión que lo arregle.
- **Sin duración medida.** `duration_seconds` existe y es `null`: el navegador la
  conoce al reproducir, pero escribirla aquí desde el cliente sería un dato
  inventado. Se rellena cuando algo mida.
- **Sin cola de subida.** Hay un tope (`max_media_bytes`, 500 MB) y por encima de
  él no hay nada. ADR-049 manda los archivos grandes a un worker, y ese worker
  todavía no existe.
- **Sin miniaturas ni derivados.** Una biblioteca sin carátulas se navera con
  texto; es una limitación, no una decisión.

### Impacto en el código

Dominio nuevo (`MediaItem`, dos revisiones de Alembic), seis permisos `media:*`
sembrados, servicio, API con `Range`, pantalla `/admin/multimedia`, una ruta de
streaming propia en lugar de ampliar el proxy compartido, y el menú pasando de
`planned` a `ready`. Los clientes siguen sin ver nada: el rol `cliente` no tiene
ningún permiso de `media`, y eso está fijado por una prueba.
## ADR-056 - Se construye facturación (V3); el brief queda anulado por la dirección

`MASTER_PROMPT.md` sitúa facturación entre las «Fases futuras, NO implementar aún».
La dirección ordenó construirla, igual que hizo con el centro multimedia
(ADR-055). Se escribe aquí, y no solo en el código, porque dentro de seis meses un
lector encontrará «NO implementar aún» junto a un módulo en producción y no sabrá
cuál manda. La regla que acompaña a las dos anulaciones es que **una instrucción
anulada se corrige donde estaba escrita**.

### Qué es una factura aquí, y qué no

No es un registro jurídico y no se borra (ADR-051): una factura emitida se anula
con motivo y conserva su número, que es lo que un contador necesita para poder
explicar en una auditoría por qué existe una factura anulada. Anular y borrar son
cosas distintas, y confirlas es como se pierde un número ya declarado.

Los importes **se calculan en el servidor**. El cliente envía conceptos (descripción,
cantidad, precio unitario) y nunca un total: un total que acepta el navegador es un
total que alguien puede escribir a mano. Los tres niveles se derivan con `Decimal`
y columnas `Numeric(14, 2)`, nunca con coma flotante, porque `0.1 + 0.2` en binario
no es `0.3` y una factura que no cuadra por centavos no se usa.

El saldo también es derivado: `total - SUM(pagos)`. Que una factura figure como
`pagada` lo decide un pago registrado, no un estado que alguien escriba a mano.

### El impuesto no se inventa

`tax_rate` existe y **vale 0 por defecto**. El 19 % es un dato que tiene que traer
quien conoce la obligación tributaria del cliente, y escribirlo en una migración
sería inventar una posición fiscal en nombre de la firma. La pantalla lo pide
explícitamente y explica que 0 significa «sin impuesto aplicado», no «IVA
calculado en cero».

### Numeración

`FE-AAAA-NNNNNN`, un contador por año respaldado por la base de datos, igual que
`CaseNumberSequence` hace con los expedientes (`WA-AAAA-000001`). No se numera en
el servidor de aplicación: dos peticiones simultáneas deben recibir números
distintos, y una tabla con `UPDATE ... RETURNING` lo garantiza sin aplikasi.

### Quién puede hacer qué

- `abogado` y `asistente`: leer, crear y editar facturas **en borrador**, registrar
  pagos. Nunca anular.
- `administrador`: todo, incluida la anulación y el cambio de impuesto.

La anulación se separa del resto por la misma razón que en el resto del proyecto:
es el eje que nadie puede deshacer desde la pantalla, así que no se deja en manos
de quien la usa a diario. Y el rol `cliente` no recibe nada: una factura interna no
se publica en el portal, y eso está fijado por una prueba.

### Impacto

Tres tablas (`invoices`, `invoice_lines`, `payments`), permisos `invoices:*` y
`payments:*` sembrados, servicio con totales derivados, API, pantalla
`/admin/facturacion` y el menú pasando de `planned` a `ready`.
## ADR-057 - IA jurídica: se construye la búsqueda y el resumen, no el chatbot

`MASTER_PROMPT.md` situaba la IA jurídica entre las «Fases futuras, NO implementar
aún» y la hoja de ruta la describe como «RAG, resumen, análisis y generación
asistida». La dirección ordenó construirla.

La primera decisión es qué significa eso aquí, y no admite la lectura obvia. Este
proyecto **no tiene proveedor de lenguaje**: no hay clave, ni modelo, ni
embeddings, ni cola, ni un solo punto donde un texto generado entre al sistema. La
pregunta útil no es «cómo llamo a un modelo» sino **qué es verdad sin él**.

### Lo que se construye, que es verdadero y verificable

1. **Búsqueda sobre el material de la firma.** El centro multimedia que se acaba
   de construir clasifica material; la agenda, los expedientes y los documentos ya
   existen. Un índice **léxico** —PostgreSQL, sin embeddings— que devuelve
   coincidencias reales y explicables. Es la mitad de recuperación del RAG, y esa
   mitad no necesita un modelo.
2. **Resúmenes extractivos.** Se eligen las frases más representativas del texto y
   se etiquetan como **extractivos**, nunca como prosa generada. Un resumen que roba
   las frases del documento es verificable contra él; uno que las reescribe no lo
   es, y en un expediente la diferencia es la que separa un resumen útil de una
   suposición.
3. **Un asistente que declara que no hay proveedor.** En vez de un cuadro de texto
   que promete análisis, la pantalla dice qué falta y por qué: sin clave de API no
   hay nada que invocar, y un botón que devuelve texto inventado es peor que un
   botón ausente.

### Lo que no se construye, y por qué queda escrito

- **Generación assistida y análisis.** Requieren un modelo. La costura queda
  documentada —un único adaptador, y la pantalla lo detecta— para que activarla sea
  escribir un proveedor, no rediseñar el módulo.
- **Embeddings y búsqueda vectorial.** No hay dónde calcularlos ni dónde
  almacenarlos. Un índice léxico con `ts_rank` responde la pregunta que hace la
  gente en una firma («¿en qué expediente se justifica esto?») sin una
  infraestructura que no existe.

### El riesgo que este módulo sí tiene, y que se lee en pantalla

Una búsqueda que devuelve «parecido» puede devolver material **de otro cliente** si
no se filtra por alcance. Por eso las búsquedas heredan el `case_scoped` del módulo
que las alimenta y el rol `cliente` no tiene **ningún** permiso aquí: el índice
devuelve lo que la persona ya podía ver por otra vía, nunca más. Es la misma
disciplina de ADR-045, y está fijada por pruebas.

### Impacto

Un dominio de índice y resumen, permisos `ai:*`, API con la búsqueda y el resumen,
la pantalla `/admin/ia-juridica` con la declaración de que no hay proveedor, y el
menú pasando de `planned` a `ready`. Ninguna migración añade columna de proveedor:
la configuración se lee del entorno y su ausencia **es** la respuesta.

## ADR-058 - El arranque exige que el bucket exista y tenga versionado

`S3Storage.enable_versioning()` existía y estaba probado desde la fase de
almacenamiento, pero **nada lo llamaba**: el bucket se creaba si hacía falta y ya.
Un objeto sobrescrito por un error no tenía segunda oportunidad, y el defecto no
aparecía en ninguna prueba.


La decisión es que el arranque **falla**. Con `STORAGE_BACKEND=s3`, el lifespan
comprueba que el bucket exista —o lo crea solo si `S3_CREATE_BUCKET=true`, que en
producción debe ser `false` porque el bucket se aprovisiona, no se adivina— y exige
que el versionado quede habilitado. Si cualquiera de las dos operaciones falla, la
API no arranca.

Se eligió fallar en vez de avisar porque el aviso se lee una vez y el proceso
sigue aceptando documentos en un bucket donde un borrado es irrecuperable. El
coste es que un bucket mal configurado detiene el servicio: es el precio de que
la protección no sea opcional.

`initialize_storage` vive en `app/services/storage.py` y es el mismo punto por el
que `build_storage` decide el backend, para que no exista una forma de arrancar sin
pasar por la comprobación.

### Impacto

La verificación ocurre en el lifespan, no en cada escritura: versionar el bucket es
una propiedad del bucket, y comprobarla por operación costaría una llamada de red
en cada subida. Veintiuna pruebas cubren el arranque, incluido el caso que obliga a
fallar cuando el bucket no existe.

## ADR-059 - El worker de evidencias es un servicio dedicado, no un worker más

`evidence_worker` existía como CLI y lo reclamaba con `FOR UPDATE SKIP LOCKED`, pero
nada lo ejecutaba: los archivos de más de 5 MB se quedaban en `queued` para siempre
y nadie lo notaba.

La tentación era ejecutar el worker dentro del backend. Se descartó por una razón
concreta: **el rate limiter vive en memoria**, así que cada proceso API nuevo
multiplica el límite por usuario. Añadir un worker HTTP habría empeorado la
deuda que ya estaba escrita.

Se añade por tanto un servicio de Compose, `evidence-worker`, que corre el mismo
CLI con `--loop`, comparte base y volumen con la API y reinicia con
`unless-stopped`. Es un proceso que no habla HTTP, así que no añade superficie de
ataque ni estado de limitador.

### Lo que sigue en pie

El bloqueo por filas sigue siendo lo que impide que dos workers tomen el mismo
trabajo, así que añadir una segunda réplica es seguro cuando haga falta. Y en un
despliegue que no sea Compose, la obligación es la misma: un proceso de larga
duración con `--loop`.


## ADR-060 - Cerrar sesión revoca la sesión en el servidor

`signOut` borraba las cookies y nada más. El token de refresco vivía **siete días**
en la base, así que una sesión «cerrada» seguía acuñando tokens de acceso: un
`httpOnly` copiado antes del cierre, o un token filtrado por otro lado, seguía
sirviendo hasta una semana después.

El código lo justificaba, y el motivo era **falso**. Decía que la alternativa era
una llamada `beforeunload` que los navegadores cancelan «tan a menudo como la
honran». Un Server Action no es eso: es una petición que el servidor espera antes de
redirigir, así que no hay nada que cancelar. La razón escrita hacía la decisión
parecer inevitable cuando no lo era.

La corrección llama a `POST /api/v1/auth/logout` con el token antes de borrar las
cookies, y revoca **solo esa sesión**: cerrar un portátil no debe terminar el
trabajo del teléfono. Nunca bloquea el cierre; si la API no responde, las cookies
se borran igual.

### El límite que queda dicho

Si el token de acceso ya expiró, el endpoint exige autenticación y la revocación no
ocurre, así que ese token de refresco sigue vivo hasta caducar. Se acepta porque
cubrirlo exigiría un endpoint de revocación anónimo, que es una superficie nueva y
un abuso nuevo.

## ADR-061 - Passlib se sustituye por argon2-cffi, con el hash viejo congelado

Passlib no está mantenido, avisa en la importación bajo Python 3.12 y usa `crypt`,
que 3.13 elimina. Se sustituyó por `argon2-cffi`, que es la librería a la que
Passlib delegaba, con los mismos parámetros: `argon2id`, t=3, m=64 MiB, p=4.

El riesgo no era compilar. Era que **los hashes ya escritos en la base dejaran de
validar** y nadie pudiera entrar, y eso no lo detecta ninguna prueba de las que
existían: todas creaban su propia contraseña.

Así que el hash de Passlib quedó **congelado como constante** en
`test_password_hashing.py`, y ese test **no importa Passlib**, para que siga
funcionando dentro de tres años con la librería desinstalada. Un hash congelado es
un contrato; un comentario que dice «los parámetros son los mismos» es una promesa.
Además se comprobó con un login real sobre una cuenta cuyo hash lo escribió Passlib.

## ADR-062 - El respaldo de objetos se verifica por digest; el recuento pasa a ser un dato

`scripts/backup.sh` escribía `objects.count` y un `MANIFEST.sha256` con el digest de
cada archivo. **Ninguno de los dos se leía.** El recuento no puede detectar un
archivo truncado —que es justo el fallo que importa— y el manifiesto era un fichero
que nadie consumía.

`app/services/backup_manifest.py` relee cada archivo y compara su SHA-256, en
trozos de 1 MiB porque un original puede pesar cientos de megabytes. Distingue
**alterado**, **ausente** y **no listado**, porque significan cosas distintas: uno
es una transferencia fallida, otro es pérdida de datos, y el tercero suele ser un
log escrito después del manifiesto.

Dos decisiones que parecen detalles y no lo son:

1. **Un manifiesto vacío es fallo.** Verificar cero archivos no verifica nada, y
   reportarlo como correcto sería la forma más limpia de mentira.
2. **Los separadores son POSIX, fijados.** El manifiesto se escribe en la máquina
   que respalda y se lee en la que restaura. Con `\` en Windows, un respaldo
   verificado desde Windows reportaba **todos** los objetos ausentes, que se lee
   como pérdida total. La suite corre en Linux y nunca lo habría visto.

`backup.sh` ejecuta la verificación **antes** de la copia externa: subir un
respaldo corrupto y descubrirlo después deja una copia rota al otro lado que parece
una copia de seguridad.

## ADR-064 — Analítica first-party agregada sin identificación de visitantes

**Fecha:** 2026-11-11. **Motivo:** autorización del usuario para medir visitas,
interés por áreas y contactos de la web oficial en un panel privado.

**Decisión:** conservar agregados diarios en PostgreSQL y deduplicar mediante
digests temporales de UUID aleatorios que solo viven en memoria del navegador.
No cookies, almacenamiento persistente de navegador, IP, fingerprint ni proveedor
externo. Los únicos son estimaciones de navegaciones por día: pueden repetirse
al recargar y no se deduplican mensualmente. Retención de digests 48 horas con
purga horaria; agregados 400 días. Las consultas aceptadas incrementan un total
anónimo en su propia transacción, sin copiar datos personales.

**Acceso:** `website_analytics:read`, administrador por defecto, validado también
en backend. Solo se miden portada, servicios y análisis públicos publicados.
Do Not Track/GPC excluyen navegación. La única excepción de auditoría adicional
es el intake exacto de eventos, para no registrar IP/user agent por visita.

**Consecuencias:** conteo orientativo, no personas exactas ni sistema antifraude;
sin histórico anterior a activar. La funcionalidad no debe bloquear la navegación
si la telemetría no responde. Detalles y operación: `docs/ESTADISTICAS_WEB.md`.

## ADR-063 - Los ceilings de dependencias se fijan a lo verificado

Los rangos abiertos (`ruff>=0.12,<1`, `sqlalchemy>=2.0.41,<3`) rompieron los
gates dos veces: una versión nueva añadió reglas y endureció tipos, y el fallo no
era de este código.

La decisión no fue volver atrás, sino **adaptar el código y fijar el techo a lo
medido**: `ruff>=0.12,<0.13`, `mypy>=1.17,<1.18`, `sqlalchemy>=2.1,<2.2`, cada uno
con el motivo escrito al lado. Un techo sin explicación es una barrera que alguien
salta sin saber qué protege.

Y como moraleja: **los errores de tipos se corrigen en la causa.** Los 33 errores

de SQLAlchemy 2.1 parecían 33 problemas: once por `Select[Model]` y dieciocho por
atributos de fila «desaparecidos». Antes de reescribir nada se preguntó al
comprobador qué declaraba 2.1 para `.scalars().all()`, y la respuesta fue
`Sequence[Case]`, sin error. Los atributos eran consecuencia: las anotaciones
`Select[tuple[Modelo]]` de ocho helpers fijaban el tipo de fila. Cambiar esas ocho
líneas resolvió los treinta y tres.

### Y una puerta que faltaba

Durante este trabajo, una dependencia (`uvicorn`) se borró por accidente de
`pyproject.toml`. La imagen se construyó, `ruff` pasó, `mypy` pasó y las 678
pruebas pasaron, porque **nada en la suite importa uvicorn**. El único que lo notó
fue `docker compose up`, con `executable file not found`.

De ahí `test_packaging.py`: un test no puede importar el entrypoint, pero sí leer
el `CMD` del Dockerfile y comprobar que ese binario está declarado. Un gate que no
puede observar el fallo no es un gate.
