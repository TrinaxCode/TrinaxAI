#!/usr/bin/env bash
# TrinaxAI - cross-platform AI shutdown wrapper.
# Stops Ollama + RAG API and keeps the PWA available for remote restart.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  PY="$SCRIPT_DIR/.venv/bin/python"
elif [ -x "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
  PY="$SCRIPT_DIR/.venv/Scripts/python.exe"
else
  PY="${TRINAXAI_PYTHON:-python3}"
fi

echo "TrinaxAI: stopping AI services..."
TRINAXAI_PRIVILEGED_WRAPPER=1 "$PY" "$SCRIPT_DIR/service_manager.py" stop-ai --base-dir "$SCRIPT_DIR"
echo "TrinaxAI: AI services stopped. The PWA remains available."
