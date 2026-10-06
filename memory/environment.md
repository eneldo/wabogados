# Entorno

## Sistema operativo
- Windows con PowerShell 5.1. El separador de comandos es `;`, nunca `&&`.
- El intérprete disponible es `python`, no `python3`.
- Cuidado con `Set-Content` en PowerShell 5.1: añade BOM y puede alterar
  codificación. Para escribir Markdown usar la herramienta de edición.

## Python
- 3.12 en desarrollo; 3.12.11-slim en la imagen Docker.
- Dependencias instaladas en `/opt/venv` dentro del contenedor.

## Node.js
- Next.js 16 con React 19, TypeScript strict y Tailwind 4.

## Docker
- Compose con `postgres:17.6-alpine`, `backend` y `frontend`.
- `compose.test.yaml` monta `./backend` en `/build` y usa PostgreSQL efímero en
  `tmpfs`; el volumen debe coincidir con el `WORKDIR` de la imagen de test.
- Ejecutar la suite con:
  `docker compose -f compose.yaml -f compose.test.yaml run --rm test`
- `docker compose up --force-recreate` sin `--build` reutiliza la imagen
  anterior; hay que incluir `--build`.
- Los volúmenes con nombre heredan la propiedad del directorio existente en la
  imagen. Si el directorio no se crea, el volumen nace como root y el usuario no
  root no puede escribir.

## Base de datos
- PostgreSQL 17. La conexión host → Docker presenta fallos intermitentes: las
  pruebas se ejecutan siempre dentro de Docker.
- Si un test se ejecuta con un motor distinto, el `postgres-test` queda
  contaminado. Reiniciarlo antes de la suite:
  `docker compose -f compose.yaml -f compose.test.yaml restart postgres-test`

## Servicios
- Backend: <http://localhost:8000> (healthcheck en `/api/v1/health/ready`).
- Frontend: <http://localhost:3000>.
- PostgreSQL local: `localhost:5432`.

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
