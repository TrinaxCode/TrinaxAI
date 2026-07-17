#!/usr/bin/env bash
# TrinaxAI backup/restore for local state and imported sources.
set -euo pipefail
# Backups contain tokens, conversations, attachments and private sources.
# Never let a permissive caller umask expose them to a group or other users.
umask 077

usage() {
  cat <<EOF
TrinaxAI Backup/Restore

Usage:
  ./backup.sh                         Create a backup (default)
  ./backup.sh create                  Create a timestamped backup
  ./backup.sh restore ARCHIVE         Restore from an archive
  ./backup.sh --help                  Show this help

Backups include: .env, storage/, local_sources/
Backups exclude: runtime locks, .venv, chat-pwa/node_modules, chat-pwa/dist

Environment variables:
  TRINAXAI_BACKUP_DIR   Backup directory (default: ./backups)
EOF
  exit 0
}

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && usage

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${TRINAXAI_BACKUP_DIR:-$ROOT/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
ACTION="${1:-create}"
SERVICES_PAUSED=0

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

quiesce_services() {
  [ "${TRINAXAI_BACKUP_QUIESCE:-1}" = "1" ] || return 0
  [ -f "$ROOT/service_manager.py" ] || return 0
  local python_bin status
  python_bin="$(python_command)"
  [ -n "$python_bin" ] || return 0
  status="$($python_bin "$ROOT/service_manager.py" status --base-dir "$ROOT" 2>/dev/null || true)"
  if grep -q '^rag_api: running' <<<"$status"; then
    "$python_bin" "$ROOT/service_manager.py" stop-ai --base-dir "$ROOT" >/dev/null
    status="$($python_bin "$ROOT/service_manager.py" status --base-dir "$ROOT" 2>/dev/null || true)"
    if grep -q '^rag_api: running' <<<"$status"; then
      echo "Error: could not pause the API for a consistent backup." >&2
      return 1
    fi
    SERVICES_PAUSED=1
  fi
}

resume_services() {
  if [ "$SERVICES_PAUSED" = "1" ] && [ -f "$ROOT/service_manager.py" ]; then
    local python_bin
    python_bin="$(python_command)"
    [ -z "$python_bin" ] || "$python_bin" "$ROOT/service_manager.py" start-ai --base-dir "$ROOT" >/dev/null 2>&1 || true
    SERVICES_PAUSED=0
  fi
}

mkdir -p "$BACKUP_DIR"
chmod 0700 "$BACKUP_DIR" 2>/dev/null || true

create_backup() {
  local out="$BACKUP_DIR/trinaxai-backup-$STAMP.tar.gz"

  # Only include paths that actually exist, so a missing optional item (e.g. a
  # fresh checkout without .env) does not abort the whole backup.
  local items=()
  local candidate
  for candidate in .env storage local_sources; do
    [ -e "$ROOT/$candidate" ] && items+=("$candidate")
  done
  if [ "${#items[@]}" -eq 0 ]; then
    echo "Error: nothing to back up (.env, storage, local_sources all missing)" >&2
    exit 1
  fi

  local tmp
  tmp="$(mktemp "$BACKUP_DIR/.trinaxai-backup-$STAMP.XXXXXX")"

  quiesce_services
  trap resume_services EXIT

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
    echo "Error: backup failed while creating $out" >&2
    rm -f "$tmp"
    exit 1
  fi

  # A valid archive must be non-empty and readable by tar.
  if [ ! -s "$tmp" ] || ! tar -tzf "$tmp" >/dev/null 2>&1; then
    echo "Error: backup archive is empty or corrupt: $out" >&2
    rm -f "$tmp"
    exit 1
  fi

  chmod 0600 "$tmp"
  mv -f "$tmp" "$out"
  resume_services
  trap - EXIT

  echo "$out"
}

restore_backup() {
  local archive="${2:-}"
  if [ -z "$archive" ] || [ ! -f "$archive" ]; then
    echo "Usage: ./backup.sh restore /path/to/trinaxai-backup.tar.gz (or --help)" >&2
    exit 1
  fi

  local python_bin stage rollback
  python_bin="$(command -v python3 || command -v python || true)"
  if [ -z "$python_bin" ]; then
    echo "Error: Python is required for safe staged restore" >&2
    exit 1
  fi
  stage="$(mktemp -d "$ROOT/.trinaxai-restore.XXXXXX")"
  rollback="$(mktemp -d "$ROOT/.trinaxai-rollback.XXXXXX")"

  if ! "$python_bin" - "$archive" "$stage" <<'PY'
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

archive, stage = Path(sys.argv[1]), Path(sys.argv[2])
allowed = {".env", "storage", "local_sources"}
try:
    handle = tarfile.open(archive, "r:gz")
except (OSError, tarfile.TarError) as exc:
    raise SystemExit(f"Error: could not read archive: {exc}")
with handle:
    members = handle.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"Error: archive contains path traversal: {member.name}")
        if not path.parts or path.parts[0] not in allowed:
            raise SystemExit(f"Error: archive contains unexpected path: {member.name}")
        if path.parts[0] == ".env" and (len(path.parts) != 1 or not member.isfile()):
            raise SystemExit(f"Error: archive contains invalid .env entry: {member.name}")
        if not (member.isdir() or member.isfile()):
            raise SystemExit(f"Error: archive contains unsafe entry type: {member.name}")
    for member in members:
        target = stage.joinpath(*PurePosixPath(member.name).parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            continue
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        source = handle.extractfile(member)
        if source is None:
            raise SystemExit(f"Error: cannot extract regular file: {member.name}")
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
  echo "Restored $archive"
}

case "$ACTION" in
  create|"")
    create_backup
    ;;
  restore)
    restore_backup "$@"
    ;;
  *)
    echo "Usage: ./backup.sh [create|restore ARCHIVE] (or --help)" >&2
    exit 1
    ;;
esac
