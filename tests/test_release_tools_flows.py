from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import auto_update, public_readiness


def test_public_readiness_scans_repository_contracts(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(
        "\n".join(
            [
                ".env",
                ".env.*",
                "*.log",
                "*.pem",
                "*.key",
                "*.crt",
                "*.pfx",
                "certs/",
                "storage/",
                "backups/",
                "local_sources/",
                "logs/",
            ]
        ),
        encoding="utf-8",
    )
    source = tmp_path / "src" / "module.py"
    source.parent.mkdir()
    source.write_text("/home/trinaxcode\nadmin_token = 'real-looking-token'\n", encoding="utf-8")
    ignored = tmp_path / "node_modules" / "ignored.ts"
    ignored.parent.mkdir()
    ignored.write_text("192.168.1.23", encoding="utf-8")
    monkeypatch.setattr(public_readiness, "ROOT", tmp_path)
    monkeypatch.setattr(public_readiness, "REQUIRED_FILES", ["README.md"])

    files = public_readiness.iter_source_files()
    assert source in files and ignored not in files
    assert public_readiness.check_required_files() == ["missing required file: README.md"]
    assert any("local hardcode" in error for error in public_readiness.check_hardcodes(files))
    assert any("token" in error for error in public_readiness.check_secrets(files))
    assert public_readiness.check_local_artifacts()
    assert public_readiness.check_never_commit_files() == []


def test_public_readiness_i18n_tracked_files_and_main(monkeypatch, tmp_path: Path, capsys) -> None:
    translations = tmp_path / "chat-pwa" / "src" / "i18n" / "translations.ts"
    translations.parent.mkdir(parents=True)
    translations.write_text(
        "export const translations = {\n  es: {\n    hello: 'Hola',\n  },\n  en: {\n  },\n};\n",
        encoding="utf-8",
    )
    component = tmp_path / "chat-pwa" / "src" / "App.tsx"
    component.write_text("t('hello')", encoding="utf-8")
    monkeypatch.setattr(public_readiness, "ROOT", tmp_path)
    assert public_readiness.check_i18n() == ["missing i18n key `hello` in en"]

    tracked = [tmp_path / ".env", tmp_path / ".env.example", tmp_path / "certs" / "local.pem"]
    monkeypatch.setattr(public_readiness, "git_tracked_files", lambda: tracked)
    errors = public_readiness.check_tracked_never_commit_files()
    assert len(errors) == 2
    assert public_readiness._matches_never_commit("logs/app.log", "*.log")
    assert public_readiness._matches_never_commit("storage/data.json", "storage/")

    checks = (
        "check_required_files",
        "check_local_artifacts",
        "check_i18n",
        "check_never_commit_files",
        "check_tracked_never_commit_files",
    )
    for name in checks:
        monkeypatch.setattr(public_readiness, name, lambda: [])
    monkeypatch.setattr(public_readiness, "iter_source_files", lambda: [])
    monkeypatch.setattr(public_readiness, "check_hardcodes", lambda _files: [])
    monkeypatch.setattr(public_readiness, "check_secrets", lambda _files: [])
    assert public_readiness.main() == 0
    assert "passed" in capsys.readouterr().out
    monkeypatch.setattr(public_readiness, "check_required_files", lambda: ["missing"])
    assert public_readiness.main() == 1
    assert "missing" in capsys.readouterr().out


def test_public_readiness_git_failure_and_missing_ignore_are_safe(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(public_readiness, "ROOT", tmp_path)
    monkeypatch.setattr(public_readiness.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    assert public_readiness.git_tracked_files() == []
    assert public_readiness.check_local_artifacts()
    assert public_readiness.check_never_commit_files()


def test_auto_update_linux_cron_and_windows_scheduler(monkeypatch, tmp_path: Path) -> None:
    completed = SimpleNamespace(returncode=0, stdout="old cron\n", stderr="")
    calls = []
    monkeypatch.setattr(auto_update, "_run", lambda command, **kwargs: calls.append((command, kwargs)) or completed)
    monkeypatch.setattr(auto_update.platform, "system", lambda: "Linux")
    monkeypatch.setattr(auto_update.shutil, "which", lambda name: "/usr/bin/crontab" if name == "crontab" else None)

    assert auto_update.enable(tmp_path) == "weekly cron update enabled"
    wrapper = tmp_path / "storage" / "maintenance" / "weekly-update.sh"
    assert wrapper.stat().st_mode & 0o077 == 0
    assert any(call[0] == ["crontab", "-"] for call in calls)

    calls.clear()
    monkeypatch.setattr(auto_update.platform, "system", lambda: "Windows")
    assert "Windows task" in auto_update.enable(tmp_path)
    assert (tmp_path / "storage" / "maintenance" / "weekly-update.cmd").exists()
    assert calls[-1][0][0] == "schtasks"


@pytest.mark.parametrize("system", ["Linux", "Darwin", "Windows"])
def test_auto_update_disable_removes_platform_state(monkeypatch, tmp_path: Path, system: str) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(auto_update.Path, "home", lambda: home)
    monkeypatch.setattr(auto_update.platform, "system", lambda: system)
    monkeypatch.setattr(auto_update.shutil, "which", lambda _name: "/bin/tool")
    monkeypatch.setattr(
        auto_update,
        "_run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    maintenance = tmp_path / "storage" / "maintenance"
    maintenance.mkdir(parents=True)
    for name in ("weekly-update.sh", "weekly-update.cmd", "weekly-update.vbs"):
        (maintenance / name).write_text("", encoding="utf-8")
    plist = home / "Library" / "LaunchAgents" / f"{auto_update.MAC_LABEL}.plist"
    plist.parent.mkdir(parents=True)
    plist.write_text("", encoding="utf-8")

    assert auto_update.disable(tmp_path) == "weekly automatic updates disabled"


def test_scheduled_update_checks_versions_without_executing_remote_code(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(auto_update.shutil, "which", lambda _name: "/usr/bin/git")
    logged = []
    monkeypatch.setattr(auto_update, "_log", lambda _base, message: logged.append(message))
    responses = iter(
        [
            SimpleNamespace(returncode=0, stdout="a" * 40 + "\n", stderr=""),
            SimpleNamespace(returncode=0, stdout="b" * 40 + "\trefs/heads/main\n", stderr=""),
        ]
    )
    monkeypatch.setattr(auto_update, "_run", lambda *_args, **_kwargs: next(responses))

    assert auto_update.run_update(tmp_path) == 0
    assert "Update available" in logged[-1]
    assert not (tmp_path / "storage" / "maintenance" / "update.lock").exists()

    lock = tmp_path / "storage" / "maintenance" / "update.lock"
    lock.write_text("", encoding="utf-8")
    os.utime(lock, (time.time(), time.time()))
    assert auto_update.run_update(tmp_path) == 0
    assert "already running" in logged[-1]


def test_scheduled_update_no_git_and_lookup_failure_are_logged(monkeypatch, tmp_path: Path) -> None:
    logged = []
    monkeypatch.setattr(auto_update, "_log", lambda _base, message: logged.append(message))
    monkeypatch.setattr(auto_update.shutil, "which", lambda _name: None)
    assert auto_update.run_update(tmp_path) == 0
    assert "no Git metadata" in logged[-1]

    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(auto_update.shutil, "which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr(
        auto_update,
        "_run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="network offline"),
    )
    assert auto_update.run_update(tmp_path) == 1
    assert "failed safely" in logged[-1]


def test_auto_update_main_routes_actions(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["auto_update.py", "disable", "--base-dir", str(tmp_path)])
    monkeypatch.setattr(auto_update, "disable", lambda path: f"disabled {path}")
    assert auto_update.main() == 0
    assert "disabled" in capsys.readouterr().out
