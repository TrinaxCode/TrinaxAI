from __future__ import annotations

from typing import Any

from trinaxai_cli.commands.chat import _send_to_rag
from trinaxai_cli.session import Session


def _collections(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(value)


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    prompt = " ".join(getattr(args, "prompt", [])).strip()
    if not prompt:
        ui.error("Usage: trinaxai ask \"your question\"")
        return 2
    messages = [{"role": "user", "content": prompt}]
    with Session(getattr(args, "session", None) or "default") as session:
        session.append("user", prompt)
        try:
            answer = _send_to_rag(client, messages, _collections(getattr(args, "collections", None)))
        except Exception as exc:
            ui.error(f"Cannot reach the local RAG API: {exc}")
            ui.info("Start TrinaxAI with: trinaxai start")
            return 1
        session.append("assistant", answer)
    ui.markdown(answer)
    return 0
