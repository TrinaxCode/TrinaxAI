"""``trinaxai chat`` — interactive REPL or single-shot prompt.

Without arguments starts a REPL. With ``--prompt`` runs a single request.
The ``Session`` class in :mod:`trinaxai_cli.session` persists every exchange
to ``~/.local/share/trinaxai/sessions/<name>.jsonl``.
"""
from __future__ import annotations

import sys
from typing import Any

from trinaxai_cli.session import Session


def _send_to_rag(client: Any, messages: list[dict[str, str]], collections: list[str] | None = None) -> str:
    """POST to /v1/chat/completions (non-streaming) and return the assistant text."""
    payload = {
        "model": None,
        "messages": messages,
        "stream": False,
        "collections": collections or [],
    }
    # Use the raw httpx client for /v1/chat/completions since the helper client
    # doesn't expose chat specifically.
    r = client._client.post("/v1/chat/completions", json=payload, timeout=120.0)  # noqa: SLF001
    # Treat non-2xx as errors here so the caller can surface them.
    if r.status_code >= 400:
        raise RuntimeError(f"chat: HTTP {r.status_code} — {r.text[:200]}")
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return "(no answer)"


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    session_name = getattr(args, "session", None) or "default"
    collections = getattr(args, "collections", None) or []
    if isinstance(collections, str):
        collections = [c.strip() for c in collections.split(",") if c.strip()]

    with Session(session_name) as session:
        messages: list[dict[str, str]] = []

        prompt = getattr(args, "prompt", None)
        if prompt:
            messages.append({"role": "user", "content": prompt})
            session.append("user", prompt)
            try:
                answer = _send_to_rag(client, messages, collections)
            except Exception as exc:
                ui.error(f"chat: {exc}")
                return 1
            session.append("assistant", answer)
            ui.markdown(answer)
            return 0

        ui.info(f"TrinaxAI REPL (session: {session_name}). Type 'exit' or Ctrl-D to quit.")
        while True:
            try:
                user = ui.prompt("you")
            except (EOFError, KeyboardInterrupt):
                ui.info("\nbye.")
                return 0
            if not user:
                continue
            if user.strip().lower() in {"exit", "quit", "/exit", "/quit"}:
                ui.info("bye.")
                return 0
            messages.append({"role": "user", "content": user})
            session.append("user", user)
            try:
                with ui.spinner("thinking..."):
                    answer = _send_to_rag(client, messages, collections)
            except Exception as exc:
                ui.error(str(exc))
                continue
            session.append("assistant", answer)
            messages.append({"role": "assistant", "content": answer})
            ui.markdown(answer)
            ui.print("")
    return 0