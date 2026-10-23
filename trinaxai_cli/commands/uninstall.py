from __future__ import annotations

import sys
from typing import Any

from trinaxai_cli.commands._lifecycle import run_script


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    windows = sys.platform == "win32"
    mapping = {
        "yes": "-Yes" if windows else "--yes",
        "purge": "-Purge" if windows else "--purge",
        "remove_data": "-RemoveData" if windows else "--remove-data",
        "remove_models": "-RemoveModels" if windows else "--remove-models",
        "remove_ollama": "-RemoveOllama" if windows else "--remove-ollama",
        "keep_env": "-KeepEnv" if windows else "--keep-env",
        "remove_env": "-RemoveEnv" if windows else "--remove-env",
        "remove_certs": "-RemoveCerts" if windows else "--remove-certs",
        "remove_app": "-RemoveApp" if windows else "--remove-app",
        "dry_run": "-DryRun" if windows else "--dry-run",
    }
    forwarded = [flag for name, flag in mapping.items() if getattr(args, name, False)]
    return run_script("uninstall", forwarded, ui)
