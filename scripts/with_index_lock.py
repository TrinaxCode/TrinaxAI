#!/usr/bin/env python3
"""Run a command while the transactional index store is quiescent."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Run by path from backup.sh: do not depend on the venv's editable-install
# mapping, which predates the ``trinaxai`` package on upgraded installs.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trinaxai.core import exclusive_process_lock  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a command is required after --")

    root = Path(args.root).expanduser().resolve()
    lock = root / "storage" / ".indexing.lock"
    with exclusive_process_lock(lock, timeout=max(1.0, args.timeout)):
        result = subprocess.run(command, cwd=root, check=False, env=os.environ.copy())
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
