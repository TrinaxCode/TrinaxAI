from __future__ import annotations

import warnings
from pathlib import Path

from trinaxai_cli import config as config_module
from trinaxai_cli.config import CLIConfig


def test_config_round_trips_all_public_fields_atomically(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.toml"
    expected = CLIConfig(
        api_base_url='https://example.test/"api"',
        engine="rag",
        model='model\\with"quotes',
        collections=["docs", 'team "notes"'],
        active_collection='team "notes"',
        ui_color="never",
        session_enabled=True,
        session_dir=r"C:\Users\TrinaxAI",
    )

    assert expected.save(path) == path
    assert not path.with_suffix(".toml.tmp").exists()
    loaded = CLIConfig.load(path)

    assert loaded == expected
    assert loaded.api == {"base_url": expected.api_base_url, "verify_tls": True}
    assert loaded.defaults["collections"] == expected.collections
    assert loaded.ui == {"color": "never"}
    assert loaded.session == {"enabled": True, "dir": expected.session_dir}
    assert loaded.to_dict()["model"] == expected.model


def test_config_discovery_prefers_explicit_existing_file(monkeypatch, tmp_path: Path) -> None:
    explicit = tmp_path / "explicit.toml"
    default = tmp_path / "xdg" / "trinaxai" / "config.toml"
    explicit.write_text('[defaults]\nmodel = "explicit"\n', encoding="utf-8")
    default.parent.mkdir(parents=True)
    default.write_text('[defaults]\nmodel = "default"\n', encoding="utf-8")
    monkeypatch.setenv("TRINAXAI_CONFIG", str(explicit))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert CLIConfig.find_config() == explicit
    assert CLIConfig.load().model == "explicit"

    explicit.unlink()
    assert CLIConfig.find_config() == default


def test_config_missing_unreadable_and_malformed_files_fall_back(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    assert CLIConfig.load(missing) == CLIConfig()

    unreadable = tmp_path / "directory.toml"
    unreadable.mkdir()
    assert CLIConfig.load(unreadable) == CLIConfig()

    malformed = tmp_path / "malformed.toml"
    malformed.write_text("[defaults\nmodel =", encoding="utf-8")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert CLIConfig.load(malformed) == CLIConfig()
    assert "Malformed config" in str(caught[0].message)

    monkeypatch.setattr(config_module, "_config_search_paths", lambda: [missing])
    assert CLIConfig.find_config() is None


def test_fallback_parser_reads_the_format_written_by_the_cli(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "tomllib", None)
    raw = b"""
        # comment
        ignored = "outside a section"
        [api]
        verify_tls = true
        [defaults]
        model = "small"
        collections = ["docs", "code, examples"]
        empty = []
        [session]
        enabled = false
    """

    parsed = config_module._parse_toml(raw)

    assert parsed["api"]["verify_tls"] is True
    assert parsed["defaults"]["collections"] == ["docs", "code, examples"]
    assert parsed["defaults"]["empty"] == []
    assert parsed["session"]["enabled"] is False
