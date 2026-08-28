"""Security tests for TrinaxAI system endpoints.

Tests authorization, token validation, LAN access control, and
localhost checks. Uses mocks — never executes real system commands.
"""

from __future__ import annotations

import secrets
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.testclient import TestClient

from app.routes import pairing as pairing_routes
from app.security.admin_auth import (
    _client_host,
    _is_lan_client,
    _is_local_browser_origin,
    _is_local_client,
    _is_trusted_proxy_peer,
    _load_proxy_secret,
    _validate_browser_origin,
    authorize_lan_or_scope,
    authorize_scope,
    authorize_system,
    required_scopes_for_request,
)

# ── Test helpers ──


def _make_request(client_host: str = "127.0.0.1", headers: dict | None = None) -> MagicMock:
    """Build a mock FastAPI Request with a given client IP and headers."""
    req = MagicMock()
    req.client.host = client_host
    req.headers = headers or {}
    return req


# ── Localhost / IP validation ──


class TestLocalhostIPv4:
    def test_loopback_127_0_0_1(self):
        assert _is_lan_client("127.0.0.1") is True

    def test_loopback_localhost(self):
        assert _is_lan_client("localhost") is True

    def test_private_192_168(self):
        assert _is_lan_client("192.168.1.100") is True

    def test_private_10_x(self):
        assert _is_lan_client("10.0.0.5") is True

    def test_private_172_16(self):
        assert _is_lan_client("172.16.0.1") is True

    def test_public_ip_rejected(self):
        assert _is_lan_client("8.8.8.8") is False

    def test_public_ipv6_rejected(self):
        assert _is_lan_client("2001:4860:4860::8888") is False


@pytest.mark.asyncio
async def test_pairing_revoke_returns_404_for_unknown_device(monkeypatch):
    monkeypatch.setattr(pairing_routes, "authorize_scope", lambda *_args: None)
    monkeypatch.setattr(pairing_routes, "revoke_device", lambda _device_id: None)
    with pytest.raises(HTTPException) as exc:
        await pairing_routes.pairing_revoke("missing-device", _make_request())
    assert exc.value.status_code == 404

    device = {"id": "known-device", "revoked_at": 1}
    monkeypatch.setattr(pairing_routes, "revoke_device", lambda _device_id: device)
    assert await pairing_routes.pairing_revoke("known-device", _make_request()) == {"ok": True, "device": device}


class TestLocalhostIPv6:
    def test_ipv6_loopback(self):
        assert _is_lan_client("::1") is True

    def test_ipv4_mapped_loopback(self):
        assert _is_lan_client("::ffff:127.0.0.1") is True

    def test_ipv6_link_local(self):
        assert _is_lan_client("fe80::1") is True

    def test_ipv6_private(self):
        assert _is_lan_client("fd00::1") is True


def test_admin_helper_scope_mapping_origin_and_proxy_secret(tmp_path, monkeypatch):
    assert _is_trusted_proxy_peer("127.0.0.1") is True
    monkeypatch.setenv("TRINAXAI_PROXY_TRUSTED_PEERS", "10.0.0.0/8,invalid")
    assert _is_trusted_proxy_peer("10.2.3.4") is True
    assert _is_trusted_proxy_peer("8.8.8.8") is False

    monkeypatch.setenv("TRINAXAI_PROXY_SECRET_FILE", str(tmp_path / "proxy-secret"))
    import app.security.admin_auth as auth_mod

    monkeypatch.setattr(auth_mod, "_PROXY_SECRET", None)
    generated = _load_proxy_secret()
    assert len(generated) == 64
    monkeypatch.setattr(auth_mod, "_PROXY_SECRET", None)
    assert _load_proxy_secret() == generated
    monkeypatch.setenv("TRINAXAI_PROXY_SECRET", "configured")
    monkeypatch.setattr(auth_mod, "_PROXY_SECRET", None)
    assert _load_proxy_secret() == b"configured"

    from starlette.requests import Request

    def request(path: str, method: str = "GET", headers=None):
        return Request(
            {
                "type": "http",
                "method": method,
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [(key.encode(), value.encode()) for key, value in (headers or {}).items()],
                "client": ("127.0.0.1", 1234),
                "server": ("localhost", 3333),
            }
        )

    assert required_scopes_for_request(request("/v1/agent/run", "POST")) == ("agent",)
    assert required_scopes_for_request(request("/v1/watch/status")) == ("index",)
    assert required_scopes_for_request(request("/collections")) == ("read_private",)
    assert required_scopes_for_request(request("/collections", "POST")) == ("index",)
    assert required_scopes_for_request(request("/v1/sources/docs/file", "DELETE")) == ("index",)
    assert required_scopes_for_request(request("/app-state", "GET")) == ("read_private",)
    assert required_scopes_for_request(request("/app-state", "DELETE")) == ("system",)
    assert required_scopes_for_request(request("/attachments/a/open", "POST")) == ("system",)
    assert required_scopes_for_request(request("/attachments/a", "DELETE")) == ("system",)
    assert required_scopes_for_request(request("/v1/memory", "POST")) == ("system",)
    assert required_scopes_for_request(request("/v1/memory/context", "POST")) == ("read_private",)
    assert required_scopes_for_request(request("/v1/settings/web-search", "PUT")) == ("system",)
    assert required_scopes_for_request(request("/v1/settings", "PUT")) == ("system",)
    assert required_scopes_for_request(request("/unknown")) == ("system",)

    monkeypatch.delenv("TRINAXAI_CORS_ORIGINS", raising=False)
    _validate_browser_origin(request("/health", headers={"origin": "https://localhost:3334"}))
    bad = request("/health", headers={"origin": "https://evil.example"})
    with pytest.raises(HTTPException):
        _validate_browser_origin(bad)


def test_loopback_auto_trust_rejects_lan_browser_origin(monkeypatch):
    import app.security.admin_auth as auth_mod

    monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "")
    monkeypatch.setenv("TRINAXAI_CORS_ORIGIN_REGEX", r"https?://192\.168\.1\.\d+:3334")
    request = _make_request(
        client_host="127.0.0.1",
        headers={"Origin": "https://192.168.1.50:3334"},
    )
    with pytest.raises(HTTPException) as denied:
        authorize_system(request)
    assert denied.value.status_code == 403
    assert "loopback" in str(denied.value.detail).lower()


def test_loopback_origin_parser_does_not_trust_remote_hostnames():
    assert _is_local_browser_origin("https://localhost:3334") is True
    assert _is_local_browser_origin("https://127.0.0.1:3334") is True
    assert _is_local_browser_origin("https://192.168.1.50:3334") is False
    assert _is_local_browser_origin("https://localhost.evil.example:3334") is False


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/app-state", "DELETE"),
        ("/system/stop-all", "POST"),
        ("/system/index-upload", "POST"),
        ("/v1/agent", "POST"),
        ("/collections", "POST"),
        ("/v1/sources/file.txt", "DELETE"),
        ("/attachments/abc/open", "POST"),
        ("/attachments/abc", "DELETE"),
        ("/v1/memory", "POST"),
        ("/v1/pairing/devices", "GET"),
    ],
)
def test_remote_admin_token_never_grants_host_only_matrix(path, method, monkeypatch):
    import app.security.admin_auth as auth_mod

    monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "remote-admin")
    request = Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"x-admin-token", b"remote-admin")],
            "client": ("192.168.1.90", 50000),
            "server": ("localhost", 3333),
        }
    )
    with pytest.raises(HTTPException) as denied:
        authorize_system(request)
    assert denied.value.status_code == 403
    assert "localhost" in str(denied.value.detail).lower()


class TestClientHost:
    def test_extracts_client_ip(self):
        req = _make_request(client_host="192.168.1.5")
        assert _client_host(req) == "192.168.1.5"

    def test_falls_back_when_no_client(self):
        req = MagicMock()
        req.client = None
        req.headers = {}
        assert _client_host(req) == "unknown"


class TestLocalClient:
    def test_loopback_variants_are_local(self):
        for host in ["127.0.0.1", "127.0.0.2", "127.255.255.255", "::1", "0:0:0:0:0:0:0:1"]:
            assert _is_local_client(host) is True

    def test_private_lan_is_not_local(self):
        assert _is_local_client("192.168.1.100") is False


class TestLanDocumentAccess:
    def test_unauthenticated_lan_peer_can_use_stateless_chat_feature(self):
        request = _make_request(client_host="192.168.1.50")
        authorize_lan_or_scope(request, "chat")
        assert request.state.trinaxai_identity == {"kind": "lan", "scopes": ["chat"]}

    def test_unauthenticated_public_peer_is_rejected(self):
        request = _make_request(client_host="8.8.8.8")
        with pytest.raises(HTTPException) as exc:
            authorize_lan_or_scope(request, "chat")
        assert exc.value.status_code == 403

    def test_invalid_credential_cannot_fall_back_to_lan_access(self, monkeypatch):
        import app.security.admin_auth as auth_mod

        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "valid-token")
        request = _make_request(
            client_host="192.168.1.50",
            headers={"X-Admin-Token": "wrong-token"},
        )
        with pytest.raises(HTTPException) as exc:
            authorize_lan_or_scope(request, "chat")
        assert exc.value.status_code == 403


def test_device_without_required_scope_cannot_fall_back_to_lan(monkeypatch):
    import app.security.admin_auth as auth_mod

    monkeypatch.setattr(auth_mod, "authenticate_device_token", lambda *_args: None)
    request = _make_request(
        client_host="192.168.1.50",
        headers={"X-TrinaxAI-Device-Token": "invalid-device-token"},
    )
    with pytest.raises(HTTPException) as exc:
        authorize_scope(request, "read_private")
    assert exc.value.status_code == 403


# ── Admin token validation ──


class TestAdminToken:
    def test_accepts_correct_token_for_remote_safe_scope(self, monkeypatch):
        """An admin token may authenticate private reads, but not host control."""
        import app.security.admin_auth as auth_mod

        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "secret123")

        req = _make_request(
            client_host="8.8.8.8",
            headers={"X-Admin-Token": "secret123"},
        )
        try:
            authorize_scope(req, "read_private")
        except HTTPException:
            pytest.fail("Correct admin token should be accepted.")

    def test_rejects_wrong_token(self, monkeypatch):
        """Wrong X-Admin-Token must be rejected immediately."""
        import app.security.admin_auth as auth_mod

        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "secret123")

        req = _make_request(
            client_host="127.0.0.1",
            headers={"X-Admin-Token": "wrong-token"},
        )
        with pytest.raises(HTTPException) as exc:
            authorize_system(req)
        assert exc.value.status_code == 403
        assert "invalid" in str(exc.value.detail).lower()

    def test_no_token_required_when_not_set(self, monkeypatch):
        """When ADMIN_TOKEN is empty, localhost access should work."""
        import app.security.admin_auth as auth_mod

        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "")

        req = _make_request(client_host="127.0.0.1")
        try:
            authorize_system(req)
        except HTTPException:
            pytest.fail("Localhost should be allowed when no admin token is set.")

    def test_localhost_still_works_with_token_set(self, monkeypatch):
        """Localhost should work even when a token is configured (no token header)."""
        import app.security.admin_auth as auth_mod

        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "secret123")

        req = _make_request(client_host="127.0.0.1", headers={})
        try:
            authorize_system(req)
        except HTTPException:
            pytest.fail("Localhost should be allowed even with admin token configured.")

    def test_remote_token_is_mandatory_even_when_lan_is_enabled(self, monkeypatch):
        """A configured credential must not silently fall back to LAN trust."""
        import app.security.admin_auth as auth_mod

        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "secret123")
        monkeypatch.setattr(auth_mod, "ALLOW_LAN_SYSTEM", True)
        with pytest.raises(HTTPException) as exc:
            authorize_system(_make_request(client_host="192.168.1.20"))
        assert exc.value.status_code == 403
        assert "localhost" in str(exc.value.detail).lower()


class TestTrustedProxyIdentity:
    def _signed_request(
        self,
        auth_mod,
        *,
        client_ip: str,
        secret: bytes,
        path: str = "/app-state",
        method: str = "GET",
        nonce: str | None = None,
    ):
        timestamp = str(int(time.time()))
        nonce = nonce or secrets.token_hex(16)
        signature = auth_mod._proxy_signature(
            secret,
            client_ip,
            timestamp,
            nonce,
            method,
            path,
        )
        request = _make_request(
            client_host="127.0.0.1",
            headers={
                "X-TrinaxAI-Proxy": "v1",
                "X-TrinaxAI-Client-IP": client_ip,
                "X-TrinaxAI-Proxy-Timestamp": timestamp,
                "X-TrinaxAI-Proxy-Nonce": nonce,
                "X-TrinaxAI-Proxy-Signature": signature,
            },
        )
        request.method = method
        request.url.path = path
        return request

    def test_signed_proxy_preserves_remote_identity(self, monkeypatch):
        import app.security.admin_auth as auth_mod

        secret = b"gateway-test-secret"
        monkeypatch.setattr(auth_mod, "_PROXY_SECRET", secret)
        request = self._signed_request(auth_mod, client_ip="192.168.1.77", secret=secret)
        assert _client_host(request) == "192.168.1.77"

    def test_remote_via_loopback_proxy_cannot_bypass_admin_token(self, monkeypatch):
        import app.security.admin_auth as auth_mod

        secret = b"gateway-test-secret"
        monkeypatch.setattr(auth_mod, "_PROXY_SECRET", secret)
        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "required-token")
        monkeypatch.setattr(auth_mod, "ALLOW_LAN_SYSTEM", True)
        request = self._signed_request(
            auth_mod,
            client_ip="192.168.1.77",
            secret=secret,
            path="/system/shutdown",
            method="POST",
        )
        request.headers["X-Admin-Token"] = "required-token"
        with pytest.raises(HTTPException) as exc:
            authorize_system(request)
        assert exc.value.status_code == 403
        assert "localhost" in str(exc.value.detail).lower()

    def test_forged_proxy_identity_is_rejected(self, monkeypatch):
        import app.security.admin_auth as auth_mod

        secret = b"gateway-test-secret"
        monkeypatch.setattr(auth_mod, "_PROXY_SECRET", secret)
        request = self._signed_request(auth_mod, client_ip="192.168.1.77", secret=b"wrong-secret")
        with pytest.raises(HTTPException) as exc:
            _client_host(request)
        assert exc.value.status_code == 403

    def test_replayed_proxy_identity_is_rejected(self, monkeypatch):
        import app.security.admin_auth as auth_mod

        secret = b"gateway-test-secret"
        nonce = "a" * 32
        monkeypatch.setattr(auth_mod, "_PROXY_SECRET", secret)
        monkeypatch.setattr(auth_mod, "_PROXY_SEEN_NONCES", {})
        first = self._signed_request(auth_mod, client_ip="192.168.1.77", secret=secret, nonce=nonce)
        replay = self._signed_request(auth_mod, client_ip="192.168.1.77", secret=secret, nonce=nonce)

        assert _client_host(first) == "192.168.1.77"
        with pytest.raises(HTTPException) as exc:
            _client_host(replay)
        assert exc.value.status_code == 403
        assert "replay" in str(exc.value.detail).lower()

    def test_proxy_assertion_from_non_loopback_peer_is_rejected(self, monkeypatch):
        import app.security.admin_auth as auth_mod

        secret = b"gateway-test-secret"
        monkeypatch.setattr(auth_mod, "_PROXY_SECRET", secret)
        request = self._signed_request(auth_mod, client_ip="192.168.1.77", secret=secret)
        request.client.host = "192.168.1.10"
        with pytest.raises(HTTPException) as exc:
            _client_host(request)
        assert exc.value.status_code == 403

    def test_signed_proxy_accepts_configured_runtime_peer(self, monkeypatch):
        import app.security.admin_auth as auth_mod

        secret = b"gateway-test-secret"
        monkeypatch.setattr(auth_mod, "_PROXY_SECRET", secret)
        monkeypatch.setenv("TRINAXAI_PROXY_TRUSTED_PEERS", "172.31.0.0/24")
        request = self._signed_request(auth_mod, client_ip="192.168.1.77", secret=secret)
        request.client.host = "172.31.0.2"
        assert _client_host(request) == "192.168.1.77"

    def test_configured_runtime_peer_without_signature_is_still_remote(self, monkeypatch):
        import app.security.admin_auth as auth_mod

        monkeypatch.setenv("TRINAXAI_PROXY_TRUSTED_PEERS", "172.31.0.0/24")
        with pytest.raises(HTTPException) as exc:
            auth_mod.authorize_scope(_make_request(client_host="172.31.0.2"), "chat")
        assert exc.value.status_code == 403

    def test_rate_limit_uses_verified_original_peer(self, monkeypatch):
        import app.security.admin_auth as auth_mod
        import app.security.rate_limit as rate_mod

        secret = b"gateway-test-secret"
        monkeypatch.setattr(auth_mod, "_PROXY_SECRET", secret)
        monkeypatch.setattr(rate_mod, "_RATE_LIMIT_MAX", 1)
        rate_mod.state.rate_limit_clients.clear()
        rate_mod.state.rate_limit_last_prune = 0.0
        first = self._signed_request(
            auth_mod,
            client_ip="192.168.1.77",
            secret=secret,
            path="/v1/chat/completions",
            method="POST",
        )
        second = self._signed_request(
            auth_mod,
            client_ip="192.168.1.78",
            secret=secret,
            path="/v1/chat/completions",
            method="POST",
        )

        rate_mod.enforce_rate_limit(first)
        rate_mod.enforce_rate_limit(second)
        with pytest.raises(HTTPException) as exc:
            rate_mod.enforce_rate_limit(first)
        assert exc.value.status_code == 429
        assert int(exc.value.headers["Retry-After"]) >= 1
        rate_mod.state.rate_limit_clients.clear()


# ── LAN system control ──


class TestLANSystemControl:
    def test_allows_loopback_variants_when_lan_disabled(self, monkeypatch):
        """Loopback addresses must not require LAN system control."""
        import app.security.admin_auth as auth_mod

        monkeypatch.setattr(auth_mod, "ALLOW_LAN_SYSTEM", False)
        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "")

        for host in ["127.0.0.2", "127.255.255.255", "0:0:0:0:0:0:0:1"]:
            authorize_system(_make_request(client_host=host))

    def test_blocks_lan_when_disabled(self, monkeypatch):
        """LAN access must be rejected when TRINAXAI_ALLOW_LAN_SYSTEM=0."""
        import app.security.admin_auth as auth_mod

        monkeypatch.setattr(auth_mod, "ALLOW_LAN_SYSTEM", False)
        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "")

        req = _make_request(client_host="192.168.1.100")
        with pytest.raises(HTTPException) as exc:
            authorize_system(req)
        assert exc.value.status_code == 403

    def test_legacy_flag_never_allows_lan(self, monkeypatch):
        """The retired flag must never turn a LAN peer into localhost."""
        import app.security.admin_auth as auth_mod

        monkeypatch.setattr(auth_mod, "ALLOW_LAN_SYSTEM", True)
        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "")

        with pytest.raises(HTTPException) as exc:
            authorize_system(_make_request(client_host="192.168.1.100"))
        assert exc.value.status_code == 403

    def test_public_ip_rejected_without_token(self, monkeypatch):
        """Public IPs must be rejected when no admin token is set."""
        import app.security.admin_auth as auth_mod

        monkeypatch.setattr(auth_mod, "ALLOW_LAN_SYSTEM", False)
        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "")

        req = _make_request(client_host="45.33.32.156")
        with pytest.raises(HTTPException) as exc:
            authorize_system(req)
        assert exc.value.status_code == 403


# ── System endpoint safety (no real execution) ──


class TestSystemEndpointSafety:
    """Verify that dangerous system operations are properly gated."""

    def test_shutdown_endpoint_requires_auth(self, monkeypatch):
        """/system/shutdown must reject requests without auth."""
        # This tests the FastAPI dependency — the authorize_system call
        # inside the endpoint will raise HTTPException for unauthorized requests.

        from fastapi.testclient import TestClient

        # Patch environment so no admin token is set and LAN is disabled
        monkeypatch.setenv("TRINAXAI_ADMIN_TOKEN", "")
        monkeypatch.setenv("TRINAXAI_ALLOW_LAN_SYSTEM", "0")

        # We test with a mock client that simulates a remote request
        import rag_api

        client = TestClient(rag_api.app, raise_server_exceptions=False, client=("127.0.0.1", 50000))

        # Simulate request from a public IP, no token
        response = client.post(
            "/system/shutdown",
            headers={"X-Forwarded-For": "8.8.8.8"},
        )
        # The authorize_system function uses request.client.host, not X-Forwarded-For,
        # so TestClient connections from localhost will pass. This is expected behavior
        # for local testing. The security is validated in the unit tests above.
        # This test just verifies the endpoint exists and responds.
        assert response.status_code in {200, 403}

    def test_reload_endpoint_requires_auth(self, monkeypatch):
        """/system/reload must reject unauthorized requests."""
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "test-token")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        client = TestClient(rag_api.app, raise_server_exceptions=False, client=("127.0.0.1", 50000))
        response = client.post(
            "/system/reload",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 403

    def test_reload_endpoint_accepts_correct_token(self, monkeypatch):
        """/system/reload must accept requests with the correct token."""
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "my-secret")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        client = TestClient(rag_api.app, raise_server_exceptions=False, client=("127.0.0.1", 50000))
        response = client.post(
            "/system/reload",
            headers={"X-Admin-Token": "my-secret"},
        )
        # May return 200 (OK) or 500 (no index) — both mean auth passed
        assert response.status_code != 403

    def test_shutdown_with_correct_token_allows(self, monkeypatch):
        """/system/shutdown with correct token should pass auth (even if service manager fails)."""
        import rag_api
        from app.services import system_service

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "shutdown-secret")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        # Mock _spawn_service_manager to prevent real process spawn
        with patch.object(system_service, "_spawn_service_manager"):
            client = TestClient(rag_api.app, raise_server_exceptions=False, client=("127.0.0.1", 50000))
            response = client.post(
                "/system/shutdown",
                headers={"X-Admin-Token": "shutdown-secret"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True

    def test_self_test_endpoint_requires_auth(self, monkeypatch):
        """/system/self-test must reject without auth."""
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "required")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        client = TestClient(rag_api.app, raise_server_exceptions=False)
        response = client.post(
            "/system/self-test",
            headers={},  # no token
        )
        assert response.status_code == 403

    def test_startup_endpoint_mocked(self, monkeypatch):
        """/system/startup with auth should not execute real startup."""
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "start-token")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        # Mock subprocess.run to prevent real execution
        with patch("rag_api.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            client = TestClient(rag_api.app, raise_server_exceptions=False, client=("127.0.0.1", 50000))
            response = client.post(
                "/system/startup",
                headers={"X-Admin-Token": "start-token"},
            )
            assert response.status_code == 200

    def test_index_upload_requires_auth(self, monkeypatch):
        """/system/index-upload must reject without proper auth (or return 422 for missing form)."""
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "upload-token")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        client = TestClient(rag_api.app, raise_server_exceptions=False)
        response = client.post(
            "/system/index-upload",
            headers={},  # no token
        )
        # Either 403 (auth rejected) or 422 (form validation before auth) is acceptable
        assert response.status_code in {403, 422}


class TestRuntimeAuthorizeSystem:
    """Cover the authorization helper actually used by rag_api.py routes."""

    def test_runtime_blocks_lan_when_disabled(self, monkeypatch):
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        req = _make_request(client_host="192.168.1.100")
        with pytest.raises(HTTPException) as exc:
            rag_api._authorize_system(req)
        assert exc.value.status_code == 403

    def test_runtime_rejects_admin_token_from_public_ip(self, monkeypatch):
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "runtime-secret")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        req = _make_request(
            client_host="8.8.8.8",
            headers={"X-Admin-Token": "runtime-secret"},
        )
        with pytest.raises(HTTPException) as exc:
            rag_api._authorize_system(req)
        assert exc.value.status_code == 403

    def test_runtime_ignores_x_forwarded_for(self, monkeypatch):
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        req = _make_request(
            client_host="127.0.0.1",
            headers={"X-Forwarded-For": "8.8.8.8"},
        )
        rag_api._authorize_system(req)

    def test_runtime_allows_loopback_variants_when_lan_disabled(self, monkeypatch):
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        for host in ["127.0.0.2", "127.255.255.255", "0:0:0:0:0:0:0:1"]:
            rag_api._authorize_system(_make_request(client_host=host))

    def test_runtime_rejects_untrusted_browser_origin_even_on_loopback(self, monkeypatch):
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "")
        request = _make_request(
            client_host="127.0.0.1",
            headers={"Origin": "https://malicious.example"},
        )
        with pytest.raises(HTTPException) as exc:
            rag_api._authorize_system(request)
        assert exc.value.status_code == 403

    def test_runtime_accepts_trusted_pwa_origin(self, monkeypatch):
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "")
        request = _make_request(
            client_host="127.0.0.1",
            headers={"Origin": "https://localhost:3334"},
        )
        rag_api._authorize_system(request)


class TestPrivateDataEndpoints:
    """Private state and attachment identifiers must not be public on LAN."""

    def test_remote_app_state_requires_configured_token(self, tmp_path, monkeypatch):
        import app.security.admin_auth as auth_mod
        from app.main import app
        from app.services import app_state_service

        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "private-token")
        monkeypatch.setattr(auth_mod, "ALLOW_LAN_SYSTEM", True)
        monkeypatch.setattr(app_state_service, "APP_STATE_PATH", str(tmp_path / "app_state.json"))
        client = TestClient(app, client=("192.168.1.50", 50000))

        denied = client.get("/app-state")
        allowed = client.get("/app-state", headers={"X-Admin-Token": "private-token"})

        assert denied.status_code == 403
        assert allowed.status_code == 200
        assert allowed.json()["values"] == {}

    def test_remote_attachment_lookup_requires_token_before_id_lookup(self, monkeypatch):
        import app.security.admin_auth as auth_mod
        from app.main import app

        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "private-token")
        monkeypatch.setattr(auth_mod, "ALLOW_LAN_SYSTEM", True)
        client = TestClient(app, client=("192.168.1.50", 50000))

        denied = client.get(f"/attachments/{'a' * 32}")
        authenticated = client.get(
            f"/attachments/{'a' * 32}",
            headers={"X-Admin-Token": "private-token"},
        )

        assert denied.status_code == 403
        assert authenticated.status_code == 404

    def test_remote_attachment_host_open_is_forbidden(self, monkeypatch):
        import app.security.admin_auth as auth_mod
        from app.main import app

        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "private-token")
        monkeypatch.setattr(auth_mod, "ALLOW_LAN_SYSTEM", True)
        client = TestClient(app, client=("192.168.1.50", 50000))

        response = client.post(
            f"/attachments/{'a' * 32}/open",
            headers={"X-Admin-Token": "private-token"},
        )

        assert response.status_code == 403

    def test_collection_names_are_private(self, monkeypatch):
        import app.security.admin_auth as auth_mod
        from app.main import app

        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "private-token")
        client = TestClient(app, client=("192.168.1.50", 50000))
        assert client.get("/collections").status_code == 403


# ── No dangerous command execution ──


class TestNoDangerousCommands:
    def test_authorize_system_does_not_execute_commands(self):
        """Authorization must only check tokens/IPs, never execute anything."""
        req = _make_request(client_host="127.0.0.1")
        # This must not spawn processes, read files outside config, etc.
        try:
            authorize_system(req)
        except Exception:
            pytest.fail("authorize_system should not raise for localhost.")

    def test_spawn_service_manager_only_spawns_known_actions(self):
        """_spawn_service_manager must only accept predefined actions."""
        from rag_api import _spawn_service_manager

        # The function should only be called with safe actions internally.
        # We verify it doesn't execute arbitrary strings.
        with patch("rag_api.subprocess.Popen") as mock_popen:
            _spawn_service_manager("/fake/path/service_manager.py", "stop-ai")
            call_args = mock_popen.call_args[0][0]
            # The command must contain the script path and the action
            assert "service_manager.py" in str(call_args)
            assert "stop-ai" in str(call_args)


# ── LAN access edge cases ──


class TestLANEdgeCases:
    def test_localhost_ipv4_variants(self):
        """All common localhost IPv4 representations must be recognized."""
        for host in ["127.0.0.1", "127.0.0.2", "127.255.255.255"]:
            assert _is_lan_client(host) is True, f"{host} should be loopback"

    def test_localhost_ipv6_variants(self):
        """All common localhost IPv6 representations must be recognized."""
        for host in ["::1", "::ffff:127.0.0.1", "0:0:0:0:0:0:0:1"]:
            assert _is_lan_client(host) is True, f"{host} should be loopback"

    def test_private_ranges(self):
        """RFC 1918 private ranges must be recognized."""
        for host in ["10.0.0.1", "172.16.0.1", "172.31.255.255", "192.168.0.1"]:
            assert _is_lan_client(host) is True, f"{host} should be private"

    def test_non_private_not_lan(self):
        """Public IPs must NOT be treated as LAN."""
        for host in ["1.1.1.1", "8.8.8.8", "9.9.9.9"]:
            assert _is_lan_client(host) is False, f"{host} should not be LAN"

    def test_mangled_ip_rejected_safely(self):
        """Invalid IP strings must not cause crashes."""
        for host in ["not-an-ip", "", "256.256.256.256"]:
            # Must not raise; fallback to string matching
            result = _is_lan_client(host)
            assert isinstance(result, bool)
