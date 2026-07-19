"""Reserved command for a future MCP integration."""

from __future__ import annotations

from typing import Any


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    ui.info("MCP server integration is planned and is not configured in this release.")
    ui.info("Use the TrinaxAI HTTP API or CLI commands directly for now.")
    return 2
