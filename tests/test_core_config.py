from __future__ import annotations

from trinaxai_core import (
    SAFE_DEFAULTS,
    VALID_PROFILES,
    normalize_http_base_url,
    sanitize_collection_id,
    validate_runtime_config,
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


def test_http_base_url_validation_rejects_unsafe_and_malformed_schemes() -> None:
    assert normalize_http_base_url("https://ollama.example:11434/") == "https://ollama.example:11434"
    assert normalize_http_base_url("file:///tmp/socket", "http://localhost:11434") == "http://localhost:11434"
    assert normalize_http_base_url("http://localhost:bad", "fallback") == "fallback"
    assert normalize_http_base_url("http://localhost:11434/api", "fallback") == "fallback"
    assert normalize_http_base_url("http://user:secret@localhost:11434", "fallback") == "fallback"
    assert normalize_http_base_url("http://bad host:11434", "fallback") == "fallback"


def test_runtime_config_accepts_profile_aliases() -> None:
    assert validate_runtime_config({"TRINAXAI_PROFILE": "8g"})["profile"] == "8g"
    assert validate_runtime_config({"TRINAXAI_PROFILE": "4g"})["profile"] == "4g"
