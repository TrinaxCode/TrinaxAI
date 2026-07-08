from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def service_manager() -> Path:
    return PROJECT_ROOT / "service_manager.py"


def run_service_action(action: str, ui: Any, *, timeout: int = 120) -> int:
    script = service_manager()
    if not script.is_file():
        ui.error("Cannot locate service_manager.py. Run this command from a TrinaxAI checkout.")
        return 1
    try:
        proc = subprocess.run(
            [sys.executable, str(script), action, "--base-dir", str(PROJECT_ROOT)],
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        ui.error(f"Timed out while running service action: {action}")
        return 1
    except OSError as exc:
        ui.error(f"Could not run service manager: {exc}")
        return 1

    output = (proc.stdout or "").strip()
    error = (proc.stderr or "").strip()
    if output:
        ui.print(output)
    if proc.returncode != 0:
        ui.error(error or f"service action failed: {action}")
        return proc.returncode or 1
    if error:
        ui.warn(error)
    return 0


def load_dotenv_values() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def masked(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def service_state() -> dict[str, Any]:
    path = PROJECT_ROOT / "storage" / "service_state.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def env_value(key: str) -> str:
    return os.environ.get(key) or load_dotenv_values().get(key, "")
