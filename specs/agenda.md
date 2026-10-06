# SPEC — AGENDA

Desarrollar conforme a MASTER_PROMPT.md.

## Estado: implementado en Fase 5

### Eventos

- `calendar_events` siempre ligado a un expediente: así el alcance de acceso es
  inequívoco y no hay eventos huérfanos que auditar.
- Tipos persistidos: `audiencia`, `reunion`, `vencimiento`, `llamada`, `cita`,
  `recordatorio`. Una audiencia solo se crea y modifica por `/hearings`; los
  endpoints genéricos de calendario rechazan ese tipo.
- Estados: `programada`, `realizada`, `cancelada`, `aplazada`.
- Visibilidad: `interna`, `equipo`, `publicada`, con las mismas reglas que las
  actuaciones.
- Si no se indica `ends_at`, se calcula una hora o un día según `all_day`.
- `ends_at` debe ser posterior a `starts_at`; el filtro de eventos usa solapamiento
  para que un evento de varios días no se corte.

### Audiencias con lógica especializada

`hearings` se une 1:1 al evento de tipo `audiencia` y añade:

- juzgado, sala, juez, radicado, etapa procesal, notificación, asistencia y resultado.
- Etapas: `primera_instancia`, `apelacion`, `ejecucion`, `previa`, `conciliacion`, `otra`.
- **No se puede marcar como realizada sin registrar el resultado.**
- **No se puede reprogramar una audiencia realizada o cancelada.**
- **Detección de solapamiento:** un abogado no puede tener dos audiencias en la
  misma franja; el alta y la reprogramación devuelven 409.
- La reprogramación deja traza: la audiencia queda `aplazada` y enlaza con la
  programación anterior mediante `rescheduled_from_id`.

### Vencimientos

`GET /api/v1/calendar/deadlines` combina los eventos `vencimiento` con las
próximas acciones ya registradas, ordenados por fecha y marcados como `overdue`.
No aplica límite inferior de fecha: lo vencido es precisamente lo prioritario.

## Vistas

`GET /api/v1/calendar?view=day|week|month|lawyer|case` con filtros `lawyer_id`,
`case_id` y `event_type`.

La interfaz administrativa en `/admin/agenda` ofrece Día, Semana y Mes,
navegación entre periodos, filtros por abogado, expediente y tipo, cronología
agrupada, métricas y vencimientos prioritarios. Las escrituras usan Server
Actions y los controles solo aparecen cuando la sesión posee el permiso
correspondiente.

Todas las horas se almacenan como instantes UTC y se interpretan y presentan en
la zona institucional `America/Bogota`. El fin del rango de consulta es exclusivo;
los rótulos visuales restan un instante antes de mostrarlo.

## Permisos

`calendar:read`, `calendar:read_published`, `calendar:create`, `calendar:update`,
`hearings:read`, `hearings:create`, `hearings:update`, `hearings:reschedule`.

`hearings:reschedule` es exclusivo del administrador: la fecha la fija el juzgado.

`GET /hearings` exige `hearings:read` y aplica alcance del expediente,
visibilidad y actividad. Crear una audiencia valida que el expediente y el
abogado existan y que el abogado esté activo.

## Endpoints

- `GET /api/v1/calendar`, `POST /api/v1/calendar`, `PATCH /api/v1/calendar/{id}`
- `GET /api/v1/calendar/deadlines`
- `GET /api/v1/hearings`, `POST /api/v1/hearings`, `PATCH /api/v1/hearings/{id}`
- `POST /api/v1/hearings/{id}/reschedule`

## Ficha 360°

Las secciones `agenda` y `audiencias` pasan a `available: true` con sus totales.
Una audiencia también aparece en la agenda, porque es un evento del calendario.

## Pendiente

- Carga de trabajo por abogado a partir de audiencias y actuaciones.
- Recordatorios automáticos a partir de `reminder_minutes` (requiere workers).
