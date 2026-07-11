from __future__ import annotations

import sys
from typing import Any

from trinaxai_cli.commands._lifecycle import run_script


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    mapping = {
        "yes": "-NonInteractive" if sys.platform == "win32" else "--non-interactive",
        "no_backup": "-NoBackup" if sys.platform == "win32" else "--no-backup",
        "no_pull": "-NoPull" if sys.platform == "win32" else "--no-pull",
        "models": "-Models" if sys.platform == "win32" else "--models",
        "no_models": "-NoModels" if sys.platform == "win32" else "--no-models",
        "restart": "-Restart" if sys.platform == "win32" else "--restart",
        "no_restart": "-NoRestart" if sys.platform == "win32" else "--no-restart",
    }
    forwarded = [flag for name, flag in mapping.items() if getattr(args, name, False)]
    ui.info("Updating TrinaxAI...")
    return run_script("update", forwarded, ui)
