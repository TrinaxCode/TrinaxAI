#!/usr/bin/env bash
# TrinaxAI - cross-platform AI shutdown wrapper.
# Stops Ollama + RAG API and keeps the PWA available for remote restart.

set -euo pipefail

LANGUAGE="${TRINAXAI_LANG:-${LANG:-en}}"
LANGUAGE_LOWER="$(printf '%s' "$LANGUAGE" | tr '[:upper:]' '[:lower:]')"
case "$LANGUAGE_LOWER" in es*|*_es*) LANGUAGE=es ;; *) LANGUAGE=en ;; esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  PY="$SCRIPT_DIR/.venv/bin/python"
elif [ -x "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
  PY="$SCRIPT_DIR/.venv/Scripts/python.exe"
else
  PY="${TRINAXAI_PYTHON:-python3}"
fi

if [ "$LANGUAGE" = "es" ]; then echo "TrinaxAI: deteniendo servicios de IA..."; else echo "TrinaxAI: stopping AI services..."; fi
"$PY" "$SCRIPT_DIR/service_manager.py" stop-ai --base-dir "$SCRIPT_DIR"
if [ "$LANGUAGE" = "es" ]; then echo "TrinaxAI: servicios de IA detenidos. La PWA sigue disponible."; else echo "TrinaxAI: AI services stopped. The PWA remains available."; fi
