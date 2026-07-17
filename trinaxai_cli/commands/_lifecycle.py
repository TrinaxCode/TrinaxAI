"""Shared launcher for the platform-native update and uninstall scripts."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from trinaxai_cli.processes import run_process_group
from trinaxai_cli.runtime import find_install_root


def command_for(script_stem: str, arguments: list[str], root: Path) -> list[str]:
    if sys.platform == "win32":
        shell = shutil.which("pwsh") or shutil.which("powershell") or shutil.which("powershell.exe")
        if not shell:
            raise FileNotFoundError("PowerShell 5+ is required for this operation")
        script = root / f"{script_stem}.ps1"
        return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *arguments]
    shell = shutil.which("bash")
    if not shell:
        raise FileNotFoundError("bash is required for this operation")
    script = root / f"{script_stem}.sh"
    return [shell, str(script), *arguments]


def run_script(script_stem: str, arguments: list[str], ui: Any) -> int:
    root = find_install_root()
    if root is None:
        ui.error("Cannot locate the TrinaxAI installation. Set TRINAXAI_HOME or run the installer again.")
        return 1
    suffix = ".ps1" if sys.platform == "win32" else ".sh"
    script = root / f"{script_stem}{suffix}"
    if not script.is_file():
        ui.error(f"Installation is incomplete: {script.name} was not found in {root}.")
        return 1
    try:
        command = command_for(script_stem, arguments, root)
        return run_process_group(command, cwd=root, check=False, timeout=3600).returncode
    except KeyboardInterrupt:
        ui.warn(f"Interrupted; stopped {script.name} and its child processes.")
        return 130
    except (OSError, subprocess.SubprocessError) as exc:
        ui.error(f"Could not run {script.name}: {exc}")
        return 1
