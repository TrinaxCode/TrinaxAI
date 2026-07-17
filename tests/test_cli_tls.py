from pathlib import Path

from trinaxai_cli.client import TrinaxAPIClient
from trinaxai_cli.config import DEFAULT_BASE_URL


def test_cli_defaults_to_verified_https():
    assert DEFAULT_BASE_URL == "https://localhost:3333"


def test_local_ca_file_is_used_without_disabling_verification(tmp_path, monkeypatch):
    ca_file = tmp_path / "rootCA.pem"
    ca_file.write_text("test CA path", encoding="utf-8")
    monkeypatch.setenv("TRINAXAI_CA_FILE", str(ca_file))
    client = object.__new__(TrinaxAPIClient)
    client.base_url = "https://localhost:3333"

    assert client._resolve_local_ca(True) == str(ca_file)
    assert client._resolve_local_ca(False) is False


def test_remote_urls_never_trust_the_local_ca(tmp_path, monkeypatch):
    ca_file = Path(tmp_path) / "rootCA.pem"
    ca_file.write_text("test CA path", encoding="utf-8")
    monkeypatch.setenv("TRINAXAI_CA_FILE", str(ca_file))
    client = object.__new__(TrinaxAPIClient)
    client.base_url = "https://example.test:3333"

    assert client._resolve_local_ca(True) is True
