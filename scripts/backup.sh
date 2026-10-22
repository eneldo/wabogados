#!/usr/bin/env bash
# WABOGADOS backup: PostgreSQL, originals, critical derivatives and configuration.
#
# MASTER_PROMPT section 44 requires all four, and requires that the restore be
# documented and tested. This script creates the backup and then proves the
# database part can be restored.
#
# Ordering matters and is not arbitrary. Document content is written to storage
# BEFORE its database row commits, so an object can exist without a row but a row
# never exists without its object. Backing up the database first and the objects
# after can only leave an extra object in the backup. The other order could
# produce a restorable database with rows pointing at objects the backup does not
# contain.
#
# Usage (from the repository root):
#   scripts/backup.sh
#   BACKUP_TAG=daily scripts/backup.sh
#   SKIP_RESTORE_VERIFY=1 scripts/backup.sh   # not recommended

set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-backups}"
BACKUP_TAG="${BACKUP_TAG:-auto}"
KEEP="${BACKUP_KEEP:-30}"
SKIP_RESTORE_VERIFY="${SKIP_RESTORE_VERIFY:-0}"
# Set to "required" to turn a missing off site copy into a hard failure. The
# default warns loudly, because failing every local run makes people disable the
# check, which is worse than a loud warning.
REMOTE_TARGET="${BACKUP_REMOTE:-}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "${BACKUP_ROOT}"
# Absoluto a propósito: compose run resuelve un `-v` relativo como volumen
# nombrado, no como directorio del host, y montaría vacío o rechazaría el nombre.
RUN_DIR="$(cd "${BACKUP_ROOT}" && pwd)/${STAMP}"

mkdir -p "${RUN_DIR}"

log() { printf '[backup] %s\n' "$*"; }
fail() { printf '[backup][ERROR] %s\n' "$*" >&2; exit 1; }

log "directorio: ${RUN_DIR}"

# --- 1. Configuration -----------------------------------------------------
# Without the settings, a restore is guesswork: the dump alone cannot say which
# storage backend or which tiering policy it expects.
log "1/4 configuración"
CONFIG_FILE="${RUN_DIR}/config.json"
: > "${CONFIG_FILE}"
{
  printf '{\n'
  printf '  "created_at": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '  "host": "%s",\n' "$(hostname)"
  # Only the non secret variables. A backup that contains credentials is a
  # liability, not a safeguard.
  env | grep -E '^(STORAGE_BACKEND|S3_BUCKET|S3_ENDPOINT_URL|S3_ADDRESSING_STYLE|S3_ARCHIVE_STORAGE_CLASS|STORAGE_ROOT|MAX_UPLOAD_BYTES|RETENTION_HOT_DAYS|RETENTION_TIERING_ENABLED|APP_ENVIRONMENT)=' \
    | sed 's/^/  "/; s/$/",/; s/="/": "/' \
    || true
  printf '  "alembic_revision": "%s"\n' "$(
    docker compose exec -T backend alembic current 2>/dev/null | grep -oE '[0-9a-f]{10,}( \(head\))?' | head -1 | tr -d ' ' || echo "unknown"
  )"
  printf '}\n'
} > "${CONFIG_FILE}"
log "  ${CONFIG_FILE}"

# --- 2. PostgreSQL --------------------------------------------------------
log "2/4 PostgreSQL"
docker compose exec -T postgres sh -c \
  'pg_dump --format=custom --compress=9 --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  > "${RUN_DIR}/postgres.dump"
[ -s "${RUN_DIR}/postgres.dump" ] || fail "pg_dump no produjo un archivo utilizable"
sha256sum "${RUN_DIR}/postgres.dump" | cut -d' ' -f1 > "${RUN_DIR}/postgres.dump.sha256"

# The manifest is what turns a file into a restorable backup: it records the
# digest, the schema revision and the configuration the dump expects.
REV="$(
  docker compose exec -T backend alembic current 2>/dev/null \
    | grep -oE '[0-9a-f]{10,}( \(head\))?' | head -1 | tr -d ' ' || echo "unknown"
)"
{
  printf '{\n'
  printf '  "sha256": "%s",\n' "$(cat "${RUN_DIR}/postgres.dump.sha256")"
  printf '  "created_at": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '  "alembic_revision": "%s",\n' "${REV}"
  printf '  "storage_backend": "%s",\n' "${STORAGE_BACKEND:-local}"
  printf '  "file": "postgres.dump"\n'
  printf '}\n'
} > "${RUN_DIR}/postgres.manifest.json"
log "  $(du -h "${RUN_DIR}/postgres.dump" | cut -f1) en postgres.dump (rev ${REV})"

# --- 3. Originals ---------------------------------------------------------
# Mirrors the bucket to a separate location. A copy inside the same volume is
# not a backup; it survives nothing.
log "3/4 originales (objetos)"
OBJECTS_DIR="${RUN_DIR}/objects"
if [ "${STORAGE_BACKEND:-local}" = "s3" ]; then
  log "  usando mc mirror contra ${S3_BUCKET}"
  docker run --rm \
    -e MC_HOST_wabo="http://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT_URL#*://}" \
    -v "${RUN_DIR}:/backup" \
    minio/mc:latest \
    mirror --overwrite --preserve "wabo/${S3_BUCKET}" "/backup/objects" \
    || fail "mc mirror falló: el respaldo de objetos no está garantizado"
else
  log "  copiando el árbol local de documentos"
  mkdir -p "${OBJECTS_DIR}"
  # `cp -a` preserves timestamps; a restored document that looks freshly written
  # is misleading when reviewing an audit trail.
  docker compose exec -T backend sh -c \
    'tar -cf - -C /var/lib/wabogados/storage .' \
    | tar -xf - -C "${OBJECTS_DIR}"
fi
[ -d "${OBJECTS_DIR}" ] || fail "no se obtuvo el directorio de objetos"
OBJECT_COUNT="$(find "${OBJECTS_DIR}" -type f | wc -l | tr -d ' ')"
log "  ${OBJECT_COUNT} objetos"
# Informativo, y nada más. Este número NO verifica el respaldo: sobrevive a un
# archivo truncado, que es exactamente el fallo que importa. La verificación por
# digest se hace más abajo, con app.cli.verify_backup_files.
printf '%s\n' "${OBJECT_COUNT}" > "${RUN_DIR}/objects.count"

# --- 4. Critical derivatives ---------------------------------------------
# Alembic files are what a restored database is compared against.
log "4/4 derivados críticos (migraciones)"
MIGRATIONS_DIR="${RUN_DIR}/migrations"
mkdir -p "${MIGRATIONS_DIR}"
docker compose exec -T backend sh -c 'tar -cf - -C /app alembic alembic.ini' \
  | tar -xf - -C "${MIGRATIONS_DIR}"
[ -d "${MIGRATIONS_DIR}/alembic/versions" ] || fail "no se pudieron copiar las migraciones"

# --- Manifest -------------------------------------------------------------
log "manifiesto"
MANIFEST="${RUN_DIR}/MANIFEST.sha256"
( cd "${RUN_DIR}" && find . -type f ! -name 'MANIFEST.sha256' -print0 \
    | sort -z | xargs -0 sha256sum ) > "${MANIFEST}"
log "  ${MANIFEST} ($(wc -l < "${MANIFEST}") archivos)"

# --- Verify the files by digest ------------------------------------------
# The manifest above is worthless unless something reads it, and `objects.count`
# cannot do it: a count survives a truncated file. This re-reads every object and
# compares its digest, which is the only check that distinguishes an intact
# evidence original from half a copy.
#
# It runs before the off-site push on purpose. Pushing a corrupted backup and
# only then discovering it is corrupted wastes the transfer and, worse, leaves a
# broken copy at the far end that looks like a backup.
log "verificando objetos por digest"
set +e
docker compose run --rm --no-deps \
  -v "${RUN_DIR}:/backup:ro" \
  backend python -m app.cli.verify_backup_files \
    --manifest "/backup/MANIFEST.sha256" \
  2>&1 | tail -25
FILES_STATUS=$?
set -e
if [ "${FILES_STATUS}" != "0" ]; then
  fail "el respaldo no está íntegro por digest. No se envía a ningún destino externo."
fi

# --- Optional off-site copy ----------------------------------------------
# Implemented in Python rather than with `mc mirror` for two reasons: the
# mechanism is then covered by the test suite, and it can verify the copy by
# digest afterwards. An upload that returns success only proves the bytes left
# the process.
if [ "${REMOTE_TARGET}" = "required" ] || [ "${BACKUP_REMOTE_ENABLED:-false}" = "true" ]; then
  log "copia externa habilitada"
  set +e
  docker compose run --rm --no-deps \
    -v "${RUN_DIR}:/backup:ro" \
    backend python -m app.cli.remote_backup \
      --push "/backup/${STAMP}" \
    2>&1 | tail -20
  REMOTE_STATUS=$?
  set -e
  if [ "${REMOTE_STATUS}" != "0" ]; then
    fail "la copia externa no se pudo verificar. La copia local sigue siendo válida."
  fi

  log "comprobando que la copia externa existe y es legible"
  docker compose exec -T backend python -m app.cli.remote_backup --list \
    || fail "no se pudo leer el destino externo"
else
  log "AVISO: BACKUP_REMOTE_ENABLED no está activo."
  log "AVISO: esta copia NO sale de $(hostname). Un incendio o un ransomware"
  log "AVISO: se lleva el original y su copia a la vez. Ver docs/RESTORE.md §8."
fi

# --- Restore verification -------------------------------------------------
if [ "${SKIP_RESTORE_VERIFY}" = "1" ]; then
  log "AVISO: restauración NO verificada. Esto no es un respaldo, es una hipótesis."
else
  log "verificando que la base de datos se puede restaurar"
  # The dump is mounted read only and restored into a scratch database by
  # verify_backup, so the live database is never touched.
  set +e
  docker compose run --rm --no-deps \
    -v "${RUN_DIR}:/backup:ro" \
    backend python -m app.cli.verify_backup \
      --dump "/backup/postgres.dump" \
      --manifest "/backup/postgres.manifest.json" \
    2>&1 | tail -25
  VERIFY_STATUS=$?
  set -e
  if [ "${VERIFY_STATUS}" != "0" ]; then
    fail "la restauración no se verificó. El respaldo no es válido."
  fi
  log "  restauración verificada"
fi

log "respaldo completado en ${RUN_DIR}"
log "restaure siguiendo docs/RESTORE.md"