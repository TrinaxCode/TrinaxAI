#!/usr/bin/env bash
# TrinaxAI - cross-platform AI startup wrapper.
# Starts Ollama + RAG API while leaving the PWA/service supervisor intact.

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

if [ "$LANGUAGE" = "es" ]; then echo "TrinaxAI: iniciando servicios de IA..."; else echo "TrinaxAI: starting AI services..."; fi
"$PY" "$SCRIPT_DIR/service_manager.py" start-ai --base-dir "$SCRIPT_DIR"
if [ "$LANGUAGE" = "es" ]; then echo "TrinaxAI: servicios de IA iniciados."; else echo "TrinaxAI: AI services started."; fi
echo "PWA: https://localhost:3334"
echo "RAG API: https://localhost:3333 (HTTP fallback if no local certificate)"
echo "Ollama: http://localhost:11434"
