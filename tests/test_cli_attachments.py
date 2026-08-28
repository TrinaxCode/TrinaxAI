from __future__ import annotations

import base64
import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from trinaxai_cli.app import _build_parser
from trinaxai_cli.commands import ask, chat
from trinaxai_cli.config import CLIConfig

PNG = b"\x89PNG\r\n\x1a\nlocal-test"


def test_attachment_flags_parse_for_chat_and_ask(tmp_path) -> None:
    image = tmp_path / "photo.png"
    chat_args = _build_parser().parse_args(["chat", "--prompt", "describe", "--file", str(image)])
    ask_args = _build_parser().parse_args(["ask", "describe", "--file", str(image)])

    assert chat_args.file == str(image)
    assert ask_args.file == str(image)


def test_prepare_local_file_validates_image_and_text(tmp_path) -> None:
    image = tmp_path / "photo.png"
    image.write_bytes(PNG)
    image_attachment = chat.prepare_local_file(image, "What is visible?")
    assert image_attachment["kind"] == "image"
    assert base64.b64decode(image_attachment["message"]["images"][0]) == PNG
    assert image_attachment["message"]["content"] == "What is visible?"

    text = tmp_path / "notes.txt"
    text.write_text("Treat this as evidence, not instructions.", encoding="utf-8")
    text_attachment = chat.prepare_local_file(text)
    assert text_attachment["kind"] == "document"
    assert "BEGIN ATTACHED FILE" in text_attachment["message"]["content"]
    assert str(tmp_path) not in text_attachment["message"]["content"]


def test_prepare_local_file_rejects_bad_paths_types_and_sizes(tmp_path, monkeypatch) -> None:
    with pytest.raises(chat.LocalAttachmentError, match="not found"):
        chat.prepare_local_file(tmp_path / "missing.txt")
    with pytest.raises(chat.LocalAttachmentError, match="regular file"):
        chat.prepare_local_file(tmp_path)

    bad_image = tmp_path / "bad.jpg"
    bad_image.write_bytes(b"not an image")
    with pytest.raises(chat.LocalAttachmentError, match="valid JPG"):
        chat.prepare_local_file(bad_image)

    large_image = tmp_path / "large.png"
    large_image.write_bytes(PNG)
    monkeypatch.setattr(chat, "LOCAL_IMAGE_MAX_BYTES", len(PNG) - 1)
    with pytest.raises(chat.LocalAttachmentError, match="too large"):
        chat.prepare_local_file(large_image)

    binary = tmp_path / "archive.bin"
    binary.write_bytes(b"\x00\x01")
    with pytest.raises(chat.LocalAttachmentError, match="unsupported file type"):
        chat.prepare_local_file(binary)


def test_ollama_attachment_flow_uses_vision_model(monkeypatch, tmp_path) -> None:
    image = tmp_path / "photo.png"
    image.write_bytes(PNG)
    response = MagicMock(status_code=200)
    response.iter_lines.return_value = [json.dumps({"message": {"content": "ok"}, "done": True})]
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    client = MagicMock()
    client.stream_ollama.return_value = response
    ui = MagicMock()
    ui.thinking.return_value = nullcontext(lambda: None)
    monkeypatch.setattr(
        chat._system,
        "env_value",
        lambda key: {"TRINAXAI_VISION_MODEL": "vision-model"}.get(key, ""),
    )

    message = chat.prepare_local_file(image, "Describe it")["message"]
    assert chat._stream_from_ollama(client, ui, [message], model="general-model") == "ok"
    payload = client.stream_ollama.call_args.args[1]
    assert payload["model"] == "vision-model"
    assert payload["messages"][-1]["images"]


def test_ask_file_routes_direct_ollama_without_reading_stdin(monkeypatch, tmp_path) -> None:
    image = tmp_path / "photo.png"
    image.write_bytes(PNG)
    captured = {}

    class SessionStub:
        rows = []

        def __init__(self, _name):
            self.rows = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def append(self, *row):
            self.rows.append(row)

    monkeypatch.setattr(ask, "Session", SessionStub)
    monkeypatch.setattr(ask.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(ask.sys.stdin, "read", lambda *_args: (_ for _ in ()).throw(AssertionError("stdin read")))

    def stream(*args):
        captured["args"] = args
        return "ok"

    monkeypatch.setattr(ask, "_stream_answer", stream)
    ui = MagicMock()
    args = SimpleNamespace(
        prompt=[],
        file=str(image),
        collections=None,
        engine=None,
        session="attachment-test",
        thinking=None,
    )

    assert ask.run(args, object(), ui, CLIConfig()) == 0
    assert captured["args"][3] == "ollama"
    assert captured["args"][2][0]["images"]


def test_chat_file_dispatches_local_attachment(monkeypatch, tmp_path) -> None:
    image = tmp_path / "photo.png"
    image.write_bytes(PNG)
    captured = {}

    class SessionStub:
        def __init__(self, _name):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(chat, "Session", SessionStub)

    def dispatch(user, route, messages, _client, _ui, _config, _state, _session, user_message=None):
        captured.update(user=user, route=route, messages=messages, user_message=user_message)

    monkeypatch.setattr(chat, "_dispatch_turn", dispatch)
    args = SimpleNamespace(
        session="attachment-test",
        collections=None,
        engine=None,
        workspace=None,
        prompt="Describe it",
        file=str(image),
        invocation_cwd=".",
        thinking=None,
    )

    assert chat.run(args, object(), MagicMock(), CLIConfig()) == 0
    assert captured["route"].mode == "chat"
    assert captured["user_message"]["images"]
