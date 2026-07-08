from __future__ import annotations

import os
from typing import Any

RECOMMENDED = ["llama3.2:3b", "qwen2.5-coder:3b", "bge-m3", "qwen2.5vl:3b"]


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    rows: list[list[str]] = []
    installed: set[str] = set()
    try:
        response = client._client.get(f"{base}/api/tags", timeout=5.0)  # noqa: SLF001
        response.raise_for_status()
        for model in response.json().get("models", []):
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
    ui.table(["model", "status", "detail"], rows, title="TrinaxAI models")
    return 0
