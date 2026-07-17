"""Mutable state for the unified ``trinaxai chat`` REPL.

Keeping the state object separate prevents the slash-command registry and the
turn controller from importing each other.  ``chat.py`` re-exports
``ChatState`` for backwards compatibility with existing integrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatState:
    engine: str = "ollama"
    collections: list[str] = field(default_factory=list)
    model: str | None = None
    # ``forced_mode`` pins a mode; the remaining flags bias automatic routing.
    forced_mode: str | None = None
    web_mode: bool = False
    research_mode: bool = False
    yolo: bool = False
    workspace: str = "."
    lang: str = "es"
    agent_engine: Any = None
    agent_messages: list[dict[str, Any]] = field(default_factory=list)
    # Inline slash prompts (for example ``/web query``) are consumed by the
    # controller on the same REPL turn.
    pending_input: str | None = None
