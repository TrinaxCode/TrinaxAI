from __future__ import annotations

from typing import Any

from trinaxai_cli.commands import _system


def _format_size(value: Any) -> str:
    """Ollama reports sizes in bytes; show them the way people read them."""
    try:
        size = float(value)
    except (TypeError, ValueError):
        return str(value or "")
    if size <= 0:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


RECOMMENDED = ["qwen3.5:2b", "qwen3.5:4b", "qwen3-embedding:0.6b"]
ON_DEMAND: list[str] = []


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    base = _system.env_value("OLLAMA_BASE_URL") or "http://localhost:11434"
    rows: list[list[str]] = []
    installed: set[str] = set()
    try:
        for model in client.list_ollama_models(base):
            name = str(model.get("name", ""))
            if name:
                installed.add(name)
                rows.append([name, "installed", _format_size(model.get("size"))])
    except Exception as exc:
        ui.failure("Model listing", exc)
        ui.info("Start TrinaxAI with: trinaxai start")

    for name in RECOMMENDED:
        if name not in installed:
            rows.append([name, "recommended", f"ollama pull {name}"])
    for name in ON_DEMAND:
        if name not in installed:
            rows.append([name, "on-demand", "downloaded on first image analysis"])
    ui.table(["model", "status", "detail"], rows, title="TrinaxAI models")
    return 0
