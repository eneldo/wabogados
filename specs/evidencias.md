# SPEC — EVIDENCIAS

Desarrollar conforme a MASTER_PROMPT.md, secciones 17 a 32 y 40.

## Estado: implementado en Fase 7

## Principio rector

**El original recibido nunca se destruye ni se sustituye.** Todo lo demás se
deriva de él. Un PDF firmado no se reoptimiza, porque reescribirlo destruye la
firma, y una firma rota en una evidencia es peor que un archivo más grande.

## Modelo de datos

Seis tablas, según `MASTER_PROMPT` sección 25:

| Tabla | Contenido |
| --- | --- |
| `evidences` | Registro lógico, ligado a expediente y opcionalmente a actuación |
| `evidence_files` | El original recibido. Inmutable |
| `evidence_derivatives` | Versiones derivadas, cada una con su hash |
| `evidence_processing_jobs` | Cola de trabajo para archivos grandes |
| `evidence_access_logs` | Cada descarga y cada visualización |
| `evidence_events` | Cadena de custodia. Solo se añade, nunca se modifica |

La restricción `uq_evidence_single_original (evidence_id, is_original)` impide
tener dos originales en la base de datos. "Un solo original" es una invariante
legal, no una convención: la base la garantiza, no el código de aplicación.

## Pipeline

Orden obligatorio de `MASTER_PROMPT` sección 18:

```
subida → validación de extensión → MIME real → tamaño → seguridad
       → SHA-256 original → metadatos → original inmutable
       → normalizar → optimizar → SHA-256 derivado → vista previa
       → registrar resultados → vincular → auditar
```

### Validación (`evidence_validation.py`)

Más estricta que la de documentos, por tres razones:

1. **Detección de políglotos.** Un archivo que es a la vez PDF y ZIP hace que dos
   filtros de contenido discrepen y uno de los dos esté equivocado. Se buscan las
   firmas de contenedor en toda la cabecera, no solo en el offset cero, porque el
   polígloto clásico empieza como PDF válido y lleva el directorio ZIP más
   adelante. Un archivo con dos formatos se rechaza.
2. **Bombas de descompresión.** Un PNG de 40 kB puede declarar 40000x40000
   píxeles. Las dimensiones se comprueban **antes** de decodificar.
3. **Validación estructural.** Una imagen se abre de verdad; un PDF se parsea de
   verdad. Los magic bytes no bastan.

**No hay motor antivirus.** La comprobación es estructural: firmas, formatos
prohibidos, políglotos y dimensional. Eso no sustituye a ClamAV ni a un
proveedor de análisis. Está anotado en `KNOWN_ISSUES.md`.

### Imágenes (`evidence_processing.py`, Pillow)

- Se preserva la proporción. Nunca se deforma.
- Se aplica la rotación EXIF **antes** de redimensionar, para que las
  dimensiones registradas sean las reales.
- Nunca se amplía una imagen pequeña: escalar inventa detalle que no era
  evidencia.
- Los PNG con transparencia conservan alfa en el derivado.
- Perfiles según `MASTER_PROMPT` sección 21: `legal_standard` para documento
  fotografiado (2200 px, calidad 85) y fotografía (2560 px, calidad 86), más
  `web_preview` para miniaturas.

### PDF (pikepdf/qpdf)

- Un **PDF firmado se copia byte a byte**. No se reoptimiza.
- Un PDF sin firma se optimiza de forma estructural y linealizada: sin pérdida,
  conservando texto seleccionable y marcadores.
- Si la optimización resultara más grande, se conserva el original.

### Estados

`uploaded`, `validating`, `scanning`, `processing`, `optimized`, `ready`,
`failed`, `quarantined`.

## Procesamiento asíncrono

Los archivos de más de 5 MB (`INLINE_LIMIT_BYTES`) no se procesan en la
petición: se registra un trabajo en `evidence_processing_jobs` y un worker lo
toma.

```bash
python -m app.cli.evidence_worker --once
python -m app.cli.evidence_worker --loop --interval 30
```

El worker reclama trabajos con `FOR UPDATE SKIP LOCKED`, así que dos workers no
toman el mismo trabajo.

**No hay planificador ejecutándose en desarrollo.** El CLI existe y funciona;
hace falta un cron o un servicio que lo invoque. Está anotado como pendiente.

## Inmutabilidad

`MUTABLE_FIELDS` es la lista explícita de lo que un usuario puede cambiar. El
hash original, la fecha de carga y la clave de almacenamiento **no están en ella**
y ningún schema de actualización puede expresarlos. No es una validación que se
pueda saltarse: la API no tiene el campo.

`update_evidence` rechaza cualquier clave fuera de la lista, y hay un test que lo
comprueba.

## Cadena de custodia

Cada acción añade un `EvidenceEvent`: subida, validación, almacenamiento del
original, derivados, procesado, cambio de visibilidad, clasificación y
descargas. Las filas **no se actualizan nunca**.

Toda descarga del original se registra en `evidence_access_logs` y además en la
cadena de custodia. Si los bytes leídos no coinciden con el hash registrado, la
descarga **se bloquea**: servir contenido corrupto es el peor resultado posible.

## Claves de almacenamiento

`MASTER_PROMPT` sección 28, con UUID y nunca el nombre del usuario:

```
evidences/case_uuid/evidence_uuid/original/file_uuid.pdf
                             /optimized/file_uuid.webp
                             /previews/thumbnail_abc123.jpg
```

## Permisos

`evidences:view`, `evidences:create`, `evidences:upload`,
`evidences:download_original`, `evidences:download_optimized`,
`evidences:publish_to_client`, `evidences:classify`, `evidences:archive`,
`evidences:audit`, más `evidences:view_published` para el cliente.

Los nombres son la forma inglesa de los de `MASTER_PROMPT` sección 32
(`evidencias.view` → `evidences:view`), coherente con `cases:` y `documents:`.

El cliente **nunca** recibe `download_original`. Puede ver que hay una evidencia
publicada y bajar el derivado de consulta.

## Endpoints

- `GET/POST /api/v1/cases/{case_id}/evidences`
- `GET/PATCH /api/v1/evidences/{evidence_id}`
- `POST /api/v1/evidences/{evidence_id}/original`
- `GET /api/v1/evidences/{evidence_id}/original`
- `GET /api/v1/evidences/{evidence_id}/derivatives/{derivative_id}`
- `GET /api/v1/evidences/{evidence_id}/custody`
- `GET /api/v1/evidences/{evidence_id}/history`

Todo lo que se lee por identificador exige **visibilidad y alcance de
expediente**. El alcance va dentro de la consulta, no como filtro posterior, para
que ningún endpoint pueda olvidarlo: un permiso sin alcance permite leer
cualquier registro de la firma adivinando su UUID.

Una evidencia fuera de alcance responde 404, no 403.

## Ficha 360°

La sección `evidencias` pasa a `available: true` con su total.

## Verificación

- 70 tests del motor: validación, políglotos, bombas, imágenes, PDF, firma
  digital, custodia, inmutabilidad, aislamiento de cliente y worker.
- Flujo HTTP real en ejecución: original inmutable, segundo original rechazado,
  descarga auditada, PDF de 3 páginas, 360º.
- La base de datos garantiza un solo original por evidencia.

## Pendiente

- **Motor antivirus real.** La validación es estructural, no un análisis de
  malware.
- **Worker continuo.** Compose ejecuta el CLI como servicio `evidence-worker`;
  otros despliegues deben mantener un proceso equivalente con `--loop`.
- **Firma digital verificable.** Se detecta si un PDF lleva firma y si su
  ByteRange cubre el archivo, pero no se valida criptográficamente.
- **Notificación al cliente.** `MASTER_PROMPT` la contempla; no existe.
- **PDF rasterizado a imagen.** No implementado: solo hay derivados PDF.