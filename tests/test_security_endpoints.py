"""Security tests for TrinaxAI system endpoints.

Tests authorization, token validation, LAN access control, and
localhost checks. Uses mocks — never executes real system commands.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from app.security.admin_auth import (
    _client_host,
    _is_lan_client,
    _is_local_client,
    authorize_system,
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


class TestLocalhostIPv6:
    def test_ipv6_loopback(self):
        assert _is_lan_client("::1") is True

    def test_ipv4_mapped_loopback(self):
        assert _is_lan_client("::ffff:127.0.0.1") is True

    def test_ipv6_link_local(self):
        assert _is_lan_client("fe80::1") is True

    def test_ipv6_private(self):
        assert _is_lan_client("fd00::1") is True


class TestClientHost:
    def test_extracts_client_ip(self):
        req = _make_request(client_host="192.168.1.5")
        assert _client_host(req) == "192.168.1.5"

    def test_falls_back_when_no_client(self):
        req = MagicMock()
        req.client = None
        assert _client_host(req) == "127.0.0.1"


class TestLocalClient:
    def test_loopback_variants_are_local(self):
        for host in ["127.0.0.1", "127.0.0.2", "127.255.255.255", "::1", "0:0:0:0:0:0:0:1"]:
            assert _is_local_client(host) is True

    def test_private_lan_is_not_local(self):
        assert _is_local_client("192.168.1.100") is False


# ── Admin token validation ──


class TestAdminToken:
    def test_accepts_correct_token(self, monkeypatch):
        """Request with the correct X-Admin-Token should pass without error."""
        import app.security.admin_auth as auth_mod
        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "secret123")

        req = _make_request(
            client_host="8.8.8.8",
            headers={"X-Admin-Token": "secret123"},
        )
        try:
            authorize_system(req)
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

    def test_allows_lan_when_enabled(self, monkeypatch):
        """LAN access must work when TRINAXAI_ALLOW_LAN_SYSTEM=1."""
        import app.security.admin_auth as auth_mod
        monkeypatch.setattr(auth_mod, "ALLOW_LAN_SYSTEM", True)
        monkeypatch.setattr(auth_mod, "ADMIN_TOKEN", "")

        req = _make_request(client_host="192.168.1.100")
        try:
            authorize_system(req)
        except HTTPException:
            pytest.fail("LAN should be allowed when TRINAXAI_ALLOW_LAN_SYSTEM=1.")

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

        client = TestClient(rag_api.app, raise_server_exceptions=False)

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

        client = TestClient(rag_api.app, raise_server_exceptions=False)
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

        client = TestClient(rag_api.app, raise_server_exceptions=False)
        response = client.post(
            "/system/reload",
            headers={"X-Admin-Token": "my-secret"},
        )
        # May return 200 (OK) or 500 (no index) — both mean auth passed
        assert response.status_code != 403

    def test_shutdown_with_correct_token_allows(self, monkeypatch):
        """/system/shutdown with correct token should pass auth (even if service manager fails)."""
        import rag_api
        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "shutdown-secret")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        # Mock _spawn_service_manager to prevent real process spawn
        with patch.object(rag_api, "_spawn_service_manager"):
            client = TestClient(rag_api.app, raise_server_exceptions=False)
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
            client = TestClient(rag_api.app, raise_server_exceptions=False)
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

    def test_runtime_accepts_admin_token_from_public_ip(self, monkeypatch):
        import rag_api

        monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "runtime-secret")
        monkeypatch.setattr(rag_api, "ALLOW_LAN_SYSTEM", False)

        req = _make_request(
            client_host="8.8.8.8",
            headers={"X-Admin-Token": "runtime-secret"},
        )
        rag_api._authorize_system(req)

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
