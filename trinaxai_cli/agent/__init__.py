"""Backward-compatible import surface for the shared agent core."""

from __future__ import annotations

from trinaxai_agent import (
    DEFAULT_TOOLS,
    MAX_OUTPUT_CHARS,
    AgentEngine,
    SandboxError,
    Tool,
    build_tool_map,
    default_system_prompt,
    format_tool_failure,
    is_degraded_tool_result,
    normalize_tool_result,
)

from . import engine as engine
from . import extract as extract
from . import tools as tools

__all__ = [
    "AgentEngine",
    "default_system_prompt",
    "DEFAULT_TOOLS",
    "MAX_OUTPUT_CHARS",
    "SandboxError",
    "Tool",
    "build_tool_map",
    "format_tool_failure",
    "is_degraded_tool_result",
    "normalize_tool_result",
]
