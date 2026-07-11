#!/usr/bin/env bash
# TrinaxAI backup/restore for local state and imported sources.
set -euo pipefail

usage() {
  cat <<EOF
TrinaxAI Backup/Restore

Usage:
  ./backup.sh                         Create a backup (default)
  ./backup.sh create                  Create a timestamped backup
  ./backup.sh restore ARCHIVE         Restore from an archive
  ./backup.sh --help                  Show this help

Backups include: .env, storage/, local_sources/
Backups exclude: .venv, chat-pwa/node_modules, chat-pwa/dist

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

mkdir -p "$BACKUP_DIR"

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

  if ! tar -czf "$out" \
    --exclude='chat-pwa/node_modules' \
    --exclude='chat-pwa/dist' \
    --exclude='.venv' \
    -C "$ROOT" \
    "${items[@]}"; then
    echo "Error: backup failed while creating $out" >&2
    rm -f "$out"
    exit 1
  fi

  # A valid archive must be non-empty and readable by tar.
  if [ ! -s "$out" ] || ! tar -tzf "$out" >/dev/null 2>&1; then
    echo "Error: backup archive is empty or corrupt: $out" >&2
    rm -f "$out"
    exit 1
  fi

  echo "$out"
}

restore_backup() {
  local archive="${2:-}"
  if [ -z "$archive" ] || [ ! -f "$archive" ]; then
    echo "Usage: ./backup.sh restore /path/to/trinaxai-backup.tar.gz (or --help)" >&2
    exit 1
  fi

  local listing
  listing="$(tar -tzf "$archive" 2>/dev/null)" || {
    echo "Error: could not read archive listing from $archive" >&2
    exit 1
  }

  while IFS= read -r entry; do
    [ -z "$entry" ] && continue
    # reject absolute paths
    case "$entry" in
      /*) echo "Error: archive contains absolute path: $entry" >&2; exit 1;;
    esac
    # reject path traversal
    case "$entry" in
      *..*) echo "Error: archive contains path traversal: $entry" >&2; exit 1;;
    esac
  done <<< "$listing"

  tar --no-absolute-names -xzf "$archive" -C "$ROOT"
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
