from __future__ import annotations

from trinaxai_core import SAFE_DEFAULTS, sanitize_collection_id, validate_runtime_config


def test_sanitize_collection_id_rejects_path_traversal_shapes() -> None:
    assert sanitize_collection_id("../../etc/passwd") == "etc-passwd"
    assert sanitize_collection_id("My Project / Docs!") == "my-project-docs"
    assert sanitize_collection_id("") == "collection"


def test_runtime_config_uses_safe_defaults() -> None:
    cfg = validate_runtime_config({})
    assert cfg["profile"] == SAFE_DEFAULTS["profile"]
    assert cfg["ollama_base_url"] == SAFE_DEFAULTS["ollama_base_url"]
    assert cfg["default_collection_id"] == "default"
    assert cfg["allow_lan_system"] is False


def test_runtime_config_falls_back_on_invalid_values() -> None:
    cfg = validate_runtime_config(
        {
            "TRINAXAI_PROFILE": "unknown",
            "OLLAMA_BASE_URL": "file:///tmp/socket",
            "TRINAXAI_NUM_CTX": "not-a-number",
            "TRINAXAI_EMBED_WORKERS": "999",
            "TRINAXAI_DEFAULT_COLLECTION_ID": "../bad id",
        }
    )
    assert cfg["profile"] == "16gb"
    assert cfg["ollama_base_url"] == "http://localhost:11434"
    assert cfg["num_ctx"] == 4096
    assert cfg["embed_workers"] == 16
    assert cfg["default_collection_id"] == "bad-id"
