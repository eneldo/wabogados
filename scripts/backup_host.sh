#!/usr/bin/env bash
# Respaldo programado del entorno Fedora para WABOGADOS.
#
# No reinventa la maquinaria: ejecuta scripts/backup.sh del proyecto (dump en
# formato custom, copia de objetos, MANIFEST.sha256, verificación por digest y
# prueba de restauración en base raíz) y añade lo que este host necesita:
#
#   1. Copia secundaria al disco externo (Seagate), si está montado.
#      El disco se monta en /run/media/vaner/... que desaparece al
#      desconectarlo: la copia local siempre existe y la externa es un extra
#      anunciado, no una condición.
#   2. Retención de directorios por antigüedad, local y externa.
#   3. Llave de exclusión mutua para no solapar dos corridas.
#   4. Entorno reproducible para cron (PATH, directorio de trabajo).
#
# Uso:
#   scripts/backup_host.sh                        # corrida manual
#   BACKUP_TAG=manual scripts/backup_host.sh      # con etiqueta distinta
#
# El crontab del usuario lanza esto a diario; la entrada cron no versiona nada.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO}"

DESTINO_EXTERNO="${BACKUP_EXTERNO:-/run/media/vaner/Seagate Expansion Drive/RESPALDO_WABOGADOS}"
KEEP_LOCAL="${BACKUP_KEEP_LOCAL:-14}"
KEEP_EXTERNO="${BACKUP_KEEP_EXTERNO:-30}"
LOG="${REPO}/backups/backup.log"

# cron parte con PATH=/usr/bin; docker y las herramientas están ahí.
export PATH="/usr/bin:/usr/local/bin:${HOME}/.local/bin"

mkdir -p "$(dirname "${LOG}")"
exec 9>"${REPO}/backups/.backup.lock"
if ! flock -n 9; then
  echo "$(date -u '+%F %T') [backup_host] otra corrida está en curso; se omite" >> "${LOG}"
  exit 0
fi

{
echo "════════ $(date -u '+%F %T UTC') ════════"

if scripts/backup.sh; then
  RUN_DIR="${REPO}/backups/$(ls -1 backups | grep -E '^[0-9]{8}T[0-9]{6}Z$' | sort | tail -1)"
  echo "[backup_host] respaldo local completo: ${RUN_DIR}"

  # --- Copia secundaria al disco externo ---------------------------------
  # El original vive en el repositorio; esta es la copia que sobrevive a un
  # problema del disco del sistema. Se compara el digest del dump para que
  # «copiado» signifique «copiado sin cambios».
  if [ -d "$(dirname "${DESTINO_EXTERNO}")" ]; then
    mkdir -p "${DESTINO_EXTERNO}"
    if rsync -a --chmod=go-w "${RUN_DIR}/" "${DESTINO_EXTERNO}/$(basename "${RUN_DIR}")/"; then
      remoto="${DESTINO_EXTERNO}/$(basename "${RUN_DIR}")/postgres.dump"
      if cmp -s "${RUN_DIR}/postgres.dump" "${remoto}"; then
        echo "[backup_host] copia externa idéntica verificada: ${remoto}"
      else
        echo "[backup_host][ERROR] la copia externa del dump NO coincide" >&2
        exit 1
      fi

      # Retención externa: los directorios son UTC-stamps, orden léxico = orden temporal.
      cd "${DESTINO_EXTERNO}"
      ls -1d [0-9]*T[0-9]*Z 2>/dev/null | sort | head -n -"${KEEP_EXTERNO}" \
        | tr '\n' '\0' | xargs -0 -r rm -rf
      cd "${REPO}"
      echo "[backup_host] retención externa aplicada (quedan ${KEEP_EXTERNO})"
    else
      echo "[backup_host][ERROR] no se pudo copiar al disco externo" >&2
      exit 1
    fi
  else
    echo "[backup_host][AVISO] el disco externo no está montado: ${DESTINO_EXTERNO}"
    echo "[backup_host][AVISO] solo existe la copia local en ${REPO}/backups"
  fi

  # --- Retención local ---------------------------------------------------
  cd "${REPO}/backups"
  ls -1d [0-9]*T[0-9]*Z 2>/dev/null | sort | head -n -"${KEEP_LOCAL}" \
    | tr '\n' '\0' | xargs -0 -r rm -rf
  cd "${REPO}"
  echo "[backup_host] retención local aplicada (quedan ${KEEP_LOCAL})"
else
  echo "[backup_host][ERROR] scripts/backup.sh falló" >&2
  exit 1
fi
} >> "${LOG}" 2>&1

tail -3 "${LOG}" | sed 's/^/[backup_host] /'
echo "[backup_host] terminado — log: ${LOG}"
