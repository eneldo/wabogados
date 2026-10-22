# PROCEDIMIENTO DE RESTAURACIÓN

Este documento existe porque `MASTER_PROMPT` sección 44 exige que la
restauración esté **documentada y probada**. No es un ejercicio teórico: hay un
script que la ejecuta y falla si no funciona.

---

## 1. Qué respalda y qué no

| Componente | Cubierto | Dónde |
| --- | --- | --- |
| PostgreSQL | Sí | `postgres.dump` + `postgres.manifest.json` |
| Originales documentales | Sí | `objects/` |
| Migraciones Alembic | Sí | `migrations/` |
| Configuración no secreta | Sí | `config.json` |
| Objetos en MinIO/S3 | Depende | `BACKUP_REMOTE` sin definir: **solo copia local** |
| Bucket de objetos | No | Requiere réplica del bucket |
| Sistema de ficheros del host | No | Fuera de alcance |
| Claves y secretos | **Nunca** | Deliberadamente excluido |

Una copia dentro del mismo volumen no es un respaldo: no sobrevive a la
pérdida de ese volumen. Para una firma esto no es opcional.

---

## 2. Orden de respaldo y por qué importa

El contenido se escribe en el almacenamiento **antes** de que su fila en la
base de datos haga commit. Por tanto:

- Un objeto puede existir sin fila. Es lo normal cuando una transacción falla.
- Una fila **nunca** existe sin su objeto: `DocumentService` borra el objeto si
  el commit falla.

De ahí se deduce el orden obligatorio:

```
1. Configuración
2. PostgreSQL          ← primero
3. Objetos             ← después
4. Migraciones
```

Hacerlo al revés produciría una base de datos restaurable con filas apuntando a
objetos que la copia no contiene. `scripts/backup.sh` sigue ese orden y el
comentario está en el propio script para que nadie lo "optimice".

---

## 3. Ejecutar el respaldo

```bash
# Respaldo local con verificación de restauración
scripts/backup.sh

# Con copia externa (imprescindible en producción)
BACKUP_REMOTE=s3/wabogados-backups scripts/backup.sh

# Etiqueta y retención
BACKUP_TAG=diaria BACKUP_KEEP=30 scripts/backup.sh
```

Resultado en `backups/<marca-de-tiempo>/`:

```
config.json                 variables no secretas
postgres.dump               volcado de PostgreSQL
postgres.dump.sha256        digest del volcado
postgres.manifest.json      digest + revisión de Alembic
objects/                    objetos documentales
objects.count               número de objetos (informativo, no verifica)
migrations/alembic/         migraciones
MANIFEST.sha256             digest de todo el directorio
```

`objects.count` es un dato, no una comprobación: un recuento sobrevive a un
archivo truncado. La verificación real es contra `MANIFEST.sha256`:

```bash
python -m app.cli.verify_backup_files --manifest backups/<STAMP>/MANIFEST.sha256
```

Se ejecuta sola al final de `scripts/backup.sh`, **antes** de enviar nada al
destino externo, y el script se detiene si falla. Distingue alterado, ausente y
no listado, y un manifiesto vacío se considera fallo: no verifica nada y no puede
dar por bueno un respaldo.

### Salidas y códigos

| Código | Significado |
| --- | --- |
| 0 | Respaldo creado y restauración verificada |
| 4 | El volcado **no** es restaurable |
| 5 | No se pudo crear el volcado |

Si el código es 4, el respaldo **no existe**. No lo archive como válido.

---

## 4. Verificar una copia sin restaurarla en producción

```bash
# `exec` no admite montajes en Compose 5.6: usar `run` con la ruta absoluta
# (un origen relativo en `run -v` se interpreta como volumen nombrado).
docker compose run --rm --no-deps \
  -v "$PWD/backups/<marca>:/backup:ro" \
  backend python -m app.cli.verify_backup \
    --dump /backup/postgres.dump \
    --manifest /backup/postgres.manifest.json
```

Qué comprueba, en una base de datos temporal que después borra:

1. El digest del archivo coincide con el manifiesto.
2. `pg_restore` termina sin error.
3. Existe la revisión de Alembic esperada.
4. Están las tablas críticas: `users`, `cases`, `documents`,
   `document_versions`, `change_logs`, `audit_logs`, `integrity_scans`.
5. Recuento de filas de cada tabla crítica.

La base de datos en producción no se toca jamás.

---

## 5. Verificar la integridad del almacenamiento

Un respaldo restaurable no garantiza que el contenido esté íntegro. Son dos
controles distintos.

```bash
# Muestra rápida, para el día a día
docker compose exec -T backend \
  python -m app.cli.verify_integrity --mode sample --sample 500

# Auditoría completa: descarga todos los bytes
docker compose exec -T backend \
  python -m app.cli.verify_integrity --check-orphans

# Un solo documento
docker compose exec -T backend \
  python -m app.cli.verify_integrity --mode sample --sample 500 --json
```

Hallazgos posibles:

| Hallazgo | Significado | Bloqueante |
| --- | --- | --- |
| `corrupted` | El contenido cambió. Bit rot, escritura parcial o edición externa | Sí |
| `missing` | La clave no existe en el almacenamiento | Sí |
| `size_mismatch` | Tamaño distinto al registrado | Sí |
| `unreadable` | El backend falló al leer | No |
| `orphaned` | Objeto sin fila en la base de datos | No |

### La verificación nunca repara

No existe ninguna ruta de código que escriba o borre contenido documental desde
el verificador, y hay un test que falla si alguien la introduce.

Un hash que no coincide **no se sobrescribe**. Un documento corrupto es un
hecho que se documenta y se restaura desde una copia; ocultarlo destruye la
prueba. Si el contenido recuperado no es el esperado, nadie sabrá nunca qué se
perdió.

---

## 6. Restauración real

### 6.1 Base de datos

```bash
# 1. Detener la aplicación para que nadie escriba durante la restauración
docker compose stop backend frontend

# 2. Restaurar el volcado sobre una base limpia
docker compose exec -T postgres sh -c \
  'dropdb -U "$POSTGRES_USER" --if-exists wabogados &&
   createdb -U "$POSTGRES_USER" wabogados'

docker compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d wabogados --no-owner --no-privileges' \
  < backups/<marca>/postgres.dump

# 3. Comprobar la revisión de esquema
docker compose exec -T backend alembic current
# Debe coincidir con postgres.manifest.json

# 4. Levantar
docker compose up -d backend frontend
```

### 6.2 Objetos documentales

Si los objetos se respaldaron en el mismo directorio:

```bash
docker compose stop backend
docker compose exec -T backend sh -c 'rm -rf /var/lib/wabogados/storage/*'
docker run --rm -v "$PWD/backups/<marca>/objects:/objects:ro" \
  -v wabogados_v1_master_storage_data:/var/lib/wabogados/storage \
  alpine sh -c 'cp -a /objects/. /var/lib/wabogados/storage/ && chown -R 10001:10001 /var/lib/wabogados/storage'
docker compose up -d backend
```

Si el bucket S3 es el origen, use `mc mirror` en el sentido inverso o active
replicación en el bucket de destino.

### 6.3 Verificación posterior obligatoria

```bash
docker compose exec -T backend python -m app.cli.verify_integrity --check-orphans
docker compose exec -T backend python -m app.cli.verify_backup --dump ...
```

Un hallazgo `orphaned` tras restaurar es normal si el respaldo de objetos se
tomó más tarde que el de la base de datos: son objetos cuyo commit no llegó a
guardarse. **No los borre.** Registran una transacción fallida.

---

## 7. Verificación de integridad tras restaurar

Este es el control que detecta corrupción silenciosa: bytes que cambiaron en
disco sin que nadie lo hiciera desde la aplicación.

```bash
docker compose exec -T backend \
  python -m app.cli.verify_integrity --check-orphans
```

Cobertura recomendada:

| Control | Frecuencia | Coste |
| --- | --- | --- |
| Muestra de 500 versiones | Diaria | Bajo |
| Verificación completa | Mensual | Alto: lee todo el bucket |
| Restauración desde copia | Mensual | Medio: requiere entorno desechable |
| Restauración completa | Trimestral | Alto: exige práctica real |

Las ejecuciones quedan registradas en `integrity_scans` y `integrity_findings`,
y se consultan en `GET /api/v1/documents/integrity/latest`. Eso es lo que se
muestra a un auditor.

---

## 8. Respaldo externo

Una copia que sigue en el mismo host que los datos que protege no es un
respaldo. `MASTER_PROMPT` sección 44 exige respaldar, y lo primero que debe
preguntarse uno de una copia es si sobrevive a la pérdida del servidor.

### Configuración

```bash
BACKUP_REMOTE_ENABLED=true
BACKUP_REMOTE_ENDPOINT=s3.eu-west-1.amazonaws.com   # u otra máquina/proveedor
BACKUP_REMOTE_ACCESS_KEY=...
BACKUP_REMOTE_SECRET_KEY=...
BACKUP_REMOTE_BUCKET=wabogados-backups
BACKUP_REMOTE_PREFIX=wabogados
BACKUP_REMOTE_VERIFY_UPLOAD=true
BACKUP_REMOTE_KEEP=90
```

**El endpoint no puede ser el bucket de los documentos.** Si `STORAGE_BACKEND`
apunta al mismo S3 y al mismo bucket que `BACKUP_REMOTE_ENDPOINT`, un borrado
accidental o un ransomware se lleva ambos a la vez. **Esta regla la hace cumplir
el código**: `RemoteBackup.from_settings` rechaza esa configuración antes de crear
el cliente, con un mensaje que nombra el bucket y pide otro destino. Un bucket
distinto en el mismo servidor sí se acepta: es una disposición más débil, pero no
la que este control describe, y rechazarla enseñaría a ignorar el error.

> Coincidencia por endpoint: `https://host` y `https://host/` son el mismo
> servidor y la comparación lo normaliza, de modo que una barra final no desactiva
> la comprobación.

### Decisión de la firma (2026-10-05)

El destino será **un bucket S3 de otro proveedor**, con credenciales propias del
respaldo y distintas de las de los documentos. Queda **sin decidir** si ese bucket
debe ser inmutable frente a un ransomware que robe esas credenciales (Object Lock o
equivalente): es una decisión de política, no de configuración, y no se da por
supuesta.

Lo que falta para ejecutarlo, todo del lado del proveedor:

1. Crear el bucket de respaldos en otra cuenta, con **versionado habilitado**.
2. Crear una credencial dedicada al respaldo, con permiso solo sobre ese bucket.
3. Definir `BACKUP_REMOTE_ENDPOINT`, `BACKUP_REMOTE_REGION` y
   `BACKUP_REMOTE_ADDRESSING_STYLE` según el proveedor. Casi todos aceptan
   `path`; AWS S3 también acepta `virtual`.
4. Poner los valores en el `.env` del despliegue — **nunca en el repositorio** —
   y arrancar con `BACKUP_REMOTE_ENABLED=true`.
5. Comprobar con `python -m app.cli.remote_backup --status` que la configuración
   es la esperada y que el destino no coincide con el de los documentos.

### Por qué el script no usa `mc mirror`

`mc mirror` devuelve éxito si los bytes salieron del proceso, no si llegaron
intactos. Un corte de red a mitad de la subida o un bucket mal configurado se
descubren el día de la restauración. Por eso la copia se hace con `boto3` y
**se relee el objeto para comparar su SHA-256**.

Con `BACKUP_REMOTE_VERIFY_UPLOAD=false` se salta esa lectura y se confían solo
los metadatos. Es más rápido y menos seguro, y la salida lo dice.

### Uso

```bash
# Estado de la configuración, sin exponer secretos
docker compose exec -T backend python -m app.cli.remote_backup --status

# Subir el último respaldo y verificarlo
docker compose exec -T -v "$PWD/backups/<marca>:/backup:ro" \
  backend python -m app.cli.remote_backup --push /backup/<marca>

# Reverificar un objeto remoto
docker compose exec -T backend python -m app.cli.remote_backup \
  --verify postgres.dump --sha256 <digest>

# Descargar para restaurar
docker compose exec -T -v "$PWD/backups:/backup" \
  backend python -m app.cli.remote_backup \
    --fetch postgres.dump --into /backup --sha256 <digest>

docker compose exec -T backend python -m app.cli.remote_backup --list
docker compose exec -T backend python -m app.cli.remote_backup --prune
```

### Códigos de salida

| Código | Significado |
| --- | --- |
| 0 | Copia externa subida y verificada por digest |
| 2 | Destino externo no configurado |
| 3 | Falta indicar acción |
| 4 | La copia externa no se pudo subir o verificar |

### Si no está configurado

`scripts/backup.sh` **avisa con tres líneas en rojo** y continúa: la copia local
sigue siendo válida y no conviene bloquear ejecuciones hasta que alguien
configure el destino externo. Para entornos donde sí es obligatorio:

```bash
BACKUP_REMOTE=required scripts/backup.sh
```

La alternativa —fallar en silencio— es peor que no tener la comprobación,
porque aparenta que funciona.

### La retención remota es conservadora

`--prune` solo borra objetos que este módulo escribió, identificados por la
marca `wabogados-backup=1` en sus metadatos. Un objeto que puso alguien más en
ese bucket nunca se toca, y `--keep 0` se rechaza.

---

## 9. Ensayo de restauración completa

**Ensayo ejecutado el 2026-10-05**, con la aplicación detenida. Se documenta aquí
porque un procedimiento que nunca se ejecutó no es un procedimiento.

### Qué se hizo

1. Inventario previo, para poder comparar después: 9 usuarios, 5 clientes, 5
   expedientes, 4 eventos, 3 documentos, 234 filas de auditoría, revisión
   `e9f0a1b2c3d4`, 43 tablas y 21 archivos en el almacenamiento.
2. Respaldo con digest y verificación previa
   (`app.cli.verify_backup` → `resultado: OK`, 43 tablas).
3. **Aplicación detenida**: `backend`, `frontend` y `evidence-worker`. Solo
   PostgreSQL sigue en pie.
4. Base borrada y recreada: **0 tablas** antes de restaurar.
5. `pg_restore` del volcado.
6. Almacenamiento **vaciado** y repuesto desde la copia: 21 archivos.
7. Aplicación levantada y verificada.

### Resultado

| Control | Antes | Después de restaurar |
| --- | --- | --- |
| usuarios / clientes / expedientes | 9 / 5 / 5 | 9 / 5 / 5 |
| eventos / documentos / auditoría | 4 / 3 / 234 | 4 / 3 / 234 |
| revisión de Alembic | `e9f0a1b2c3d4` | `e9f0a1b2c3d4` |
| tablas | 43 | 43 |
| archivos de almacenamiento | 21 | 21 |

`verify_integrity --mode full --check-orphans`: **6 de 6 versiones documentales
verificadas por digest**, 0 ausentes, 0 corruptas. Los 15 objetos marcados como
`orphaned` son de evidencias de pruebas anteriores y **ya estaban antes del
ensayo**: RESTORE.md 6.3 dice que no se borran, y aquí son además la prueba de que
el almacenamiento se restauró tal cual, sin extras ni pérdidas.

La API quedó `ready`, el frontend respondió 200 y el listado de expedientes mostró
los 5 expedientes con sus clientes y estados.

### Dos límites que este ensayo NO cubre

Son reales y conviene no presentarlos como cerrados:

1. **Lo hizo el mismo agente que escribió el sistema.** Un ensayo de
   restauración busca demostrar que *otra persona* puede recuperar el servicio.
   Este demuestra que los comandos funcionan, no que el procedimiento sea
   legible por alguien que no lo escribió.
2. **Este host no tiene `bash`**, así que `scripts/backup.sh` no se ejecutó entero:
   sus pasos se replicaron uno a uno. El script sigue sin probarse de principio a
   fin en este entorno.

### Si va a ejecutarlo una persona

`scripts/backup.sh` desde el repositorio, y después la sección 6. El orden de la
sección 6 es el que importa: primero se detiene **toda** la aplicación que pueda
escribir (`backend`, `frontend` y `evidence-worker`), después se recrea la base,
y al final se repone el almacenamiento. Saltarse el primer paso deja una
restauración que compite con escrituras vivas.

--- Lo que este procedimiento todavía no cubre

Dicho con claridad, para no dar una confianza que no existe:

- **El destino externo del stack es el mismo host.** El servicio `minio-backup`
  de `compose.yaml` existe para ejercitar el mecanismo, no para sobrevivir a un
  incendio. En producción debe ser otra máquina o proveedor.
- **Los objetos sí se verifican por digest (2026-10-04).** Antes solo había
  `objects.count`, que no detecta un archivo truncado. Ahora
  `app.cli.verify_backup_files` relee cada objeto y compara su SHA-256 contra
  `MANIFEST.sha256`, y `scripts/backup.sh` lo ejecuta antes de la copia externa.
  Lo que sigue sin probarse es una restauración completa con la aplicación caída.
- **MinIO no verificado.** Este entorno no puede descargar la imagen
  `minio/minio`, así que ni el bucket de documentos ni el de respaldos se han
  probado contra MinIO real. El mecanismo S3 sí se ejecutó sobre HTTP real.
- **Sin versionado probado.** `S3Storage.enable_versioning()` existe pero el
  arranque no lo llama.
- **RTO sin medir en condiciones reales.** La verificación mide cuánto tarda una
  restauración, pero con una base de datos de tamaño de desarrollo.
- **Sin plan de disaster recovery probado.** Existe un procedimiento de
  restauración. No existe un ejercicio completo con la aplicación caída, otro
  operador y un plazo que cumplir. Eso se rehearsal, no se documenta.