from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import trinaxai_core as core


def test_core_persistence_and_parsing_error_edges(monkeypatch, tmp_path: Path):
    assert core.migrate_profile_env(tmp_path / "missing.env") is False
    dotenv = tmp_path / ".env"
    dotenv.write_text("TRINAXAI_PROFILE=max\n", encoding="utf-8")
    original_replace = core.os.replace
    monkeypatch.setattr(core.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace")))
    assert core.migrate_profile_env(dotenv) is False
    monkeypatch.setattr(core.os, "replace", original_replace)
    original_unlink = Path.unlink

    def fail_migration_cleanup(candidate, *args, **kwargs):
        if candidate.parent == tmp_path and candidate.name.startswith("..env."):
            raise OSError("cleanup")
        return original_unlink(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_migration_cleanup)
    monkeypatch.setattr(core.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace")))
    assert core.migrate_profile_env(dotenv) is False
    monkeypatch.setattr(core.os, "replace", original_replace)
    monkeypatch.setattr(Path, "unlink", original_unlink)

    broken = tmp_path / "broken.json"
    broken.write_text("{broken", encoding="utf-8")
    assert core.load_hardware_profile(broken) is None
    broken.write_text("[]", encoding="utf-8")
    assert core.load_hardware_profile(broken) is None
    broken.write_text(json.dumps({"profile": "unknown", "hardware": []}), encoding="utf-8")
    assert core.load_hardware_profile(broken) is None

    monkeypatch.setattr(core.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")))
    assert core._command_output(["missing"]) == ""
    monkeypatch.setattr(
        core.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="ignored")
    )
    assert core._command_output(["failed"]) == ""
    assert core._parse_size(None) is None
    assert core._parse_size("unknown") is None


def test_core_platform_fallbacks_and_memory_parsers(monkeypatch):
    monkeypatch.setattr(core.sys, "platform", "linux")
    monkeypatch.setattr(core.Path, "read_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cpu")))
    monkeypatch.setattr(core.platform, "processor", lambda: "")
    monkeypatch.setattr(core.platform, "uname", lambda: SimpleNamespace(processor=""))
    monkeypatch.setattr(core.platform, "machine", lambda: "fallback")
    assert core._cpu_model() == "fallback"

    monkeypatch.setitem(sys.modules, "psutil", None)
    monkeypatch.setattr(core.sys, "platform", "darwin")
    monkeypatch.setattr(core, "_command_output", lambda *_args, **_kwargs: "6")
    assert core._cpu_cores() == 6
    monkeypatch.setattr(core, "_command_output", lambda *_args, **_kwargs: "not-a-number")
    monkeypatch.setattr(core.os, "cpu_count", lambda: 4)
    assert core._cpu_cores() == 4

    monkeypatch.setattr(core.sys, "platform", "linux")
    monkeypatch.setattr(
        core.Path,
        "read_text",
        lambda path, **_kwargs: (
            "MemTotal:       123 kB" if str(path) == "/proc/meminfo" else (_ for _ in ()).throw(OSError("cpu"))
        ),
    )
    assert core._ram_bytes() == 123 * 1024
    monkeypatch.setattr(core.Path, "read_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("mem")))
    assert core._ram_bytes() == 0

    monkeypatch.setattr(core.sys, "platform", "darwin")
    monkeypatch.setattr(core, "_command_output", lambda *_args, **_kwargs: "987654")
    assert core._ram_bytes() == 987654
    monkeypatch.setattr(core, "_command_output", lambda *_args, **_kwargs: "bad")
    assert core._ram_bytes() == 0

    monkeypatch.setattr(core.sys, "platform", "win32")
    monkeypatch.setattr(core.os, "name", "nt")
    monkeypatch.setitem(sys.modules, "ctypes", SimpleNamespace())
    assert core._ram_bytes() == 0


def test_core_gpu_parser_and_detection_edges(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(core, "_command_output", lambda *_args, **_kwargs: " , 4\nRTX, 2")
    assert len(core._nvidia_gpus()) == 1

    monkeypatch.setattr(
        core, "_command_output", lambda *_args, **_kwargs: json.dumps({"SPDisplaysDataType": {"sppci_model": "GPU"}})
    )
    assert core._mac_gpus(apple_silicon=False, ram_bytes=0)
    monkeypatch.setattr(core, "_command_output", lambda *_args, **_kwargs: json.dumps({"SPDisplaysDataType": [None]}))
    assert core._mac_gpus(apple_silicon=False, ram_bytes=0) == []

    device_unknown = tmp_path / "unknown"
    device_unknown.mkdir()
    (device_unknown / "vendor").write_text("0x9999", encoding="utf-8")
    device_bad_vram = tmp_path / "bad-vram"
    device_bad_vram.mkdir()
    (device_bad_vram / "vendor").write_text("0x10de", encoding="utf-8")
    (device_bad_vram / "product_name").write_text("PRODUCT_NAME=Test GPU", encoding="utf-8")
    (device_bad_vram / "mem_info_vram_total").write_text("bad", encoding="utf-8")
    monkeypatch.setattr(core.Path, "glob", lambda *_args, **_kwargs: [device_unknown, device_bad_vram])
    monkeypatch.setattr(core, "_command_output", lambda *_args, **_kwargs: "")
    assert core._linux_gpus()[0]["vram_bytes"] is None

    monkeypatch.setattr(core.Path, "glob", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(core, "_command_output", lambda *_args, **_kwargs: "Audio controller: test")
    assert core._linux_gpus() == []

    monkeypatch.setattr(core.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(core.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(core, "_ram_bytes", lambda: 16 * 10**9)
    monkeypatch.setattr(core, "_cpu_model", lambda: "cpu")
    monkeypatch.setattr(core, "_cpu_cores", lambda: 8)
    monkeypatch.setattr(core, "_mac_gpus", lambda **_kwargs: [])
    assert core.detect_hardware()["gpu"]["vendor"] == "none"

    monkeypatch.setattr(core.platform, "system", lambda: "Windows")
    monkeypatch.setattr(core.platform, "machine", lambda: "x86")
    monkeypatch.setattr(core, "_nvidia_gpus", lambda: [])
    monkeypatch.setattr(core, "_windows_gpus", lambda: [])
    assert core.detect_hardware()["gpu"]["vendor"] == "none"


def test_core_profile_save_and_lock_cleanup_errors(monkeypatch, tmp_path: Path):
    profile = tmp_path / "profile.json"
    hardware = {"ram": {"total_bytes": 16 * 10**9}}
    original_replace = core.os.replace
    monkeypatch.setattr(core.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace")))
    core.save_hardware_profile(profile, hardware, "16gb")
    monkeypatch.setattr(core.os, "replace", original_replace)

    original_unlink = Path.unlink

    def fail_unlink(candidate, *args, **kwargs):
        if candidate.parent == tmp_path and candidate.name.startswith(".profile.json."):
            raise OSError("cleanup")
        return original_unlink(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    monkeypatch.setattr(core.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace")))
    core.save_hardware_profile(profile, hardware, "16gb")
    monkeypatch.setattr(core.os, "replace", original_replace)

    lock = tmp_path / "retry.lock"
    lock.mkdir()
    (lock / "owner.json").write_text('{"pid": 0}', encoding="utf-8")
    replace_calls = 0

    def flaky_replace(source, target):
        nonlocal replace_calls
        replace_calls += 1
        if replace_calls == 1:
            raise OSError("busy")
        return original_replace(source, target)

    monkeypatch.setattr(core.os, "replace", flaky_replace)
    with core.exclusive_process_lock(lock, timeout=0.1):
        assert replace_calls >= 2


def test_core_process_probe_returns_true_when_signal_succeeds(monkeypatch):
    monkeypatch.setattr(core.os, "name", "posix")
    monkeypatch.setattr(core.os, "kill", lambda *_args: None)
    assert core._process_is_alive(123) is True
