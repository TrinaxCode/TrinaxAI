from __future__ import annotations

import os
from typing import Any

from trinaxai_cli.commands import _system
from trinaxai_cli.config import CLIConfig

SECRET_KEYS = {"TRINAXAI_ADMIN_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"}


def _safe_env(key: str) -> str:
    value = os.environ.get(key) or _system.load_dotenv_values().get(key, "")
    if key in SECRET_KEYS:
        return _system.masked(value)
    return value


def run(args: Any, client: Any, ui: Any, config: CLIConfig) -> int:
    rows = [
        ["api.base_url", config.api_base_url],
        ["api.verify_tls", str(config.api_verify_tls)],
        ["defaults.engine", config.engine],
        ["defaults.model", config.model],
        ["defaults.collections", ", ".join(config.collections)],
        ["ui.color", config.ui_color],
        ["install_root", str(_system.project_root() or "(not found)")],
    ]
    for key in [
        "TRINAXAI_PROFILE",
        "TRINAXAI_PORT",
        "OLLAMA_BASE_URL",
        "TRINAXAI_ALLOW_LAN_SYSTEM",
        "TRINAXAI_ADMIN_TOKEN",
    ]:
        rows.append([key, _safe_env(key) or "(unset)"])
    ui.table(["setting", "value"], rows, title="TrinaxAI config")
    return 0
