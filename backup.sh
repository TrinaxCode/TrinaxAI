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
  tar -czf "$out" \
    --exclude='chat-pwa/node_modules' \
    --exclude='chat-pwa/dist' \
    --exclude='.venv' \
    -C "$ROOT" \
    .env storage local_sources 2>/dev/null || true
  echo "$out"
}

restore_backup() {
  local archive="${2:-}"
  if [ -z "$archive" ] || [ ! -f "$archive" ]; then
    echo "Usage: ./backup.sh restore /path/to/trinaxai-backup.tar.gz (or --help)" >&2
    exit 1
  fi
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
