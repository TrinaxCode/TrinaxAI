import ssl
from pathlib import Path

import certifi
import pytest

from trinaxai_cli.client import TrinaxAPIClient
from trinaxai_cli.config import DEFAULT_BASE_URL


def test_cli_defaults_to_verified_https():
    assert DEFAULT_BASE_URL == "https://localhost:3333"


def test_local_ca_file_is_used_without_disabling_verification(monkeypatch):
    ca_file = Path(certifi.where())
    monkeypatch.setenv("TRINAXAI_CA_FILE", str(ca_file))
    client = object.__new__(TrinaxAPIClient)
    client.base_url = "https://localhost:3333"

    assert isinstance(client._resolve_local_ca(True), ssl.SSLContext)
    with pytest.raises(ValueError, match="cannot be disabled"):
        client._resolve_local_ca(False)


def test_remote_urls_never_trust_the_local_ca(monkeypatch):
    ca_file = Path(certifi.where())
    monkeypatch.setenv("TRINAXAI_CA_FILE", str(ca_file))
    client = object.__new__(TrinaxAPIClient)
    client.base_url = "https://example.test:3333"

    assert isinstance(client._resolve_local_ca(True), ssl.SSLContext)
