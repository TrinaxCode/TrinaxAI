#!/usr/bin/env bash
# TrinaxAI backup/restore for local state and imported sources.
set -euo pipefail

LANGUAGE="${TRINAXAI_LANG:-${LANG:-en}}"
LANGUAGE_LOWER="$(printf '%s' "$LANGUAGE" | tr '[:upper:]' '[:lower:]')"
case "$LANGUAGE_LOWER" in es*|*_es*) LANGUAGE=es ;; *) LANGUAGE=en ;; esac
export TRINAXAI_LANG="$LANGUAGE"

t() {
  if [ "$LANGUAGE" = "es" ]; then printf '%s' "$2"; else printf '%s' "$1"; fi
}

# Backups contain tokens, conversations, attachments and private sources.
# Never let a permissive caller umask expose them to a group or other users.
umask 077

usage() {
  if [ "$LANGUAGE" = "es" ]; then
    cat <<EOF
Backup/restauración de TrinaxAI

Uso:
  ./backup.sh                         Crear un backup (por defecto)
  ./backup.sh create                  Crear un backup con timestamp
  ./backup.sh restore ARCHIVE         Restaurar un archivo
  ./backup.sh --help                  Mostrar esta ayuda

Incluye: .env, storage/, local_sources/
Excluye: locks de ejecución, .venv, chat-pwa/node_modules, chat-pwa/dist

Variable: TRINAXAI_BACKUP_DIR (directorio por defecto: ./backups)
EOF
  else
    cat <<EOF
TrinaxAI Backup/Restore

Usage:
  ./backup.sh                         Create a backup (default)
  ./backup.sh create                  Create a timestamped backup
  ./backup.sh restore ARCHIVE         Restore from an archive
  ./backup.sh --help                  Show this help

Backups include: .env, storage/, local_sources/
Backups exclude: runtime locks, .venv, chat-pwa/node_modules, chat-pwa/dist

Environment variable: TRINAXAI_BACKUP_DIR (default: ./backups)
EOF
  fi
  exit 0
}

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && usage

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${TRINAXAI_BACKUP_DIR:-$ROOT/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
ACTION="${1:-create}"
SERVICES_PAUSED=0
API_STATUS_PREFIX='TrinaxAI RAG API: running'

python_command() {
  if [ -n "${TRINAXAI_PYTHON:-}" ] && [ -x "${TRINAXAI_PYTHON}" ]; then
    printf '%s\n' "${TRINAXAI_PYTHON}"
  elif [ -x "$ROOT/.venv/bin/python" ]; then
    printf '%s\n' "$ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  else
    command -v python || true
  fi
}

api_is_running() {
  grep -Eq "^${API_STATUS_PREFIX}([[:space:]]|$)" <<<"$1"
}

quiesce_services() {
  [ "${TRINAXAI_BACKUP_QUIESCE:-1}" = "1" ] || return 0
  [ -f "$ROOT/service_manager.py" ] || return 0
  local python_bin status
  python_bin="$(python_command)"
  [ -n "$python_bin" ] || return 0
  if ! status="$($python_bin "$ROOT/service_manager.py" status --base-dir "$ROOT" 2>/dev/null)"; then
    echo "$(t 'Error: could not read service status before backup.' 'Error: no se pudo leer el estado de los servicios antes del backup.')" >&2
    return 1
  fi
  if api_is_running "$status"; then
    SERVICES_PAUSED=1
    if ! "$python_bin" "$ROOT/service_manager.py" stop-ai --base-dir "$ROOT" >/dev/null; then
      echo "$(t 'Error: could not pause the API for a consistent backup.' 'Error: no se pudo pausar la API para un backup consistente.')" >&2
      return 1
    fi
    if ! status="$($python_bin "$ROOT/service_manager.py" status --base-dir "$ROOT" 2>/dev/null)"; then
      echo "$(t 'Error: could not confirm the API stopped before backup.' 'Error: no se pudo confirmar que la API se detuvo antes del backup.')" >&2
      return 1
    fi
    if api_is_running "$status"; then
      echo "$(t 'Error: could not pause the API for a consistent backup.' 'Error: no se pudo pausar la API para un backup consistente.')" >&2
      return 1
    fi
  fi
}

resume_services() {
  if [ "$SERVICES_PAUSED" = "1" ] && [ -f "$ROOT/service_manager.py" ]; then
    local python_bin status
    python_bin="$(python_command)"
    if [ -z "$python_bin" ] || ! "$python_bin" "$ROOT/service_manager.py" start-ai --base-dir "$ROOT" >/dev/null 2>&1; then
      echo "$(t 'Error: could not restore the API after backup.' 'Error: no se pudo restaurar la API después del backup.')" >&2
      return 1
    fi
    if ! status="$($python_bin "$ROOT/service_manager.py" status --base-dir "$ROOT" 2>/dev/null)" || ! api_is_running "$status"; then
      echo "$(t 'Error: could not confirm the API restarted after backup.' 'Error: no se pudo confirmar que la API se reinició después del backup.')" >&2
      return 1
    fi
    SERVICES_PAUSED=0
  fi
}

mkdir -p "$BACKUP_DIR"
chmod 0700 "$BACKUP_DIR" 2>/dev/null || true

create_backup() {
  local out
  out="$(mktemp "$BACKUP_DIR/trinaxai-backup-$STAMP.tar.gz.XXXXXX")"

  # Only include paths that actually exist, so a missing optional item (e.g. a
  # fresh checkout without .env) does not abort the whole backup.
  local items=()
  local candidate
  for candidate in .env storage local_sources; do
    [ -e "$ROOT/$candidate" ] && items+=("$candidate")
  done
  if [ "${#items[@]}" -eq 0 ]; then
    echo "$(t 'Error: nothing to back up (.env, storage, local_sources all missing)' 'Error: no hay nada que respaldar (faltan .env, storage y local_sources)')" >&2
    exit 1
  fi

  local tmp="$out"

  trap resume_services EXIT
  quiesce_services

  local tar_command=(tar -czf "$tmp" \
    --exclude='storage/.indexing.lock' \
    --exclude='storage/.inference.lock' \
    --exclude='storage/.index-transaction.json' \
    --exclude='storage/.txn-*' \
    --exclude='chat-pwa/node_modules' \
    --exclude='chat-pwa/dist' \
    --exclude='.venv' \
    -C "$ROOT" \
    "${items[@]}")
  local python_bin
  python_bin="$(python_command)"
  if [ -n "$python_bin" ] && [ -f "$ROOT/scripts/with_index_lock.py" ]; then
    tar_command=("$python_bin" "$ROOT/scripts/with_index_lock.py" --root "$ROOT" -- "${tar_command[@]}")
  fi
  if ! "${tar_command[@]}"; then
    echo "$(t "Error: backup failed while creating $out" "Error: el backup falló al crear $out")" >&2
    rm -f "$tmp"
    exit 1
  fi

  # A valid archive must be non-empty and readable by tar.
  if [ ! -s "$tmp" ] || ! tar -tzf "$tmp" >/dev/null 2>&1; then
    echo "$(t "Error: backup archive is empty or corrupt: $out" "Error: el archivo de backup está vacío o dañado: $out")" >&2
    rm -f "$tmp"
    exit 1
  fi

  chmod 0600 "$tmp"
  resume_services
  trap - EXIT

  echo "$out"
}

restore_backup() {
  local archive="${2:-}"
  if [ -z "$archive" ] || [ ! -f "$archive" ]; then
    echo "$(t 'Usage: ./backup.sh restore /path/to/trinaxai-backup.tar.gz (or --help)' 'Uso: ./backup.sh restore /ruta/a/trinaxai-backup.tar.gz (o --help)')" >&2
    exit 1
  fi

  local python_bin stage rollback
  python_bin="$(command -v python3 || command -v python || true)"
  if [ -z "$python_bin" ]; then
    echo "$(t 'Error: Python is required for safe staged restore' 'Error: se requiere Python para una restauración segura por etapas')" >&2
    exit 1
  fi
  stage="$(mktemp -d "$ROOT/.trinaxai-restore.XXXXXX")"
  rollback="$(mktemp -d "$ROOT/.trinaxai-rollback.XXXXXX")"

  if ! "$python_bin" - "$archive" "$stage" <<'PY'
import os
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

_lang = "es" if os.environ.get("TRINAXAI_LANG", "en").startswith("es") else "en"


def _m(english: str, spanish: str) -> str:
    return spanish if _lang == "es" else english


archive, stage = Path(sys.argv[1]), Path(sys.argv[2])
allowed = {".env", "storage", "local_sources"}
try:
    handle = tarfile.open(archive, "r:gz")
except (OSError, tarfile.TarError) as exc:
    raise SystemExit(_m(f"Error: could not read archive: {exc}", f"Error: no se pudo leer el archivo: {exc}"))
with handle:
    members = handle.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(_m(f"Error: archive contains path traversal: {member.name}", f"Error: el archivo contiene un salto de ruta: {member.name}"))
        if not path.parts or path.parts[0] not in allowed:
            raise SystemExit(_m(f"Error: archive contains unexpected path: {member.name}", f"Error: el archivo contiene una ruta inesperada: {member.name}"))
        if path.parts[0] == ".env" and (len(path.parts) != 1 or not member.isfile()):
            raise SystemExit(_m(f"Error: archive contains invalid .env entry: {member.name}", f"Error: el archivo contiene una entrada .env inválida: {member.name}"))
        if not (member.isdir() or member.isfile()):
            raise SystemExit(_m(f"Error: archive contains unsafe entry type: {member.name}", f"Error: el archivo contiene un tipo de entrada inseguro: {member.name}"))
    for member in members:
        target = stage.joinpath(*PurePosixPath(member.name).parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            continue
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        source = handle.extractfile(member)
        if source is None:
            raise SystemExit(_m(f"Error: cannot extract regular file: {member.name}", f"Error: no se puede extraer el archivo: {member.name}"))
        with source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
        target.chmod(0o600)
PY
  then
    rm -rf "$stage" "$rollback"
    exit 1
  fi

  # Validate an untrusted archive completely before disrupting live services.
  quiesce_services
  trap resume_services EXIT

  local applied=()
  rollback_restore() {
    local item
    for item in "${applied[@]}"; do
      rm -rf -- "${ROOT:?}/$item"
      [ -e "$rollback/$item" ] && mv "$rollback/$item" "$ROOT/$item"
    done
    rm -rf "$stage" "$rollback"
  }
  trap rollback_restore ERR INT TERM
  local candidate
  for candidate in .env storage local_sources; do
    [ -e "$stage/$candidate" ] || continue
    applied+=("$candidate")
    [ -e "$ROOT/$candidate" ] && mv "$ROOT/$candidate" "$rollback/$candidate"
    mv "$stage/$candidate" "$ROOT/$candidate"
  done
  trap - ERR INT TERM
  rm -rf "$stage" "$rollback"
  [ -f "$ROOT/.env" ] && chmod 0600 "$ROOT/.env"
  [ -d "$ROOT/storage" ] && chmod -R go-rwx "$ROOT/storage"
  [ -d "$ROOT/local_sources" ] && chmod -R go-rwx "$ROOT/local_sources"
  resume_services
  trap - EXIT
  echo "$(t "Restored $archive" "Restaurado $archive")"
}

case "$ACTION" in
  create|"")
    create_backup
    ;;
  restore)
    restore_backup "$@"
    ;;
  *)
    echo "$(t 'Usage: ./backup.sh [create|restore ARCHIVE] (or --help)' 'Uso: ./backup.sh [create|restore ARCHIVO] (o --help)')" >&2
    exit 1
    ;;
esac
