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
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    sys.stdout.write(completed.stdout)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
