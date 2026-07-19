from __future__ import annotations

import os
from typing import Any

RECOMMENDED = ["granite4:3b", "qwen3.5:2b", "qwen3.5:0.8b", "qwen2.5-coder:1.5b", "bge-m3"]
ON_DEMAND = ["qwen3-vl:4b-instruct"]


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
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
