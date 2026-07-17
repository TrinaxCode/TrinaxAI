"""Run pytest outside the GitHub Actions console process group on Windows."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    completed = subprocess.run(  # noqa: S603 - current interpreter and fixed module
        [sys.executable, "-m", "pytest", "-q"],
        creationflags=flags,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
