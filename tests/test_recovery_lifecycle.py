from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import recovery_server
import service_manager as sm


def test_recovery_accepts_only_loopback_addresses() -> None:
    assert recovery_server._is_loopback("127.0.0.1")
    assert recovery_server._is_loopback("::1")
    assert not recovery_server._is_loopback("192.168.1.10")
    assert not recovery_server._is_loopback("0.0.0.0")


def test_stop_all_persists_manual_stop_and_starts_recovery(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "storage").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(sm, "_try_privileged_wrapper", lambda *_args: None)
    monkeypatch.setattr(sm, "_set_ai_systemd_enabled", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(sm, "_wait_port_free", lambda: True)
    monkeypatch.setattr(sm, "_start_recovery", lambda _base: sm.ProcessState("recovery", True, pid=9))
    monkeypatch.setattr(sm, "_backend", SimpleNamespace(stop=lambda name: sm.ProcessState(name, False)))

    result = sm.stop_all_for_base(str(tmp_path))
    state = json.loads((tmp_path / "storage" / "service_state.json").read_text(encoding="utf-8"))

    assert result[-1].name == "recovery"
    assert state["ai_enabled"] is False
    assert state["system_state"] == "stopped_by_user"


def test_external_ollama_is_not_marked_as_owned(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sm, "_backend", SimpleNamespace(status=lambda _name: sm.ProcessState("ollama", True, pid=42)))
    state = sm._start_named(str(tmp_path), "ollama")
    persisted = json.loads((tmp_path / "storage" / "service_state.json").read_text(encoding="utf-8"))

    assert state.running
    assert persisted["ollama_owned"] is False
