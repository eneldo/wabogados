# SPEC — DOCUMENTOS

Desarrollar conforme a MASTER_PROMPT.md.

## Estado: implementado en Fase 6

### Modelo

- `documents` pertenece siempre a un expediente, igual que los eventos de
  agenda. Así el alcance de acceso se hereda y no hay documentos huérfanos.
- Tipos: `contrato`, `demanda`, `escrito`, `sentencia`, `procuracion`,
  `identidad`, `otro`.
- Estados: `borrador`, `vigente`, `anulado`. La primera versión sube el
  borrador a `vigente`.
- Confidencialidad: `interno`, `confidencial`, `restringido`.
- Visibilidad: `interna`, `equipo`, `publicada`, con las mismas reglas que las
  actuaciones.
- Borrado lógico mediante `is_active` y `deleted_at`; el contenido nunca se
  borra físicamente.

### Versionado inmutable

`document_versions` es el histórico real:

- Cada carga crea una versión nueva con `version_number` correlativo. La
  restricción `uq_document_version (document_id, version_number)` impide
  duplicados a nivel de base de datos.
- **Una versión existente nunca se sobrescribe ni se elimina.** El contenido
  anterior queda intacto y descargable.
- Solo una versión tiene `is_current = true`; al añadir una nueva, la anterior
  pasa a `false` sin perder su archivo.
- Cada versión guarda el SHA-256 del contenido. Se rechaza un archivo cuyo
  hash ya exista en el mismo documento (`409`), de modo que subir dos veces el
  mismo fichero no crea versiones falsas.
- `storage_key` se genera en el servidor a partir de UUID y números aleatorios.
  El nombre de archivo que envía el usuario **nunca** interviene en la ruta.

### Validación por contenido

`app/services/uploads.py` no confía en la extensión ni en el tipo declarado:

- El tipo se detecta por *magic bytes* (PDF, PNG, JPEG, GIF, TIFF, ZIP, DOC).
  Lo que no se reconoce se acepta solo si es texto plano UTF-8.
- Se rechazan ejecutables y scripts: firmas `MZ`, `\x7fELF` y cualquier
  shebang. Un `.pdf` renombrado que en realidad es un ejecutable se rechaza.
- La extensión y el `Content-Type` declarado solo sirven para detectar
  discrepancias; nunca deciden el tipo almacenado.
- Tope de tamaño configurable con `MAX_UPLOAD_BYTES` (20 MB por defecto).

### Almacenamiento

- `LocalStorage` con raíz en `STORAGE_ROOT`. Las claves son opacas y se valida
  que la ruta resuelta siga dentro de la raíz, de modo que `..` o un directorio
  hermano con prefijo similar no permiten escapar.
- En Docker se monta el volumen `storage_data` en
  `/var/lib/wabogados/storage`. El directorio se crea en la imagen con el
  propietario del usuario no root para que el volumen herede permisos.
- MinIO/S3 sigue pendiente: la clase está aislada detrás de `LocalStorage` para
  poder sustituirla.
- Si la escritura en base de datos falla tras guardar el archivo, se elimina el
  archivo para no dejar contenido huérfano sin registro.

### Descarga auditada

- Cada descarga inserta en `document_downloads`: usuario, IP, user agent,
  versión y fecha. Se puede saber quién accedió a qué versión y cuándo.
- La respuesta es binaria, nunca JSON: `Content-Disposition: attachment` con
  nombre saneado, `X-Content-SHA256`, `X-Document-Version`,
  `X-Content-Type-Options: nosniff` y `Cache-Control: no-store`.
- El nombre de archivo se sanea antes de ponerlo en la cabecera para impedir
  inyección de cabeceras.
- **Publicar un documento no concede descarga.** El cliente puede ver que hay
  un documento publicado, pero descargarlo requiere `documents:download`, que
  el rol `cliente` no tiene.

## Permisos

`documents:read`, `documents:read_published`, `documents:create`,
`documents:update`, `documents:download`.

El cliente solo recibe `documents:read_published`, limitado a sus propios
expedientes.

## Endpoints

- `GET/POST /api/v1/cases/{case_id}/documents`
- `GET/PATCH /api/v1/cases/{case_id}/documents/{document_id}`
- `POST /api/v1/documents/{document_id}/versions`
- `GET /api/v1/documents/{document_id}/versions/{version_id}/download`
- `GET /api/v1/documents/{document_id}/history`

Un documento fuera del alcance del usuario devuelve `404`, no `403`, para no
confirmar la existencia de información ajena.

## Ficha 360°

La sección `documentos` pasa a `available: true` con su total. `evidencias`,
`tareas` y `mensajes` siguen en `available: false`.

## Pendiente

- Firma digital y verificación de integridad mediante proveedor externo.
- MinIO/S3 en lugar del almacenamiento local.
- Versions de evidencias reutilizando el mismo servicio de versiones.
