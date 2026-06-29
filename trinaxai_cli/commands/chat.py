"""``trinaxai chat`` — interactive REPL or single-shot prompt.

Without arguments starts a REPL. With ``--prompt`` runs a single request.
The ``Session`` class in :mod:`trinaxai_cli.session` persists every exchange
to ``~/.local/share/trinaxai/sessions/<name>.jsonl``.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from trinaxai_cli.commands import _system
from trinaxai_cli.session import Session


def _send_to_rag(
    client: Any,
    messages: list[dict[str, str]],
    collections: list[str] | None = None,
    model: str | None = None,
) -> str:
    """POST to /v1/chat/completions (non-streaming) and return the assistant text."""
    payload = {
        "model": model,
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


def _stream_from_rag(
    client: Any,
    ui: Any,
    messages: list[dict[str, str]],
    collections: list[str] | None = None,
    model: str | None = None,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "collections": collections or [],
    }
    full = ""
    with client._client.stream("POST", "/v1/chat/completions", json=payload, timeout=120.0) as response:  # noqa: SLF001
        if response.status_code >= 400:
            detail = response.read().decode("utf-8", errors="replace")[:200]
            raise RuntimeError(f"chat: HTTP {response.status_code} — {detail}")
        for line in response.iter_lines():
            text = line.strip()
            if not text or not text.startswith("data: "):
                continue
            data = text[6:]
            if data == "[DONE]":
                break
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                continue
            error = parsed.get("trinaxai_error")
            if error:
                raise RuntimeError(str(error))
            token = (((parsed.get("choices") or [{}])[0].get("delta") or {}).get("content") or "")
            if token:
                full += token
                ui.print(token, end="")
    ui.print("")
    return full or "(no answer)"


def _slash_help(ui: Any) -> None:
    ui.print(
        "\n".join(
            [
                "Slash commands:",
                "  /help              Show this help",
                "  /exit              Exit chat",
                "  /clear             Clear in-memory conversation",
                "  /model [name]      Show or set requested model hint",
                "  /index [path]      Index a folder, default: current directory",
                "  /status            Show local service status",
            ]
        )
    )


def _handle_slash(command: str, messages: list[dict[str, str]], ui: Any, config: Any) -> tuple[bool, str | None, int | None]:
    parts = command.strip().split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    if name in {"/exit", "/quit"}:
        return True, None, 0
    if name == "/help":
        _slash_help(ui)
        return True, None, None
    if name == "/clear":
        messages.clear()
        ui.success("Conversation cleared.")
        return True, None, None
    if name == "/status":
        _system.run_service_action("status", ui, timeout=30)
        return True, None, None
    if name == "/index":
        from trinaxai_cli.commands import index as index_cmd

        idx_args = SimpleNamespace(path=arg or ".", folder=None, collection="default", append=False)
        index_cmd.run(idx_args, None, ui, config)
        return True, None, None
    if name == "/model":
        return True, arg or "", None
    return False, None, None


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    session_name = getattr(args, "session", None) or "default"
    collections = getattr(args, "collections", None) or []
    if isinstance(collections, str):
        collections = [c.strip() for c in collections.split(",") if c.strip()]

    with Session(session_name) as session:
        messages: list[dict[str, str]] = []
        requested_model: str | None = None

        prompt = getattr(args, "prompt", None)
        if prompt:
            messages.append({"role": "user", "content": prompt})
            session.append("user", prompt)
            try:
                answer = _send_to_rag(client, messages, collections, requested_model)
            except Exception as exc:
                ui.error(f"chat: {exc}")
                return 1
            session.append("assistant", answer)
            ui.markdown(answer)
            return 0

        ui.print("TrinaxAI")
        ui.info(f"Local chat session: {session_name}. Type /help for commands, /exit or Ctrl-D to quit.")
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
            if user.strip().startswith("/"):
                handled, model_hint, exit_code = _handle_slash(user, messages, ui, config)
                if exit_code is not None:
                    ui.info("bye.")
                    return exit_code
                if model_hint is not None:
                    if model_hint:
                        requested_model = model_hint
                        ui.success(f"Requested model hint set to: {requested_model}")
                    else:
                        ui.info(f"Requested model hint: {requested_model or 'auto'}")
                if handled:
                    continue
            messages.append({"role": "user", "content": user})
            session.append("user", user)
            try:
                answer = _stream_from_rag(client, ui, messages, collections, requested_model)
            except Exception as exc:
                ui.error(f"Cannot reach the local RAG API: {exc}")
                ui.info("Start TrinaxAI with: trinaxai start")
                continue
            session.append("assistant", answer)
            messages.append({"role": "assistant", "content": answer})
            ui.markdown(answer)
            ui.print("")
    return 0
