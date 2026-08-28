from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import trinaxai_core


def test_cpu_and_ram_fallbacks_cover_supported_platforms(monkeypatch) -> None:
    monkeypatch.setattr(trinaxai_core.sys, "platform", "win32")
    monkeypatch.setattr(trinaxai_core.os, "name", "nt")
    monkeypatch.setattr(trinaxai_core, "_command_output", lambda *_args, **_kwargs: "Windows CPU")
    assert trinaxai_core._cpu_model() == "Windows CPU"

    monkeypatch.setattr(trinaxai_core.sys, "platform", "darwin")
    monkeypatch.setattr(trinaxai_core.os, "name", "posix")
    monkeypatch.setattr(trinaxai_core, "_command_output", lambda *_args, **_kwargs: "Apple CPU")
    assert trinaxai_core._cpu_model() == "Apple CPU"

    total = 24 * 10**9

    def memory_status(status) -> bool:
        status.ullTotalPhys = total
        return True

    fake_ctypes = SimpleNamespace(
        Structure=object,
        c_uint32=int,
        c_uint64=int,
        sizeof=lambda _status: 1,
        byref=lambda status: status,
        windll=SimpleNamespace(kernel32=SimpleNamespace(GlobalMemoryStatusEx=memory_status)),
    )
    monkeypatch.setitem(sys.modules, "psutil", None)
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    monkeypatch.setattr(trinaxai_core.sys, "platform", "win32")
    monkeypatch.setattr(trinaxai_core.os, "name", "nt")
    assert trinaxai_core._ram_bytes() == total


def test_gpu_discovery_degrades_and_uses_platform_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(trinaxai_core, "_command_output", lambda *_args, **_kwargs: "")
    assert trinaxai_core._windows_gpus() == []

    monkeypatch.setattr(trinaxai_core, "_command_output", lambda *_args, **_kwargs: "not-json")
    assert trinaxai_core._windows_gpus() == []
    apple = trinaxai_core._mac_gpus(apple_silicon=True, ram_bytes=16 * 10**9)
    assert apple == [
        {
            "vendor": "apple",
            "name": "Apple Silicon GPU",
            "vram_bytes": None,
            "unified_memory": True,
        }
    ]

    windows = json.dumps([None, {"Name": "NVIDIA test", "AdapterRAM": 4_294_967_295}])
    monkeypatch.setattr(trinaxai_core, "_command_output", lambda *_args, **_kwargs: windows)
    assert trinaxai_core._windows_gpus()[0]["vram_bytes"] is None

    monkeypatch.setattr(trinaxai_core.Path, "glob", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        trinaxai_core,
        "_command_output",
        lambda *_args, **_kwargs: "01:00.0 VGA compatible controller: NVIDIA Test GPU",
    )
    assert trinaxai_core._linux_gpus()[0]["vendor"] == "nvidia"
