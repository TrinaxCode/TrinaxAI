"""The agent loads its model and prompt prefix while the user is still typing."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from trinaxai_agent import AgentEngine
from trinaxai_cli.commands import agent_repl


class _Recorder(AgentEngine):
    """Engine that records the payload it would send to Ollama."""

    def __init__(self, root: Path, reply: dict | Exception) -> None:
        super().__init__(model="warm-model", workspace_root=root)
        self._reply = reply
        self.sent: list[tuple[str, dict]] = []

    def _post(self, url, payload):  # type: ignore[override]
        self.sent.append((url, payload))
        if isinstance(self._reply, Exception):
            raise self._reply
        return self._reply


def test_warm_up_sends_the_same_prefix_as_a_real_turn(tmp_path: Path) -> None:
    engine = _Recorder(tmp_path, {"message": {"content": "p"}})
    assert engine.warm_up() is True

    (url, payload) = engine.sent[0]
    assert url == "http://localhost:11434/api/chat"
    # Same model, context window, system prompt and tool schemas as `_chat`, so Ollama reuses
    # the loaded model and the cached prefix; only the reply is cut to one token.
    assert payload["model"] == engine.model
    assert payload["messages"][0] == {"role": "system", "content": engine.system_prompt}
    assert payload["tools"] == [tool.schema() for tool in engine.tools]
    assert payload["options"]["num_ctx"] == engine.num_ctx
    assert payload["options"]["num_predict"] == 1
    assert payload["stream"] is False and payload["think"] is False
    assert payload["keep_alive"] == engine.keep_alive


def test_warm_up_failures_are_silent(tmp_path: Path) -> None:
    assert _Recorder(tmp_path, RuntimeError("cannot reach Ollama")).warm_up() is False
    assert _Recorder(tmp_path, {"error": "model not found"}).warm_up() is False


def test_repl_starts_warm_up_in_the_background_and_tolerates_engines_without_it() -> None:
    started = threading.Event()
    threads: list[str] = []

    def warm() -> bool:
        threads.append(threading.current_thread().name)
        started.set()
        return True

    agent_repl._warm_up_in_background(SimpleNamespace(warm_up=warm))
    assert started.wait(5)
    assert threads == ["agent-warm-up"]

    agent_repl._warm_up_in_background(SimpleNamespace())  # integrations with their own engine
    agent_repl._warm_up_in_background(MagicMock(warm_up=None))
