# SPEC — DASHBOARD

Desarrollar conforme a `MASTER_PROMPT.md`, sección 10.

## Estado: implementado en Fase 9

## Principio rector

**Un indicador nunca puede superar el detalle que resume.** El panel es un
agregado sobre las mismas filas que el llamante ya puede paginar. Si una cifra
puede ser mayor que la lista que la acompaña, el agregado está filtrando.

Consecuencias prácticas, y son la mayor parte del código:

1. Cada cifra es un `COUNT` sobre una consulta que **ya lleva** el alcance de
   expediente y la visibilidad. Nada se cuenta en Python.
2. No existe un endpoint por rol. La diferencia entre un administrador y un
   abogado no es *qué cifras existen*, sino *qué filas puede ver*. Un endpoint
   por rol duplicaría las consultas y daría un sitio donde olvidarse del
   alcance.
3. El panel se deriva del **alcance**, no del nombre del rol. Un usuario puede
   tener varios roles, y el alcance es lo que el resto de la aplicación ya
   aplica.
4. No hay una cifra "total de la firma" en ninguna respuesta.

## Arquitectura

| Pieza | Responsabilidad |
| --- | --- |
| `services/dashboard.py` | Consultas con alcance, cifras y listas |
| `schemas/dashboard.py` | Contratos de respuesta |
| `api/v1/dashboard.py` | Dos endpoints, sin lógica de negocio |

`DashboardService.prepare()` resuelve el alcance una vez y guarda la cláusula.
Cada método `_algo_scoped()` devuelve una consulta ya restringida, y `_count()`
la cuenta.

### El fallo que este módulo evita

Contar así está mal:

```python
counted = select(func.count()).select_from(statement.subquery())
counted = counted.where(Filtro.expirada >= limite)   # filtro FUERA
```

El filtro exterior referencia una tabla que ya no está en el `FROM`, así que
SQLAlchemy la reincorpora y el resultado es el producto cartesiano: contar dos
expedientes devuelve **cuatro** en cuanto existe cualquier otra fila. Los
filtros van **dentro** de la consulta. Es la misma forma de fallo que documenta
`case_scoped`, y lo cubre `test_a_count_is_not_a_cartesian_product`.

## Alcance de cada cifra

| Cifra | Alcance |
| --- | --- |
| Clientes activos | Clientes de los expedientes visibles |
| Expedientes activos / cerrados | Visible menos `cerrado` y `archivado` |
| Abogados activos | Responsable o colaborador de algún expediente visible |
| Actuaciones del mes | `occurred_at` dentro del mes en curso, con visibilidad |
| Audiencias próximas | Horizonte configurable, excluye `cancelada`, `celebrada`, `realizada` |
| Actuaciones pendientes | Con `next_action_at` dentro del horizonte, vencidas incluidas |
| Vencimientos por llegar / vencidos | Eventos `vencimiento`; los vencidos se cuentan aparte |
| Documentos recientes | Creados en los últimos 7 días |
| Evidencias | Solo las visibles para el llamante |
| Mensajes pendientes | `MessagingService.total_unread` |
| Notificaciones sin leer | `MessagingService.unread_notifications` |

Los vencimientos vencidos se informan **aparte** de los por llegar. Un único
"pendientes" que mezcla lo vencido con lo futuro esconde exactamente lo que hay
que mirar primero.

## El portal del cliente

Con alcance `own_published` el panel añade una restricción de visibilidad a
documentos, evidencias y actuaciones: solo `publicada`. Sobre audiencias se
restringe el evento que las contiene.

Una consecuencia incómoda pero correcta: el panel de un cliente cuenta cero
clientes activos. No es un error, es la consecuencia de que la única cifra de
"clientes" que puede ver es la suya. Preferimos un cero honesto a un uno
inventado.

## Permiso

`dashboard:read`, en los cuatro roles. El permiso da acceso al agregado, no a
datos nuevos: el panel solo lee filas que el llamante ya puede leer. Un cliente
sin expedientes recibe ceros, no un error.

## Endpoints

| Método | Ruta | Uso |
| --- | --- | --- |
| `GET` | `/api/v1/dashboard` | Panel completo. `days` 1-365, `limit` 1-50 |
| `GET` | `/api/v1/dashboard/summary` | Solo los contadores de la cabecera, para sondeo |

`summary` está separado a propósito: la insignia de la cabecera se sondea cada
pocos segundos y no debe arrastrar la lista de audiencias.

## Verificación

- 25 tests en `app/tests/test_dashboard.py`.
- Suite completa: **511 tests, 85.30 % de cobertura**, Ruff y mypy limpios.
- Migración `c1d2e3f4a5b6` verificada en ambos sentidos: los cuatro roles
  pierden y recuperan `dashboard:read`.

## Pendiente

- El panel no cachea. Con un volumen alto de expedientes las cifras conviene
  cachearlas por usuario con invalidación corta, no por más de unos segundos.
- No hay series temporales: los gráficos de evolución llegan en Fase 10.
- Los agregados de almacenamiento del `MASTER_PROMPT` (peso original, peso
  optimizado, ahorro) no están: son una métrica de la firma completa y habría
  que decidir si el panel del administrador puede verlos sin convertirse en una
  fuga de volumen de negocio.