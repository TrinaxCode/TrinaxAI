import io
import shlex
import tarfile
import threading
import time
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

import trinaxai_manager


def test_download_source_installs_managed_archive(tmp_path: Path, monkeypatch):
    source = tmp_path / "TrinaxAI-main"
    source.mkdir()
    (source / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (source / "install.sh").write_text("#!/bin/sh", encoding="utf-8")
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(source / "pyproject.toml", "TrinaxAI-main/pyproject.toml")
        bundle.write(source / "install.sh", "TrinaxAI-main/install.sh")
    monkeypatch.setattr(trinaxai_manager, "ARCHIVE_URL", archive.as_uri())

    target = tmp_path / "installed"
    trinaxai_manager.download_source(target)

    assert (target / "install.sh").is_file()
    assert (target / ".trinaxai-managed").is_file()


def test_download_source_rejects_archive_without_project_manifest(tmp_path: Path, monkeypatch):
    source = tmp_path / "TrinaxAI-main"
    source.mkdir()
    (source / "install.sh").write_text("#!/bin/sh", encoding="utf-8")
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(source / "install.sh", "TrinaxAI-main/install.sh")
    monkeypatch.setattr(trinaxai_manager, "ARCHIVE_URL", archive.as_uri())

    with pytest.raises(RuntimeError, match="package is invalid"):
        trinaxai_manager.download_source(tmp_path / "installed")


def test_manager_runs_downloaded_installer_without_old_bootstrap_commands(tmp_path: Path, monkeypatch):
    popen = Mock()
    monkeypatch.setattr(trinaxai_manager.platform, "system", lambda: "Windows")
    monkeypatch.setattr(trinaxai_manager.subprocess, "Popen", popen)

    trinaxai_manager.launch_terminal(tmp_path, "install", "es")

    args = popen.call_args.args[0]
    assert args[4:] == ["-File", str(tmp_path / "install.ps1"), "-NonInteractive", "-Language", "es"]
    assert "curl" not in " ".join(args).lower()
    assert "irm" not in " ".join(args).lower()
    assert "git" not in " ".join(args).lower()


def test_download_source_uses_timeout_and_reports_corrupt_zip(tmp_path: Path, monkeypatch):
    calls = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def fake_urlopen(url, timeout):
        calls.update(url=url, timeout=timeout)
        return Response(b"not a zip")

    monkeypatch.setattr(trinaxai_manager.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="valid ZIP"):
        trinaxai_manager.download_source(tmp_path / "installed")

    assert calls["url"] == trinaxai_manager.ARCHIVE_URL
    assert calls["timeout"] == trinaxai_manager.DOWNLOAD_TIMEOUT


def test_download_source_rejects_zip_traversal_before_extracting(tmp_path: Path, monkeypatch):
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("TrinaxAI-main/install.sh", "#!/bin/sh")
        bundle.writestr("../outside.txt", "must not be written")
    monkeypatch.setattr(trinaxai_manager, "ARCHIVE_URL", archive.as_uri())

    with pytest.raises(RuntimeError, match="unsafe path"):
        trinaxai_manager.download_source(tmp_path / "installed")

    assert not (tmp_path / "outside.txt").exists()


def test_download_source_rejects_oversized_zip_member_before_extracting(tmp_path: Path, monkeypatch):
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("TrinaxAI-main/pyproject.toml", "[project]\n")
        bundle.writestr("TrinaxAI-main/large.bin", "x" * 16)
    monkeypatch.setattr(trinaxai_manager, "ARCHIVE_URL", archive.as_uri())
    monkeypatch.setattr(trinaxai_manager, "MAX_MEMBER_BYTES", 8)

    with pytest.raises(RuntimeError, match="package is too large"):
        trinaxai_manager.download_source(tmp_path / "installed")

    assert not (tmp_path / "installed").exists()


def test_download_source_rejects_oversized_tar_member_before_extracting(tmp_path: Path, monkeypatch):
    archive = tmp_path / "release.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for name, data in (
            ("TrinaxAI-main/pyproject.toml", b"[project]\n"),
            ("TrinaxAI-main/large.bin", b"x" * 16),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            bundle.addfile(info, io.BytesIO(data))
    monkeypatch.setattr(trinaxai_manager, "ARCHIVE_URL", archive.as_uri())
    monkeypatch.setattr(trinaxai_manager, "MAX_MEMBER_BYTES", 8)

    with pytest.raises(RuntimeError, match="package is too large"):
        trinaxai_manager.download_source(tmp_path / "installed")

    assert not (tmp_path / "installed").exists()


def test_launch_terminal_quotes_posix_paths_and_rejects_unknown_actions(tmp_path: Path, monkeypatch):
    root = tmp_path / "source;$(touch escaped)"
    root.mkdir()
    popen = Mock(return_value=None)
    monkeypatch.setattr(trinaxai_manager.platform, "system", lambda: "Linux")
    monkeypatch.setattr(trinaxai_manager.shutil, "which", lambda name: name == "xterm")
    monkeypatch.setattr(trinaxai_manager.subprocess, "Popen", popen)

    trinaxai_manager.launch_terminal(root, "install", "es")

    command = popen.call_args.args[0][-1]
    assert shlex.quote(str(root / "install.sh")) in command
    assert "TRINAXAI_LANG=es" in command
    assert popen.call_args.kwargs["cwd"] == root.resolve()
    with pytest.raises(ValueError, match="Unsupported lifecycle action"):
        trinaxai_manager.launch_terminal(root, "not-an-action", "es")


class _FakeVar:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class _FakeButton:
    def __init__(self):
        self.state = None

    def config(self, **kwargs):
        self.state = kwargs["state"]


class _FakeWindow:
    def after(self, _delay, callback):
        callback()


def _manager_without_tk(root: Path):
    manager = object.__new__(trinaxai_manager.Manager)
    manager.lang = "en"
    manager.text = trinaxai_manager.TEXT["en"]
    manager.root = root
    manager.window = _FakeWindow()
    manager.status = _FakeVar()
    manager.install_button = _FakeButton()
    manager.update_button = _FakeButton()
    manager.uninstall_button = _FakeButton()
    manager._action_lock = threading.Lock()
    manager._busy = False
    return manager


def test_manager_refresh_and_action_lock_work_without_display(tmp_path: Path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    manager = _manager_without_tk(tmp_path)
    manager.refresh()
    assert manager.status.value == manager.text["ready"]
    assert manager.install_button.state == trinaxai_manager.DISABLED
    assert manager.update_button.state == trinaxai_manager.NORMAL
    assert manager.uninstall_button.state == trinaxai_manager.NORMAL

    started = threading.Event()
    release = threading.Event()
    calls = []

    def fake_launch(root, action, lang):
        calls.append((root, action, lang))
        started.set()
        release.wait(2)
        return None

    monkeypatch.setattr(trinaxai_manager, "launch_terminal", fake_launch)
    assert manager.run("update") is True
    assert started.wait(1)
    assert manager.run("uninstall") is False
    assert manager.install_button.state == trinaxai_manager.DISABLED
    release.set()

    deadline = time.monotonic() + 2
    while manager._busy and time.monotonic() < deadline:
        time.sleep(0.01)
    assert manager._busy is False
    assert calls == [(tmp_path, "update", "en")]


def test_manager_finishes_after_lifecycle_process_exits(tmp_path: Path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    manager = _manager_without_tk(tmp_path)
    process = Mock()
    process.wait.return_value = 0
    monkeypatch.setattr(trinaxai_manager, "launch_terminal", Mock(return_value=process))

    assert manager.run("update") is True
    deadline = time.monotonic() + 2
    while manager._busy and time.monotonic() < deadline:
        time.sleep(0.01)

    process.wait.assert_called_once_with()
    assert manager._busy is False
    assert manager.update_button.state == trinaxai_manager.NORMAL


def test_user_documentation_leads_with_manager_and_in_app_docs_drop_git_clone():
    root = Path(__file__).parents[1]
    for name, terminal_marker in (("README.md", 'installer="$(mktemp)"'), ("README.es.md", 'installer="$(mktemp)"')):
        text = (root / name).read_text(encoding="utf-8")
        assert text.index("TrinaxAI Manager" if name == "README.md" else "Gestor de TrinaxAI") < text.index(
            terminal_marker
        )
        assert "no terminal commands" in text.lower() or "no necesitas git ni comandos" in text.lower()
    in_app_docs = (root / "chat-pwa/src/components/Docs.tsx").read_text(encoding="utf-8")
    assert "git clone" not in in_app_docs.lower()
