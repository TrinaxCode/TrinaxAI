from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security.host_guard import TrustedHostGuardMiddleware, is_trusted_host


@pytest.mark.parametrize(
    "host",
    [
        None,
        "",
        "localhost",
        "localhost:3333",
        "LOCALHOST.:3333",
        "127.0.0.1:3333",
        "192.168.1.20",
        "[::1]:3333",
        "::1",
        "testserver",
        "api:3333",
        "app.localhost:3333",
        "laptop.local:3334",
    ],
)
def test_safe_hosts_are_trusted(monkeypatch, host):
    monkeypatch.delenv("TRINAXAI_ALLOWED_HOSTS", raising=False)
    assert is_trusted_host(host) is True


@pytest.mark.parametrize("host", ["evil.example", "evil.example:3333", "evil.example.:3333", "[::1", "[]:3333"])
def test_foreign_domains_are_rejected(monkeypatch, host):
    monkeypatch.delenv("TRINAXAI_ALLOWED_HOSTS", raising=False)
    assert is_trusted_host(host) is False


def test_configured_hosts_and_wildcard(monkeypatch):
    monkeypatch.setenv("TRINAXAI_ALLOWED_HOSTS", " ai.home.arpa. , ,other.example")
    assert is_trusted_host("AI.home.arpa:3333") is True
    assert is_trusted_host("other.example") is True
    assert is_trusted_host("evil.example") is False
    monkeypatch.setenv("TRINAXAI_ALLOWED_HOSTS", "*")
    assert is_trusted_host("evil.example") is True


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(TrustedHostGuardMiddleware)

    @app.get("/private")
    def private() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_middleware_blocks_rebinding_and_allows_local(monkeypatch):
    monkeypatch.delenv("TRINAXAI_ALLOWED_HOSTS", raising=False)
    client = _client()

    blocked = client.get("/private", headers={"Host": "evil.example:3333"})
    assert blocked.status_code == 421
    assert blocked.json()["detail"]["code"] == "untrusted_host"

    assert client.get("/private", headers={"Host": "127.0.0.1:3333"}).json() == {"ok": True}


def test_middleware_passes_non_http_scopes():
    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["type"])

    asyncio.run(TrustedHostGuardMiddleware(inner)({"type": "lifespan"}, None, None))
    assert seen == ["lifespan"]


def test_application_rejects_foreign_host(monkeypatch):
    monkeypatch.delenv("TRINAXAI_ALLOWED_HOSTS", raising=False)
    from app.main import create_app

    response = TestClient(create_app()).get("/app-state", headers={"Host": "evil.example:3333"})
    assert response.status_code == 421
    assert response.headers["X-Content-Type-Options"] == "nosniff"
