from __future__ import annotations

import sys
from typing import Any

from trinaxai_cli.commands.chat import (
    LocalAttachmentError,
    _resolve_engine,
    _stream_answer,
    new_session_name,
    prepare_local_file,
)
from trinaxai_cli.session import Session


def _collections(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(value)


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    prompt = " ".join(getattr(args, "prompt", [])).strip()
    file_path = getattr(args, "file", None)
    piped = ""
    # A positional prompt wins without touching stdin, so interactive shells
    # and callers that also inherit a pipe never block or consume it.
    if not prompt and not file_path and not sys.stdin.isatty():
        piped = sys.stdin.read(1_048_577)
        if len(piped) > 1_048_576:
            ui.error("stdin prompt exceeds the 1 MiB limit.")
            return 2
        piped = piped.strip()
    prompt = prompt or piped
    if not prompt and not file_path:
        ui.error('Usage: trinaxai ask "your question" or echo "your question" | trinaxai ask')
        return 2
    collections = _collections(getattr(args, "collections", None))
    if file_path and (getattr(args, "engine", None) == "rag" or collections):
        ui.error("file attachments use direct Ollama; omit --engine rag and --collections")
        return 2
    if file_path:
        try:
            attachment = prepare_local_file(file_path, prompt)
        except LocalAttachmentError as exc:
            ui.error(f"file: {exc}")
            return 2
        messages = [attachment["message"]]
        session_prompt = prompt or f"Analyze attached file: {attachment['name']}"
        engine = "ollama"
    else:
        messages = [{"role": "user", "content": prompt}]
        session_prompt = prompt
        engine = _resolve_engine(args, config, collections)
    if engine == "rag" and not collections:
        collections = list(getattr(config, "collections", None) or [])
        if not collections:
            collections = [getattr(config, "active_collection", "default")]
    with Session(getattr(args, "session", None) or new_session_name()) as session:
        session.append("user", session_prompt)
        try:
            thinking = getattr(config, "thinking_enabled", True)
            if getattr(args, "thinking", None) is not None:
                thinking = bool(args.thinking)
            stream_args = (client, ui, messages, engine, collections, getattr(config, "model", None))
            # Keep the historical six-argument integration surface for the
            # default-enabled path; only pass the new override when disabling.
            answer = _stream_answer(*stream_args, False) if not thinking else _stream_answer(*stream_args)
        except Exception as exc:
            ui.failure("Local AI request", exc)
            ui.info("Start TrinaxAI with: trinaxai start")
            return 1
        session.append("assistant", answer)
    return 0
