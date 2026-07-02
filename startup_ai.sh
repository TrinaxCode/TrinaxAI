#!/usr/bin/env bash
# TrinaxAI - cross-platform AI startup wrapper.
# Starts Ollama + RAG API while leaving the PWA/service supervisor intact.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  PY="$SCRIPT_DIR/.venv/bin/python"
elif [ -x "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
  PY="$SCRIPT_DIR/.venv/Scripts/python.exe"
else
  PY="${TRINAXAI_PYTHON:-python3}"
fi

echo "TrinaxAI: starting AI services..."
TRINAXAI_PRIVILEGED_WRAPPER=1 "$PY" "$SCRIPT_DIR/service_manager.py" start-ai --base-dir "$SCRIPT_DIR"
echo "TrinaxAI: AI services started."
echo "PWA: https://localhost:3334"
echo "RAG API: http://localhost:3333"
echo "Ollama: http://localhost:11434"
