from __future__ import annotations

import sys
from typing import Any

from trinaxai_cli.commands.chat import _resolve_engine, _stream_answer, new_session_name
from trinaxai_cli.session import Session


def _collections(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(value)


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    prompt = " ".join(getattr(args, "prompt", [])).strip()
    piped = ""
    # A positional prompt wins without touching stdin, so interactive shells
    # and callers that also inherit a pipe never block or consume it.
    if not prompt and not sys.stdin.isatty():
        piped = sys.stdin.read(1_048_577)
        if len(piped) > 1_048_576:
            ui.error("stdin prompt exceeds the 1 MiB limit.")
            return 2
        piped = piped.strip()
    prompt = prompt or piped
    if not prompt:
        ui.error('Usage: trinaxai ask "your question" or echo "your question" | trinaxai ask')
        return 2
    messages = [{"role": "user", "content": prompt}]
    collections = _collections(getattr(args, "collections", None))
    engine = _resolve_engine(args, config, collections)
    if engine == "rag" and not collections:
        collections = list(getattr(config, "collections", None) or [])
        if not collections:
            collections = [getattr(config, "active_collection", "default")]
    with Session(getattr(args, "session", None) or new_session_name()) as session:
        session.append("user", prompt)
        try:
            answer = _stream_answer(client, ui, messages, engine, collections, getattr(config, "model", None))
        except Exception as exc:
            ui.error(f"Cannot reach the local AI service: {exc}")
            ui.info("Start TrinaxAI with: trinaxai start")
            return 1
        session.append("assistant", answer)
    return 0
