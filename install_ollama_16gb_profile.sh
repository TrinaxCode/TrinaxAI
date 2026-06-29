#!/usr/bin/env bash
# Compatibility wrapper for older TrinaxAI install instructions.
# The canonical installer is install.sh; this keeps old links working.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/install.sh" --profile 16gb "$@"
