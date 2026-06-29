from __future__ import annotations

from typing import Any

from trinaxai_cli.app import VERSION


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    ui.print(f"TrinaxAI CLI {VERSION}")
    return 0
