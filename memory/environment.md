# Entorno

## Sistema operativo
- **Fedora Linux** (migración concluida el 2026-10-21; el historial de abajo era
  Windows con PowerShell 5.1 y ya no aplica). El shell es `bash` con `&&`.
- El intérprete del host es `python3`; las dependencias del backend viven **en
  el contenedor** (`/opt/venv`), no en un venv del host.

## Python
- 3.12 en desarrollo; 3.12.11-slim en la imagen Docker.
- Dependencias instaladas en `/opt/venv` dentro del contenedor. El imagen base
  (target `builder`) trae las dev, pero **el servicio `test` de Compose las
  instala en cada corrida** (`command` en `compose.test.yaml`): una corrida
  con `pytest` directamente falla con *No module named pytest* si se salta ese
  paso — incluir `pip install -e .[dev]` cuando se corra un subconjunto.

## Node.js
- Next.js 16 con React 19, TypeScript strict y Tailwind 4. Playwright con
  Chromium 141 en `~/.cache/ms-playwright`.

## Docker
- Docker 29.9.2 + Compose v5.6.1 instalados en el host Fedora. Cuidado: el
  grupo `docker` está en `/etc/group` pero una sesión ya iniciada puede no
  llevarlo; si `docker info` da *permission denied*, usar `sg docker -c "..."`.
- El **PostgreSQL 18.6 de systemd ocupa el 5432; el proyecto mapea 5433 en
  host** (`.env` del host con `POSTGRES_PORT=5433`; dentro de la red Compose
  el backend sigue usando 5432).
- Compose con `postgres:17.6-alpine`, `backend`, `clamav`, `evidence-worker`,
  `redis` y `frontend` (los dos servicios `minio*` están comentados a propósito).
  `compose.test.yaml` monta `./backend` en `/build` y usa PostgreSQL efímero en
  `tmpfs`; el volumen debe coincidir con el `WORKDIR` (= `/build`) de la imagen
  de test.
- Ejecutar la suite con:
  `docker compose -f compose.yaml -f compose.test.yaml run --rm test`
- `docker compose up --force-recreate` sin `--build` reutiliza la imagen
  anterior; hay que incluir `--build`. Recuérdalo tras tocar frontend.
- Los volúmenes con nombre heredan la propiedad del directorio existente en la
  imagen. Si el directorio no se crea, el volumen nace como root y el usuario no
  root no puede escribir.

## Base de datos
- PostgreSQL 17 vía el contenedor; las pruebas se ejecutan siempre dentro de
  Docker, se corran o no en el host.
- El contenedor `postgres-test` contamina entre corridas (la base persiste):
  si un test se ejecutó con otro motor, reiniciarlo antes de la suite:
  `docker compose -f compose.yaml -f compose.test.yaml restart postgres-test`.

## Servicios
- Backend: <http://localhost:8000> (healthcheck en `/api/v1/health/ready`).
- Frontend: <http://localhost:3000>.
- PostgreSQL local (host): `localhost:5433`; desde la red Compose: `postgres:5432`.

## Almacenamiento
- Documentos en el volumen `storage_data`, montado en
  `/var/lib/wabogados/storage` con `STORAGE_ROOT` apuntando allí.
- Fuera de Docker, `STORAGE_ROOT` usa `.tmp/storage` bajo el directorio actual.
- `STORAGE_BACKEND=local` por defecto. Con `s3` hay que definir `S3_ENDPOINT_URL`,
  `S3_ACCESS_KEY`, `S3_SECRET_KEY` y `S3_BUCKET`.
- Cambiar a `s3` no mueve archivos: ejecutar antes
  `python -m app.cli.import_documents_to_s3 --dry-run`.
- Servicio `minio` en `compose.yaml`, puerto 9000 (API) y 9001 (consola).
  **No verificado en este entorno**: el registro solo permite imágenes
  `library/*` y no deja descargar `minio/minio`. Hay que confirmar el tag
  antes de depender de él.
- El bucket se crea al arrancar solo con `S3_CREATE_BUCKET=true`.

## Retención de versiones
- `RETENTION_HOT_DAYS=90` y `RETENTION_TIERING_ENABLED=true`.
- Ejecutar la política con `python -m app.cli.apply_retention --dry-run`.
- La política solo archiva; nunca borra contenido.

## Respaldo e integridad
- `pg_dump`, `pg_restore`, `createdb` y `dropdb` están en la imagen (cliente 17).
- `scripts/backup.sh` genera el respaldo completo. `BACKUP_REMOTE=required`
  convierte la falta de copia externa en fallo.
- Verificar una restauración:
  `python -m app.cli.verify_backup --dump <dump> --manifest <manifiesto>`
- Verificar integridad del almacenamiento:
  `python -m app.cli.verify_integrity --check-orphans`
- Copia externa: `python -m app.cli.remote_backup --status`.
- Procedimiento completo y probado en `docs/RESTORE.md`.

## Destino externo
- `BACKUP_REMOTE_ENDPOINT` **debe** apuntar a una máquina o proveedor distinto
  del que sirve los documentos.
- El servicio `minio-backup` de `compose.yaml` está en el mismo host: sirve para
  ejercitar el mecanismo, no para sobrevivir a un incendio.
- **No verificado en este entorno**: `minio/minio` no se puede descargar. El
  mecanismo S3 sí se probó contra `moto.server` (puerto 5099) por HTTP real.

Nunca almacenar secretos en este archivo.
