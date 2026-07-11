from __future__ import annotations

from pathlib import Path

from trinaxai_cli import runtime
from trinaxai_cli.commands import _lifecycle


def make_install(path: Path) -> Path:
    (path / "trinaxai_cli").mkdir(parents=True)
    (path / "service_manager.py").write_text("", encoding="utf-8")
    return path


def test_explicit_install_root_wins(monkeypatch, tmp_path: Path) -> None:
    install = make_install(tmp_path / "custom install")
    monkeypatch.setenv("TRINAXAI_HOME", str(install))
    assert runtime.find_install_root() == install.resolve()


def test_posix_lifecycle_command_preserves_paths_with_spaces(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "Application Support" / "TrinaxAI"
    root.mkdir(parents=True)
    monkeypatch.setattr(_lifecycle.sys, "platform", "darwin")
    monkeypatch.setattr(_lifecycle.shutil, "which", lambda name: "/bin/bash" if name == "bash" else None)
    command = _lifecycle.command_for("update", ["--no-backup"], root)
    assert command == ["/bin/bash", str(root / "update.sh"), "--no-backup"]


def test_windows_lifecycle_uses_powershell(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(_lifecycle.sys, "platform", "win32")
    monkeypatch.setattr(_lifecycle.shutil, "which", lambda name: "C:/PowerShell/pwsh.exe" if name == "pwsh" else None)
    command = _lifecycle.command_for("uninstall", ["-Yes"], tmp_path)
    assert command[-2:] == [str(tmp_path / "uninstall.ps1"), "-Yes"]
    assert command[:2] == ["C:/PowerShell/pwsh.exe", "-NoProfile"]
