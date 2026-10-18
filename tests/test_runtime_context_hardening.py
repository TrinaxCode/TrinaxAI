"""Edge paths of private-storage hardening and request language detection."""

from __future__ import annotations

import os
import stat
from types import SimpleNamespace

import pytest

from app.services import runtime_context

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX permission modes and fchmod")


def test_request_language_defaults_to_english_without_a_request() -> None:
    assert runtime_context.request_language(None) == "en"
    assert runtime_context.request_language(SimpleNamespace(headers={"accept-language": "es-MX,en"})) == "es"


@posix_only
def test_try_fchmod_reports_unsupported_and_failing_platforms(monkeypatch) -> None:
    monkeypatch.delattr(os, "fchmod", raising=False)
    assert runtime_context._try_fchmod(0, 0o700) is False

    def refuse(_fd, _mode):
        raise OSError(1, "not permitted")

    monkeypatch.setattr(os, "fchmod", refuse, raising=False)
    assert runtime_context._try_fchmod(0, 0o700) is False


@posix_only
def test_harden_creates_missing_root_and_restricts_tree_without_following_links(tmp_path) -> None:
    root = tmp_path / "storage"
    runtime_context.harden_persist_directory(str(root))
    assert stat.S_IMODE(root.stat().st_mode) == runtime_context.PRIVATE_DIRECTORY_MODE

    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    outside.chmod(0o644)
    nested = root / "chat" / "deep"
    nested.mkdir(parents=True)
    (nested / "item.bin").write_bytes(b"x")
    (nested / "item.bin").chmod(0o644)
    (root / "link.txt").symlink_to(outside)
    (root / "fifo").touch()
    os.chmod(root / "fifo", 0o644)

    runtime_context.harden_persist_directory(str(root))

    assert stat.S_IMODE((nested / "item.bin").stat().st_mode) == runtime_context.PRIVATE_FILE_MODE
    assert stat.S_IMODE(nested.stat().st_mode) == runtime_context.PRIVATE_DIRECTORY_MODE
    assert stat.S_IMODE(outside.stat().st_mode) == 0o644


@posix_only
def test_harden_rejects_links_files_and_unopenable_roots(tmp_path, monkeypatch) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(RuntimeError, match="real directory"):
        runtime_context.harden_persist_directory(str(link))

    plain = tmp_path / "file"
    plain.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="real directory"):
        runtime_context.harden_persist_directory(str(plain))

    def refuse(*_args, **_kwargs):
        raise OSError(13, "denied")

    monkeypatch.setattr(runtime_context.os, "open", refuse)
    with pytest.raises(RuntimeError, match="Could not secure"):
        runtime_context.harden_persist_directory(str(real))


@posix_only
def test_harden_falls_back_to_directory_mode_without_fchmod(tmp_path, monkeypatch) -> None:
    root = tmp_path / "plain"
    root.mkdir()
    monkeypatch.delattr(os, "fchmod", raising=False)
    runtime_context.harden_persist_directory(str(root))
    assert stat.S_IMODE(root.stat().st_mode) == runtime_context.PRIVATE_DIRECTORY_MODE
