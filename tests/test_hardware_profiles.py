from __future__ import annotations

import json

import pytest

import trinaxai_core
from app.services import health_service
from trinaxai_core import (
    VALID_PROFILES,
    load_hardware_profile,
    migrate_profile_env,
    model_recommendations,
    normalize_profile,
    recommended_ollama_gpu_layers,
    save_hardware_profile,
    select_profile,
)


def _hardware(ram_gb: int, *, vendor: str = "none", vram_gb: int | None = None, unified: bool = False) -> dict:
    gpu = {
        "vendor": vendor,
        "name": "test GPU",
        "vram_bytes": vram_gb * 1024**3 if vram_gb else None,
        "unified_memory": unified,
    }
    return {
        "ram": {"total_bytes": ram_gb * 10**9},
        "gpu": gpu,
        "gpus": [gpu],
    }


def test_profiles_use_ram_and_gpu_together() -> None:
    assert {"8gb", "16gb", "32gb", "64gb"} == VALID_PROFILES

    gpu_first = _hardware(8, vendor="nvidia", vram_gb=12)
    assert select_profile(gpu_first) == "32gb"
    assert model_recommendations(gpu_first)["general"] == "qwen3.5:9b"
    assert model_recommendations(gpu_first, profile="8gb")["general"] == "qwen3.5:2b"
    assert recommended_ollama_gpu_layers(gpu_first) == 999

    cpu_first = _hardware(64, vendor="amd", vram_gb=2)
    assert model_recommendations(cpu_first)["general"] == "qwen3.5:35b"
    assert recommended_ollama_gpu_layers(cpu_first) == 999


def test_profile_boundaries_use_decimal_memory_labels() -> None:
    expected = [
        (7.9, "8gb"),
        (8, "8gb"),
        (15.9, "8gb"),
        (16, "16gb"),
        (31.9, "16gb"),
        (32, "32gb"),
        (63.9, "32gb"),
        (64, "64gb"),
    ]
    for ram_gb, profile in expected:
        hardware = {"ram": {"total_bytes": int(ram_gb * 10**9)}}
        assert select_profile(hardware) == profile


def test_gpu_parsers_cover_nvidia_windows_and_apple(monkeypatch) -> None:
    monkeypatch.setattr(
        trinaxai_core,
        "_command_output",
        lambda _args, **_kwargs: "RTX test, 12288",
    )
    nvidia = trinaxai_core._nvidia_gpus()
    assert nvidia[0]["vendor"] == "nvidia"
    assert nvidia[0]["vram_bytes"] == 12288 * 1024**2

    windows_json = json.dumps({"Name": "AMD Radeon Test", "AdapterRAM": 8 * 1024**3})
    monkeypatch.setattr(trinaxai_core, "_command_output", lambda _args, **_kwargs: windows_json)
    windows = trinaxai_core._windows_gpus()
    assert windows[0]["vendor"] == "amd"
    assert windows[0]["vram_bytes"] == 8 * 1024**3

    mac_json = json.dumps({"SPDisplaysDataType": [{"sppci_model": "Apple M GPU"}]})
    monkeypatch.setattr(trinaxai_core, "_command_output", lambda _args, **_kwargs: mac_json)
    apple = trinaxai_core._mac_gpus(apple_silicon=True, ram_bytes=16 * 10**9)
    assert apple[0]["vendor"] == "apple"
    assert apple[0]["unified_memory"] is True
    assert apple[0]["vram_bytes"] is None


def test_detection_degrades_cleanly_without_a_gpu(monkeypatch) -> None:
    monkeypatch.setattr(trinaxai_core.platform, "system", lambda: "Linux")
    monkeypatch.setattr(trinaxai_core.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(trinaxai_core, "_ram_bytes", lambda: 16 * 10**9)
    monkeypatch.setattr(trinaxai_core, "_cpu_model", lambda: "Test CPU")
    monkeypatch.setattr(trinaxai_core, "_cpu_cores", lambda: 8)
    monkeypatch.setattr(trinaxai_core, "_nvidia_gpus", lambda: [])
    monkeypatch.setattr(trinaxai_core, "_linux_gpus", lambda: [])

    hardware = trinaxai_core.detect_hardware()

    assert hardware["cpu"] == {"model": "Test CPU", "cores": 8}
    assert hardware["ram"]["total_bytes"] == 16 * 10**9
    assert hardware["gpu"]["vendor"] == "none"
    assert hardware["gpus"] == []
    assert recommended_ollama_gpu_layers(hardware) == 0


def test_unknown_vram_still_enables_ollama_gpu_offload() -> None:
    hardware = _hardware(16, vendor="nvidia")
    assert model_recommendations(hardware)["general"] == "qwen3.5:4b"
    assert recommended_ollama_gpu_layers(hardware) == 999


def test_model_recommendations_cover_ram_vram_and_unified_memory() -> None:
    cases = [
        (_hardware(8), "qwen3.5:2b"),
        (_hardware(8, vendor="amd", vram_gb=8), "qwen3.5:4b"),
        (_hardware(8, vendor="nvidia", vram_gb=12), "qwen3.5:9b"),
        (_hardware(16), "qwen3.5:4b"),
        (_hardware(32), "qwen3.5:9b"),
        (_hardware(64), "qwen3.5:35b"),
        (_hardware(32, vendor="apple", unified=True), "qwen3.5:9b"),
        (_hardware(64, vendor="apple", unified=True), "qwen3.5:35b"),
    ]
    for hardware, model in cases:
        assert model_recommendations(hardware)["general"] == model


def test_cpu_caps_large_ram_profile_without_a_gpu() -> None:
    hardware = _hardware(64)
    hardware["cpu"] = {"model": "Small CPU", "cores": 4}

    assert select_profile(hardware) == "16gb"
    assert model_recommendations(hardware)["general"] == "qwen3.5:4b"


def test_legacy_profile_values_migrate_and_never_persist(tmp_path) -> None:
    legacy_32 = bytes((109, 97, 120)).decode("ascii")
    legacy_64 = bytes((117, 108, 116, 114, 97)).decode("ascii")
    legacy_8 = bytes((108, 111, 119)).decode("ascii")
    assert normalize_profile(legacy_32) == "32gb"
    assert normalize_profile(legacy_64) == "64gb"
    assert normalize_profile(legacy_8) == "8gb"
    assert normalize_profile("unsupported", fallback="16gb") == "16gb"

    dotenv = tmp_path / ".env"
    dotenv.write_text(f"TRINAXAI_PROFILE={legacy_32} # migrated\n", encoding="utf-8")
    assert migrate_profile_env(dotenv) is True
    assert dotenv.read_text(encoding="utf-8") == "TRINAXAI_PROFILE=32gb # migrated\n"

    snapshot = tmp_path / "hardware_profile.json"
    hardware = _hardware(64)
    snapshot.write_text(json.dumps({"profile": legacy_64, "hardware": hardware}), encoding="utf-8")
    loaded = load_hardware_profile(snapshot)
    assert loaded and loaded["profile"] == "64gb"
    assert loaded["detected_profile"] == "64gb"
    persisted = json.loads(snapshot.read_text(encoding="utf-8"))
    assert persisted["profile"] == "64gb"
    assert persisted["detected_profile"] == "64gb"
    save_hardware_profile(snapshot, hardware, legacy_32)
    assert json.loads(snapshot.read_text(encoding="utf-8"))["profile"] == "32gb"
    updated_at = json.loads(snapshot.read_text(encoding="utf-8"))["updated_at"]
    save_hardware_profile(snapshot, hardware, "32gb")
    assert json.loads(snapshot.read_text(encoding="utf-8"))["updated_at"] == updated_at
    hardware_8 = _hardware(4)
    snapshot.write_text(json.dumps({"profile": legacy_8, "hardware": hardware_8}), encoding="utf-8")
    loaded = load_hardware_profile(snapshot)
    assert loaded and loaded["profile"] == "8gb"
    assert json.loads(snapshot.read_text(encoding="utf-8"))["profile"] == "8gb"


@pytest.mark.asyncio
async def test_health_and_resources_expose_canonical_hardware_contract() -> None:
    health = await health_service.health()
    resources = await health_service.resources()
    profiles = {"8gb", "16gb", "32gb", "64gb"}
    assert set(health["features"]["profiles"]) == profiles
    assert health["profile"] in profiles
    assert health["detected_profile"] in profiles
    assert health["hardware"]["cpu"]["model"]
    assert "model_recommendations" in health
    assert resources["profile"] in profiles
    assert resources["detected_profile"] in profiles
    assert resources["models"]
    assert "model_recommendations" in resources
    assert "vram" in resources
