from __future__ import annotations

import sys

import pytest

import trinaxai_core
from trinaxai_core import (
    VALID_PROFILES,
    normalize_http_base_url,
    sanitize_collection_id,
    source_id_for_root,
)


def test_valid_profiles_are_one_immutable_source_of_truth() -> None:
    import config

    assert isinstance(VALID_PROFILES, frozenset)
    assert config.VALID_PROFILES is VALID_PROFILES
    assert "16gb" in VALID_PROFILES


def test_sanitize_collection_id_rejects_path_traversal_shapes() -> None:
    assert sanitize_collection_id("../../etc/passwd") == "etc-passwd"
    assert sanitize_collection_id("My Project / Docs!") == "my-project-docs"
    assert sanitize_collection_id("") == "collection"


def test_http_base_url_validation_rejects_unsafe_and_malformed_schemes() -> None:
    assert normalize_http_base_url("https://ollama.example:11434/") == "https://ollama.example:11434"
    assert normalize_http_base_url("file:///tmp/socket", "http://localhost:11434") == "http://localhost:11434"
    assert normalize_http_base_url("http://localhost:bad", "fallback") == "fallback"
    assert normalize_http_base_url("http://localhost:11434/api", "fallback") == "fallback"
    assert normalize_http_base_url("http://user:secret@localhost:11434", "fallback") == "fallback"
    assert normalize_http_base_url("http://bad host:11434", "fallback") == "fallback"


def test_source_id_is_stable_and_explicit_ids_are_sanitized(tmp_path) -> None:
    generated = source_id_for_root(str(tmp_path))
    assert generated == source_id_for_root(str(tmp_path))
    assert source_id_for_root(str(tmp_path), explicit_id=" Team Docs! ") == "team-docs"


def test_process_is_alive_handles_os_error_variants(monkeypatch) -> None:
    assert trinaxai_core._process_is_alive(0) is False
    monkeypatch.setattr(trinaxai_core.os, "kill", lambda *_args: (_ for _ in ()).throw(ProcessLookupError()))
    assert trinaxai_core._process_is_alive(123) is False
    monkeypatch.setattr(trinaxai_core.os, "kill", lambda *_args: (_ for _ in ()).throw(PermissionError()))
    assert trinaxai_core._process_is_alive(123) is True
    monkeypatch.setattr(trinaxai_core.os, "kill", lambda *_args: (_ for _ in ()).throw(OSError()))
    assert trinaxai_core._process_is_alive(123) is False


def test_process_is_alive_windows_probe(monkeypatch) -> None:
    class Kernel:
        def __init__(self, handle):
            self.handle = handle
            self.closed = False

        def OpenProcess(self, *_args):
            return self.handle

        def CloseHandle(self, *_args):
            self.closed = True

    fake_kernel = Kernel(1)
    fake_ctypes = type("FakeCtypes", (), {"windll": type("Windll", (), {"kernel32": fake_kernel})})
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    monkeypatch.setattr(trinaxai_core.os, "name", "nt")
    assert trinaxai_core._process_is_alive(123) is True
    assert fake_kernel.closed is True
    fake_kernel.handle = 0
    assert trinaxai_core._process_is_alive(123) is False


def test_process_lock_reclaims_stale_and_respects_live_owner(tmp_path, monkeypatch) -> None:
    stale = tmp_path / "stale.lock"
    stale.mkdir()
    (stale / "owner.json").write_text('{"pid": 0}', encoding="utf-8")
    with trinaxai_core.exclusive_process_lock(stale, timeout=0.01):
        assert (stale / "owner.json").exists()

    foreign = tmp_path / "foreign.lock"
    foreign.mkdir()
    (foreign / "owner.json").write_text('{"pid": 999}', encoding="utf-8")
    monkeypatch.setattr(trinaxai_core, "_process_is_alive", lambda _pid: True)
    with pytest.raises(TimeoutError):
        with trinaxai_core.exclusive_process_lock(foreign, timeout=0.01, poll_interval=0.01):
            pass

    malformed = tmp_path / "malformed.lock"
    malformed.mkdir()
    (malformed / "owner.json").write_text("not json", encoding="utf-8")
    old = trinaxai_core.time.time() - (25 * 60 * 60)
    trinaxai_core.os.utime(malformed, (old, old))
    with trinaxai_core.exclusive_process_lock(malformed, timeout=0.01):
        assert (malformed / "owner.json").exists()

    failed_once = tmp_path / "failed-once.lock"
    failed_once.mkdir()
    (failed_once / "owner.json").write_text('{"pid": 0}', encoding="utf-8")
    original_rmtree = trinaxai_core.shutil.rmtree
    attempts = {"count": 0}

    def flaky_rmtree(path):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OSError("busy")
        original_rmtree(path)

    monkeypatch.setattr(trinaxai_core.shutil, "rmtree", flaky_rmtree)
    monkeypatch.setattr(trinaxai_core, "_process_is_alive", lambda _pid: False)
    with trinaxai_core.exclusive_process_lock(failed_once, timeout=0.01):
        assert attempts["count"] >= 1

    stat_unavailable = tmp_path / "stat-unavailable.lock"
    stat_unavailable.mkdir()
    (stat_unavailable / "owner.json").write_text("broken", encoding="utf-8")
    original_stat = trinaxai_core.Path.stat

    def unavailable_stat(path, *args, **kwargs):
        if path == stat_unavailable:
            raise OSError("metadata unavailable")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(trinaxai_core.Path, "stat", unavailable_stat)
    with pytest.raises(TimeoutError):
        with trinaxai_core.exclusive_process_lock(stat_unavailable, timeout=0.01, poll_interval=0.01):
            pass


def test_process_lock_tolerates_corrupt_owner_during_cleanup(tmp_path) -> None:
    lock = tmp_path / "corrupt-owner.lock"
    with trinaxai_core.exclusive_process_lock(lock):
        (lock / "owner.json").write_text("broken", encoding="utf-8")
    assert lock.exists()
    trinaxai_core.shutil.rmtree(lock)


def test_positive_number_helpers_clamp_and_fallback() -> None:
    assert trinaxai_core._positive_int("9", 1, minimum=2, maximum=5) == 5
    assert trinaxai_core._positive_int("bad", 7) == 7
    assert trinaxai_core._positive_float("-1.5", 2.0, minimum=0.5) == 0.5
    assert trinaxai_core._positive_float("bad", 2.0) == 2.0
