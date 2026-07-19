from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.testclient import TestClient

from app.main import create_app
from app.security import admin_auth
from app.security.device_auth import (
    DEVICE_TOKEN_HEADER,
    authenticate_device_token,
    claim_pairing_code,
    create_pairing_code,
    list_devices,
    revoke_device,
)


@pytest.fixture
def pairing_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    registry = tmp_path / "device_pairing.json"
    monkeypatch.setenv("TRINAXAI_DEVICE_REGISTRY", str(registry))
    monkeypatch.setenv("TRINAXAI_DEVICE_SECRET_FILE", str(tmp_path / ".device_secret"))
    return registry


def _request(
    path: str,
    *,
    client: str = "192.168.20.40",
    method: str = "GET",
    token: str | None = None,
    admin_token: str | None = None,
) -> Request:
    headers = []
    if token:
        headers.append((DEVICE_TOKEN_HEADER.lower().encode(), token.encode()))
    if admin_token:
        headers.append((b"x-admin-token", admin_token.encode()))
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "scheme": "http",
            "server": ("localhost", 3333),
            "client": (client, 50000),
            "headers": headers,
        }
    )


def test_registry_never_persists_clear_codes_or_tokens_and_claim_is_single_use(pairing_store: Path) -> None:
    created = create_pairing_code(["chat", "read_private"], now=100)
    code = created["code"]
    initial = pairing_store.read_text(encoding="utf-8")
    assert code.replace("-", "") not in initial
    if os.name == "posix":
        assert pairing_store.stat().st_mode & 0o077 == 0

    claimed = claim_pairing_code(code, "Family tablet", now=101)
    token = claimed["token"]
    persisted = pairing_store.read_text(encoding="utf-8")
    assert token not in persisted
    assert code not in persisted
    assert authenticate_device_token(token, "chat", now=102)["name"] == "Family tablet"
    assert authenticate_device_token(token, "read_private", now=102) is not None
    assert authenticate_device_token(token, "system", now=102) is None
    with pytest.raises(PermissionError):
        claim_pairing_code(code, "Second tablet", now=102)


def test_expired_code_and_device_revocation_fail_closed(pairing_store: Path) -> None:
    code = create_pairing_code(["chat"], ttl_seconds=60, device_ttl_days=1, now=100)["code"]
    with pytest.raises(PermissionError):
        claim_pairing_code(code, "Late device", now=161)

    code = create_pairing_code(["chat"], device_ttl_days=1, now=200)["code"]
    claimed = claim_pairing_code(code, "Phone", now=201)
    token = claimed["token"]
    device_id = claimed["device"]["id"]
    assert authenticate_device_token(token, "chat", now=202) is not None
    assert revoke_device(device_id, now=203)["revoked_at"] == 203
    assert authenticate_device_token(token, "chat", now=204) is None
    assert "token_hash" not in list_devices()[0]


def test_scoped_authorization_and_admin_super_scope(pairing_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code = create_pairing_code(["chat", "read_private"], now=100)["code"]
    token = claim_pairing_code(code, "Laptop", now=101)["token"]
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "root-secret")

    admin_auth.authorize_scope(_request("/system/shutdown", method="POST", admin_token="root-secret"), "system")
    admin_auth.authorize_scope(_request("/app-state", token=token), "read_private")
    with pytest.raises(HTTPException) as denied:
        admin_auth.authorize_scope(_request("/system/shutdown", method="POST", token=token), "system")
    assert denied.value.status_code == 403


def test_legacy_lan_system_flag_never_grants_private_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "")
    monkeypatch.setattr(admin_auth, "ALLOW_LAN_SYSTEM", True)
    system_request = _request("/system/shutdown", method="POST")
    admin_auth.authorize_system(system_request)
    with pytest.raises(HTTPException) as denied:
        admin_auth.authorize_system(_request("/app-state"))
    assert denied.value.status_code == 403


def test_unpaired_lan_can_search_web_but_cannot_read_private_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "")
    admin_auth.authorize_scope(_request("/v1/research", method="POST"), "web")
    with pytest.raises(HTTPException) as denied:
        admin_auth.authorize_scope(_request("/app-state"), "read_private")
    assert denied.value.status_code == 403


def test_remote_pairing_claim_and_revocation_endpoint(pairing_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import shared_runtime

    monkeypatch.setattr(shared_runtime, "initialize_runtime", lambda: None)
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "")
    app = create_app()
    with TestClient(app, client=("127.0.0.1", 50100)) as local:
        start = local.post("/v1/pairing/start", json={"scopes": ["chat", "read_private"]})
        assert start.status_code == 200
        code = start.json()["code"]

    with TestClient(app, client=("192.168.1.44", 50101)) as remote:
        claim = remote.post("/v1/pairing/claim", json={"code": code, "device_name": "Phone"})
        assert claim.status_code == 200
        token = claim.json()["token"]
        headers = {DEVICE_TOKEN_HEADER: token}
        assert remote.get("/v1/pairing/me", headers=headers).status_code == 200
        assert remote.delete("/v1/pairing/me", headers=headers).status_code == 200
        assert remote.get("/v1/pairing/me", headers=headers).status_code == 403

    document = json.loads(pairing_store.read_text(encoding="utf-8"))
    assert document["pairing_codes"] == {}


def test_remote_cannot_start_or_inventory_pairing(pairing_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import shared_runtime

    monkeypatch.setattr(shared_runtime, "initialize_runtime", lambda: None)
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "admin")
    with TestClient(create_app(), client=("192.168.1.55", 50100)) as remote:
        assert remote.post("/v1/pairing/start", json={}).status_code == 403
        assert remote.get("/v1/pairing/devices").status_code == 403
        assert (
            remote.post(
                "/v1/pairing/start",
                json={},
                headers={"X-Admin-Token": "admin"},
            ).status_code
            == 200
        )


def test_pairing_claim_has_a_dedicated_bruteforce_limit(pairing_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routes import pairing as pairing_routes
    from app.services import shared_runtime

    monkeypatch.setattr(shared_runtime, "initialize_runtime", lambda: None)
    monkeypatch.setattr(pairing_routes, "_CLAIM_LIMIT", 1)
    pairing_routes._CLAIM_WINDOWS.clear()
    with TestClient(create_app(), client=("192.168.1.77", 50100)) as remote:
        first = remote.post(
            "/v1/pairing/claim",
            json={"code": "AAAA-BBBB", "device_name": "Unknown"},
        )
        second = remote.post(
            "/v1/pairing/claim",
            json={"code": "AAAA-BBBB", "device_name": "Unknown"},
        )
    assert first.status_code == 403
    assert second.status_code == 429
    assert second.headers["retry-after"] == "300"
