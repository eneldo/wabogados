# SPEC — ACTUACIONES

Desarrollar conforme a MASTER_PROMPT.md.

## Estado: implementado en Fase 4

Toda actuación pertenece obligatoriamente a un expediente y alimenta la timeline.

- Campos cubiertos: tipo, fecha/hora, descripción, resultado, responsable,
  visibilidad, próxima acción y fecha de próxima acción.
- Tipos: `reunion`, `llamada`, `visita`, `notificacion`, `presentacion`,
  `diligencia`, `consulta`, `seguimiento`, `otro`.
- Visibilidad: `interna`, `equipo` o `publicada`.
- `next_action_at` exige `next_action`: una fecha sin tarea no tiene sentido.
- Baja lógica con `is_active`, `deleted_at` y `deleted_by`; no se elimina
  físicamente porque es información jurídica.
- Historial de cambios por campo en `change_logs`.

## Alcance y visibilidad

- El acceso se hereda del expediente: una actuación nunca es visible si su
  expediente queda fuera del alcance del usuario.
- `actions:read` (administrador, abogado y asistente) ve todos los niveles.
- `actions:read_published` (cliente) ve solo lo `publicada` y solo dentro de sus
  propios expedientes, resueltos por `Client.user_id`.
- Un cliente no puede ampliar el filtro: pedir `visibility=interna` devuelve vacío.

## Permisos

`actions:read`, `actions:read_published`, `actions:create`, `actions:update`.

## Endpoints

- `POST /api/v1/cases/{case_id}/actions`
- `GET /api/v1/cases/{case_id}/timeline` — cronológico, con el estado del
  expediente y marca de pendiente.
- `GET /api/v1/actions` — con filtros `action_type`, `visibility`, `pending_only`.
- `GET /api/v1/actions/pending` — próximas acciones ya vencidas en el alcance.
- `GET /api/v1/actions/{id}`, `PATCH /api/v1/actions/{id}`
- `GET /api/v1/actions/{id}/history`

## Ficha 360°

La sección `actuaciones` pasa a `available: true` con el total de actuaciones del
expediente.

## Pendiente

- Tareas y recordatorios con vencimiento (se conectan con la agenda en Fase 5).
- Carga de trabajo por abogado a partir de las actuaciones.
