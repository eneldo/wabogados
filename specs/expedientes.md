# SPEC — EXPEDIENTES

Desarrollar conforme a MASTER_PROMPT.md.

## Estado: implementado en Fase 3

El expediente es el núcleo funcional y todo lo demás cuelga de él.

- Numeración `WA-AAAA-000001` con contador por año en `case_number_sequences`,
  protegido con `SELECT ... FOR UPDATE` para evitar colisiones concurrentes.
- Campos cubiertos: cliente, abogado responsable, área jurídica, tipo de proceso,
  jurisdicción, juzgado, radicado, estado, prioridad, fechas, descripción, cuantía
  y observaciones.
- Estados: `abierto`, `en_tramitacion`, `suspendido`, `cerrado`, `archivado`.
- Prioridades: `baja`, `normal`, `alta`, `urgente`.
- `case_lawyers` registra al responsable y a los colaboradores; cambiar el
  responsable degrada automáticamente al anterior a colaborador.
- `case_parties` registra demandante, demandado, contraparte y tercero.
- Baja lógica con `is_active`, `deleted_at` y `deleted_by`.
- Historial de cambios por campo en `change_logs`.

## Alcance de acceso (IDOR)

- `cases:read_all` (administrador y asistente) ve todo el libro de expedientes.
- `cases:read_assigned` (abogado) ve solo donde es responsable o colaborador.
- Un expediente fuera de alcance responde `404`, no `403`, para no confirmar que
  el identificador existe.
- `cases:close` es exclusivo del administrador: cerrar un expediente es un acto
  jurídico reservado.

## Permisos

`cases:read_all`, `cases:read_assigned`, `cases:create`, `cases:update`,
`cases:close`, `cases:assign`.

## Endpoints

- `GET /api/v1/cases` — paginado, con `search`, `status`, `priority`,
  `legal_area_id`, `client_id` y `open_only`, filtrado por alcance.
- `POST /api/v1/cases`
- `GET /api/v1/cases/{id}`
- `PATCH /api/v1/cases/{id}`
- `POST /api/v1/cases/{id}/close`
- `GET /api/v1/cases/{id}/360` — ficha 360°.
- `POST /api/v1/cases/{id}/lawyers`, `DELETE /api/v1/cases/{id}/lawyers/{lawyer_id}`
- `GET /api/v1/cases/{id}/parties`, `POST /api/v1/cases/{id}/parties`
- `GET /api/v1/cases/{id}/history`

## Ficha 360°

Las secciones de actuaciones, evidencias, documentos, agenda, audiencias, tareas
y mensajes se declaran con `available: false` hasta que su fase las implemente,
para que el frontend pueda construir la estructura de pestañas desde el inicio.

## Pendiente

- Actuaciones y timeline (Fase 4).
- Carga de trabajo por abogado y agenda (Fases 4 y 5).
- Tareas y Recordatorios dentro del expediente.
