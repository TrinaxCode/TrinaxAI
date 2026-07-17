from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from trinaxai_cli.commands import index, obsidian


class _UI:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)

    def success(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)

    def warn(self, message: str) -> None:
        self.messages.append(message)


class _Client:
    def __init__(self) -> None:
        self.created: list[str] = []

    def create_collection(self, name: str) -> None:
        self.created.append(name)


def test_obsidian_uses_install_root_and_safe_collection_id(monkeypatch, tmp_path: Path) -> None:
    install_root = tmp_path / "TrinaxAI"
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True)
    (vault / "notes" / "welcome.md").write_text("# Welcome", encoding="utf-8")
    monkeypatch.setattr(obsidian, "find_install_root", lambda: install_root)

    client = _Client()
    ui = _UI()
    result = obsidian.run(
        SimpleNamespace(vault=str(vault), collection="../../Team Notes"), client, ui, None
    )

    expected = install_root / "local_sources" / "collections" / "team-notes" / "notes" / "welcome.md"
    assert result == 0
    assert expected.read_text(encoding="utf-8") == "# Welcome"
    assert client.created == ["team-notes"]


def test_index_uses_install_root_when_called_outside_project(monkeypatch, tmp_path: Path) -> None:
    install_root = tmp_path / "TrinaxAI"
    install_root.mkdir()
    index_script = install_root / "index.py"
    index_script.write_text("", encoding="utf-8")
    source = tmp_path / "documents"
    source.mkdir()
    launched: dict[str, object] = {}

    class _Process:
        def wait(self, timeout: float | None = None) -> int:
            launched["timeout"] = timeout
            return 0

    def fake_popen(command, **kwargs):  # type: ignore[no-untyped-def]
        launched["command"] = command
        launched["env"] = kwargs["env"]
        return _Process()

    monkeypatch.setattr(index, "find_install_root", lambda: install_root)
    monkeypatch.setattr(index.subprocess, "Popen", fake_popen)
    monkeypatch.chdir(tmp_path)

    result = index.run(SimpleNamespace(path=str(source), folder=None, collection="default", append=False), None, _UI(), None)

    assert result == 0
    assert launched["command"][1] == str(index_script)  # type: ignore[index]
    assert launched["env"]["TRINAXAI_PROJECT_ROOT"] == str(install_root)  # type: ignore[index]
    assert launched["timeout"] == 3600
