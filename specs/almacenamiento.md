# SPEC — ALMACENAMIENTO Y RETENCIÓN

Desarrollar conforme a MASTER_PROMPT.md, en particular la sección 28.

## Estado: implementado tras la Fase 6

## Principio rector

El dominio nunca habla con un disco ni con un bucket. Habla con la interfaz
`StorageBackend`, y la configuración decide qué implementación hay detrás.

Reglas que la propia interfaz impone, no el llamador:

1. Las claves se generan en el servidor con UUID y bytes aleatorios. El nombre
   que envía el usuario **nunca** llega a la ruta.
2. **El contenido nunca se borra.** La política de retención mueve versiones a
   un tier de archivo; los bytes siguen siendo recuperables para siempre.
   `PROJECT_RULES` regla 5 prohíbe eliminar registros jurídicos.

## Implementaciones

| Backend | Uso | Clases remotas |
| --- | --- | --- |
| `LocalStorage` | desarrollo y tests | no |
| `S3Storage` | MinIO o AWS S3 | sí |

- `app/services/storage.py`: contrato `StorageBackend`, `StorageTier`, `StoredObject`
  y la fábrica `build_storage`.
- `app/services/storage_local.py`: disco local. La escritura es atómica
  (temporal + `replace`), de modo que una interrupción nunca deja un objeto
  truncado que parezca un documento válido.
- `app/services/storage_s3.py`: S3/MinIO con `boto3` ejecutado en hilo mediante
  `anyio.to_thread.run_sync`. `boto3` es síncrono; bloquear el event loop en una
  ida y vuelta de red detendría todas las peticiones concurrentes.

### Integridad verificada en cada operación

- `write` devuelve el `StoredObject` con el SHA-256 realmente persistido. Si no
  coincide con el contenido validado, `DocumentService` **borra el objeto y no
  registra la versión**.
- `read_version` revalida el hash antes de servir. Una descarga corrupta es un
  incidente de integridad, nunca una transferencia correcta.
- `set_tier` relee el objeto tras cambiarlo y compara el hash.
- El bucket se crea al arrancar solo si `S3_CREATE_BUCKET=true`.

### Storage class: por qué `STANDARD_IA`

`GLACIER`, `DEEP_ARCHIVE` y `GLACIER_IR` dejan el objeto **ilegible hasta
completar una restauración**. Eso rompería la promesa de que cualquier versión
se puede descargar en cualquier momento, así que `S3Storage` rechaza esas clases
en el constructor. El valor por defecto es `STANDARD_IA`: más barato y siempre
legible.

MinIO en un solo nodo no puede transicionar clases de almacenamiento (solo con
erasure coding). Ahí el tier se registra en la base de datos y
`native_tier_applied` devuelve `false`. El coste real se obtiene en AWS S3 o en
un MinIO con erasure coding; no se debe prometer un ahorro que el backend no
aplica.

## Política de retención

`app/services/retention.py`.

- Una versión es candidata cuando: su tier es `hot`, **no** es la actual, es más
  antigua que `RETENTION_HOT_DAYS` (90 por defecto) y su documento **no** tiene
  retención legal.
- Al archivar se registra en `change_logs` con entidad `document_retention`,
  campo `tier`, y `change_reason` explicando por qué. Nadie hizo clic en nada:
  sin ese motivo, la traza no explicaría nada.
- `plan()` no modifica nada y devuelve los candidatos. `apply(dry_run=True)`
  informa sin tocar. Esto permite revisar la política antes de ejecutarla.
- No existe ninguna ruta de código que llame a `delete` desde la política. Hay
  un test que falla si alguien la introduce.

### Retención legal

`documents.legal_hold` congela la política para un documento mientras esté
activa. Exige un motivo y queda registrado en el historial. Solo el
administrador puede activarla o levantarla.

## Endpoints

- `GET /api/v1/documents/retention/report` — resumen y plan, sin cambios.
- `POST /api/v1/documents/retention/apply?dry_run=true|false` — ejecuta la política.
- `PATCH /api/v1/documents/{id}/legal-hold` — activa o levanta la retención legal.

Se declaran antes de `/documents/{document_id}` para que el segmento literal
gane al paramétrico. Hay un test que lo verifica.

## Permisos

`documents:retention` y `documents:legal_hold`, solo del administrador: una
ejecución de archivo toca todos los expedientes de la firma.

## CLI

- `python -m app.cli.apply_retention --dry-run`
- `python -m app.cli.import_documents_to_s3 --dry-run`

`import_documents_to_s3` existe porque cambiar `STORAGE_BACKEND` **no mueve
bytes**: la `storage_key` guardada seguiría apuntando al disco local. La comando
copia cada archivo, verifica el SHA-256 de lo copiado y solo entonces repunta la
fila. Es idempotente.

## Verificación

- 18 tests de contrato S3 con `moto`, que emula el protocolo S3 en proceso.
- 26 tests de retención, incluido uno que falla si la política borra algo.
- `moto` **no** aplica IAM ni valida `ContentMD5`. La privacidad del bucket y el
  rechazo de transferencias corruptas no se pueden verificar con `moto`; están
  cubiertos por la ausencia de política pública en el bucket y por el envío
  obligatorio de `ContentMD5`, respectivamente.

## Pendiente

- Verificación contra un MinIO real (requiere registro con la imagen `minio/minio`).
- Restauración desde Glacier si algún día se acepta perder disponibilidad.
- Copia de seguridad y verificación de integridad del bucket.