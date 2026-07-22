from __future__ import annotations

from typing import Any

from trinaxai_cli.commands import _system

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
                rows.append([name, "installed", str(model.get("size", ""))])
    except Exception as exc:
        ui.warn(f"Ollama is not reachable at {base}: {exc}")
        ui.info("Start TrinaxAI with: trinaxai start")

    for name in RECOMMENDED:
        if name not in installed:
            rows.append([name, "recommended", f"ollama pull {name}"])
    for name in ON_DEMAND:
        if name not in installed:
            rows.append([name, "on-demand", "downloaded on first image analysis"])
    ui.table(["model", "status", "detail"], rows, title="TrinaxAI models")
    return 0
