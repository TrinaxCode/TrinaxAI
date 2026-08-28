from pathlib import Path

from scripts.generate_continue_config import generate


def test_generate_continue_config_uses_profile_and_env_overrides(tmp_path: Path) -> None:
    root = tmp_path / "trinaxai"
    root.mkdir()
    (root / ".env").write_text(
        "TRINAXAI_PROFILE=8gb\nTRINAXAI_MODEL_GENERAL=custom-chat:latest\n",
        encoding="utf-8",
    )
    (root / "continue-config.yaml").write_text(
        Path("continue-config.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    output = tmp_path / "generated.yaml"

    generate(root, output, None)

    text = output.read_text(encoding="utf-8")
    assert text.startswith("# Generated automatically for TrinaxAI profile 8gb.")
    assert "# ACTIVE PROFILE: 8gb" in text
    assert "# Active chat/code: custom-chat:latest / qwen3.5:2b" in text
    assert "contextLength: 8192" in text
    assert "model: qwen3-embedding:0.6b" in text


def test_generate_continue_config_keeps_64gb_autocomplete_and_embedding_aligned(tmp_path: Path) -> None:
    root = tmp_path / "trinaxai"
    root.mkdir()
    (root / "continue-config.yaml").write_text(
        Path("continue-config.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    output = tmp_path / "generated.yaml"

    generate(root, output, "64gb")

    text = output.read_text(encoding="utf-8")
    assert "# Active autocomplete: qwen3.5:4b (Fast)" in text
    assert "# Active embeddings: qwen3-embedding:4b" in text
    assert "tabAutocompleteModel: Qwen3.5 4B (Fast)" in text
    assert "model: qwen3-embedding:4b" in text
