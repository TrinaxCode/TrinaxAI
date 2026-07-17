from __future__ import annotations

from pathlib import Path


def test_wheel_includes_backend_runtime_modules() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = (root / "pyproject.toml").read_text(encoding="utf-8")
    required = {
        "config",
        "index",
        "rag_api",
        "service_manager",
        "trinaxai_core",
        "trinaxai_index_storage",
    }
    for module in required:
        assert f'"{module}"' in manifest
