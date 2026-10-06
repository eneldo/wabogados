# SPEC — QA, HARDENING Y DESPLIEGUE

Desarrollar conforme a `MASTER_PROMPT.md`, secciones 34, 37, 41, 43 y 44.

## Estado: implementado en Fase 10

## Qué faltaba de verdad

La fase no empezó escribiendo código, sino midiendo. El resultado fue mucho más
pequeño de lo que el título sugiere:

| Requisito | Estado real al empezar |
| --- | --- |
| JWT, refresh, RBAC, rate limiting, CORS, trusted hosts, headers | Implementado desde Fase 1 |
| Las 30 tablas de la sección 37 | **29**. Faltaba `system_settings` |
| Observabilidad de la sección 43 | No existía ninguna métrica |
| Quality gates | Los ejecutábamos a mano; no había pipeline |
| Backups | Implementados y con restauración probada en Fase 6 |

Dos huecos reales y tres piezas que faltaban por completitud. La Fase 10 consistió
en cerrarlos y en dejar escrito lo que sigue pendiente.

## `system_settings`

Única tabla de la sección 37 que no existía. Alojamiento clave/valor para lo que
un administrador debe cambiar sin redesplegar: política de retención, aviso de
mantenimiento, pausa del procesado de evidencias.

**No es un sitio para secretos.** Cualquier fila es legible por cualquier
administrador, entra en cada `pg_dump` y su valor anterior se escribe en
`change_logs`. Una contraseña guardada ahí acabaría en todos los respaldos y en
todas las auditorías. `reject_credential_keys` rechaza esas escrituras, aunque
el aviso del módulo es explícito: la garantía real es que los secretos viven en
el entorno.

Las claves son auditadas con un UUIDv5 derivado del nombre, de modo que los
cambios de un mismo ajuste se agrupan en el rastro.

### Una trampa de `record_changes`

`record_changes` omite un campo cuyo valor no cambió. Un borrado que pasa
`after={}` no registra **nada**: el ajuste desaparece sin dejar rastro. La
solución es pasar `after` con el valor ausente en cada campo, que es lo que
ocurre de verdad al borrar. Lo cubre `test_delete_keeps_the_trail`.

## Observabilidad (sección 43)

`GET /api/v1/admin/metrics/evidence` mide todo lo que la sección 43 enumera:

- cantidad de evidencias y desglose por estado;
- MB originales, MB optimizados, MB ahorrados y ratio de compresión;
- tiempo medio de procesado;
- fallos y trabajos en cuarentena;
- uso de almacenamiento: originales, derivados y versiones de documentos.

El ratio usa la fórmula del propio `MASTER_PROMPT`: 124 GB a 38 GB es 69% de
ahorro. Con cero evidencia el ratio es **0**, no infinito.

**Los recuentos y sumas se hacen en SQL.** Haber subido 100 GB no puede
convertir el endpoint de métricas en una lectura de 100 GB de filas.

El uso de almacenamiento sale de la base de datos, no del bucket: `pg_dump`
restaura lo que la base dice que se guardó, y si los dos se contradicen esa
contradicción ya es el hallazgo.

Solo `JobStatus` completado devolvía la media de tiempo: promediar sobre
trabajos fallidos mezclaría dos números distintos.

## Endurecimiento

- `JobStatus` pasó de cuatro cadenas mágicas repartidas por el servicio a un
  enum. Un worker que escribiera `"runing"` en lugar de `"running"` dejaría de
  encontrar trabajos en silencio.
- `test_only_login_and_refresh_are_public` recorre el árbol de dependencias de
  las 92 rutas y falla si alguna no está autenticada **y** no deriva su alcance
  de un permiso. Convierte la prohibición de la sección 48 en una prueba.
- `test_a_user_without_permissions_reads_nothing` recorre los endpoints de
  lectura con un usuario sin permisos y afirma que ningún payload contiene una
  UUID. Es más fuerte que enumerar cada sobre de respuesta: si vuelve una fila,
  vuelve su id.

## Pipeline

`.github/workflows/quality-gates.yml` ejecuta los seis gates de la sección 41 en
cada push: escaneo de secretos, lint, tipos, migraciones reversibles, suite con
techo de cobertura, construcción de la imagen y gates del frontend.

Los tests corren dentro de `compose.test.yaml`, el mismo stack que en local. Un
test que pasa en un portátil y falla en CI es peor que no tener test.

## Verificación

- 41 tests nuevos en `test_hardening.py`, 1 en `test_rbac_admin.py`.
- Suite completa: **552 tests, 85.53 % de cobertura**, Ruff y mypy limpios en
  126 archivos.
- Migraciones `d2e3f4a5b6c7` (tabla) y `e3f4a5b6c7d8` (permisos) verificadas en
  ambos sentidos.

## Pendiente, y es lo importante

`docs/DEPLOY.md` abre con siete bloqueantes. Los tres primeros cuestan datos:

1. `BACKUP_REMOTE_ENDPOINT` en otra máquina.
2. Rehearsal de restauración con la aplicación caída.
3. Verificación del respaldo de objetos por digest, no por recuento.

Después: antivirus para evidencias, planificador del `evidence_worker`,
versionado del bucket y rate limiter sobre Redis.

Nada de esto se resuelve con más código en este repositorio: son decisiones de
infraestructura y de proveedor.