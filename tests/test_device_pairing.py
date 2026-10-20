from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request
from starlette.testclient import TestClient

from app.main import create_app
from app.routes import pairing as pairing_routes
from app.routes.pairing import NewDeviceRequest, PairingClaimRequest
from app.security import admin_auth
from app.security.admin_auth import DEVICE_TOKEN_COOKIE, DEVICE_TOKEN_COOKIE_PATH
from app.security.device_auth import (
    DEVICE_TOKEN_HEADER,
    DeviceRegistryError,
    _empty_registry,
    _ensure_private_secret,
    _read_registry,
    _write_registry,
    authenticate_device_token,
    claim_pairing_code,
    create_new_device_session,
    create_pairing_code,
    device_for_token,
    list_devices,
    normalize_pairing_code,
    revoke_device,
    sanitize_device_name,
    update_device_scopes,
    validate_scopes,
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
    cookie: str | None = None,
    scheme: str = "http",
) -> Request:
    headers = []
    if token:
        headers.append((DEVICE_TOKEN_HEADER.lower().encode(), token.encode()))
    if admin_token:
        headers.append((b"x-admin-token", admin_token.encode()))
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "scheme": scheme,
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


def test_new_device_session_is_chat_web_only_and_revocable(pairing_store: Path) -> None:
    created = create_new_device_session("Fresh phone", now=100)
    token = created["token"]
    assert created["device"]["scopes"] == ["chat", "web"]
    assert authenticate_device_token(token, "chat", now=101) is not None
    assert authenticate_device_token(token, "web", now=101) is not None
    assert authenticate_device_token(token, "read_private", now=101) is None
    assert revoke_device(created["device"]["id"], now=102)["revoked_at"] == 102


@pytest.mark.asyncio
async def test_new_device_endpoint_issues_cookie_without_private_scope(pairing_store: Path) -> None:
    response = Response()
    result = await pairing_routes.pairing_new_device(
        NewDeviceRequest(device_name="Fresh phone"),
        _request("/v1/pairing/new-device", client="192.168.1.44"),
        response,
    )
    assert result["device"]["scopes"] == ["chat", "web"]
    assert f"Path={DEVICE_TOKEN_COOKIE_PATH}" in response.headers["set-cookie"]
    with pytest.raises(HTTPException) as denied:
        await pairing_routes.pairing_new_device(
            NewDeviceRequest(device_name="Public client"),
            _request("/v1/pairing/new-device", client="8.8.8.8"),
            Response(),
        )
    assert denied.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status"),
    [(ValueError("bad name"), 422), (DeviceRegistryError("locked"), 503)],
)
async def test_new_device_endpoint_maps_storage_and_validation_errors(
    pairing_store: Path, monkeypatch, error: Exception, status: int
) -> None:
    def fail(_name):
        raise error

    monkeypatch.setattr(pairing_routes, "create_new_device_session", fail)
    with pytest.raises(HTTPException) as raised:
        await pairing_routes.pairing_new_device(
            NewDeviceRequest(device_name="Fresh phone"),
            _request("/v1/pairing/new-device", client="192.168.1.44"),
            Response(),
        )
    assert raised.value.status_code == status


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

    admin_auth.authorize_scope(
        _request("/system/shutdown", client="127.0.0.1", method="POST", admin_token="root-secret"),
        "system",
    )
    admin_auth.authorize_scope(_request("/app-state", token=token), "read_private")
    with pytest.raises(HTTPException) as denied:
        admin_auth.authorize_scope(_request("/system/shutdown", method="POST", token=token), "system")
    assert denied.value.status_code == 403


def test_legacy_lan_system_flag_never_grants_private_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "")
    monkeypatch.setattr(admin_auth, "ALLOW_LAN_SYSTEM", True)
    with pytest.raises(HTTPException) as system_denied:
        admin_auth.authorize_system(_request("/system/shutdown", method="POST"))
    assert system_denied.value.status_code == 403
    with pytest.raises(HTTPException) as denied:
        admin_auth.authorize_system(_request("/app-state"))
    assert denied.value.status_code == 403


def test_paired_lan_can_search_web_but_unpaired_lan_cannot_read_private_data(
    pairing_store: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "")
    with pytest.raises(HTTPException):
        admin_auth.authorize_scope(_request("/v1/research", method="POST"), "web")
    code = create_pairing_code(["chat", "read_private", "web"], now=100)["code"]
    token = claim_pairing_code(code, "Research tablet", now=101)["token"]
    admin_auth.authorize_scope(_request("/v1/research", method="POST", token=token), "web")
    with pytest.raises(HTTPException) as denied:
        admin_auth.authorize_scope(_request("/app-state"), "read_private")
    assert denied.value.status_code == 403


def test_web_scope_cannot_mutate_host_search_settings(pairing_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "")
    code = create_pairing_code(["web"], now=100)["code"]
    token = claim_pairing_code(code, "Research tablet", now=101)["token"]

    with pytest.raises(HTTPException) as denied:
        admin_auth.authorize_system(_request("/v1/settings/web-search", method="PUT", token=token))

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
        assert "token" not in claim.json()
        cookie = claim.headers["set-cookie"]
        assert f"{DEVICE_TOKEN_COOKIE}=" in cookie
        assert "HttpOnly" in cookie
        assert "samesite=strict" in cookie.lower()
        assert f"Path={DEVICE_TOKEN_COOKIE_PATH}" in cookie
        assert "Secure" not in cookie
        token = cookie.split(";", 1)[0].split("=", 1)[1]
        cookie_header = f"{DEVICE_TOKEN_COOKIE}={token}"
        assert remote.get("/v1/pairing/me", headers={"Cookie": cookie_header}).status_code == 200
        legacy = remote.get("/v1/pairing/me", headers={DEVICE_TOKEN_HEADER: token})
        assert legacy.status_code == 200
        assert "set-cookie" not in legacy.headers
        revoked = remote.delete("/v1/pairing/me", headers={"Cookie": cookie_header})
        assert revoked.status_code == 200
        assert f"Path={DEVICE_TOKEN_COOKIE_PATH}" in revoked.headers["set-cookie"]
        assert "Max-Age=0" in revoked.headers["set-cookie"]
        assert remote.get("/v1/pairing/me", headers={"Cookie": cookie_header}).status_code == 403
        assert remote.get("/v1/pairing/me", headers={DEVICE_TOKEN_HEADER: token}).status_code == 403

    document = json.loads(pairing_store.read_text(encoding="utf-8"))
    assert document["pairing_codes"] == {}


def test_browser_device_cookie_covers_both_chat_proxy_paths() -> None:
    assert DEVICE_TOKEN_COOKIE_PATH == "/api"
    assert "/api/rag".startswith(DEVICE_TOKEN_COOKIE_PATH)
    assert "/api/ollama".startswith(DEVICE_TOKEN_COOKIE_PATH)


@pytest.mark.asyncio
async def test_pairing_me_migrates_legacy_cookie_scope(pairing_store: Path) -> None:
    claimed = claim_pairing_code(create_pairing_code(["chat"], now=100)["code"], "Legacy phone", now=101)
    response = Response()

    result = await pairing_routes.pairing_me(
        _request(
            "/v1/pairing/me",
            cookie=f"{DEVICE_TOKEN_COOKIE}={claimed['token']}",
        ),
        response,
    )

    assert result["device"]["name"] == "Legacy phone"
    assert f"Path={DEVICE_TOKEN_COOKIE_PATH}" in response.headers["set-cookie"]


def test_lifespan_clears_stopping_state_when_runtime_initialization_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import shared_runtime, system_service
    from app.services.engine_state import state

    was_stopping = state.lifecycle_stopping.is_set()
    try:
        state.lifecycle_stopping.set()
        monkeypatch.setattr(shared_runtime, "initialize_runtime", lambda: None)
        monkeypatch.setattr(system_service, "shutdown_runtime", state.lifecycle_stopping.set)

        with TestClient(create_app()):
            assert not state.lifecycle_stopping.is_set()
        assert not state.lifecycle_stopping.is_set()
    finally:
        if was_stopping:
            state.lifecycle_stopping.set()
        else:
            state.lifecycle_stopping.clear()


def test_http_only_cookie_authorizes_scoped_protected_route(pairing_store: Path) -> None:
    claimed = claim_pairing_code(create_pairing_code(["read_private"], now=100)["code"], "Cookie phone", now=101)

    admin_auth.authorize_scope(
        _request(
            "/app-state",
            client="192.168.1.44",
            cookie=f"{DEVICE_TOKEN_COOKIE}={claimed['token']}",
        ),
        "read_private",
    )


@pytest.mark.asyncio
async def test_pairing_claim_marks_cookie_secure_over_https(pairing_store: Path) -> None:
    code = create_pairing_code(["chat"])["code"]
    response = Response()
    await pairing_routes.pairing_claim(
        PairingClaimRequest(code=code, device_name="Secure phone"),
        _request("/v1/pairing/claim", client="192.168.1.44", scheme="https"),
        response,
    )
    assert "Secure" in response.headers["set-cookie"]


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
            == 403
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


def test_device_registry_and_scope_validation_fail_closed(tmp_path: Path) -> None:
    secret = tmp_path / "secret"
    generated = _ensure_private_secret(secret)
    assert len(generated) == 32
    assert _ensure_private_secret(secret) == generated
    secret.write_text("not-hex", encoding="ascii")
    with pytest.raises(DeviceRegistryError):
        _ensure_private_secret(secret)
    secret.write_text("00" * 16, encoding="ascii")
    with pytest.raises(DeviceRegistryError):
        _ensure_private_secret(secret)

    registry = tmp_path / "registry.json"
    assert _read_registry(registry) == _empty_registry()
    registry.write_text("[]", encoding="utf-8")
    with pytest.raises(DeviceRegistryError):
        _read_registry(registry)
    registry.write_text("{broken", encoding="utf-8")
    with pytest.raises(DeviceRegistryError):
        _read_registry(registry)
    _write_registry(registry, _empty_registry())
    assert _read_registry(registry)["schema_version"] == 1

    assert normalize_pairing_code(" ab-cd 12 ") == "ABCD12"
    assert validate_scopes(None) == ("chat", "read_private")
    assert validate_scopes(["chat", "chat", "web"]) == ("chat", "web")
    with pytest.raises(ValueError):
        validate_scopes([])
    with pytest.raises(ValueError):
        validate_scopes(["agent_yolo"])
    with pytest.raises(ValueError):
        validate_scopes(["system"])
    with pytest.raises(ValueError):
        validate_scopes(["unknown"])
    assert sanitize_device_name("  Home   tablet ") == "Home tablet"
    with pytest.raises(ValueError):
        sanitize_device_name("")
    with pytest.raises(ValueError):
        sanitize_device_name("x" * 81)
    with pytest.raises(ValueError):
        sanitize_device_name("bad\x00name")


def test_pairing_limits_token_refresh_and_listing(pairing_store: Path) -> None:
    with pytest.raises(ValueError):
        create_pairing_code(["chat"], ttl_seconds=0, device_ttl_days=0, now=1)
    created = create_pairing_code(["chat"], ttl_seconds=1, now=1)
    claimed = claim_pairing_code(created["code"], "Device", now=2)
    token = claimed["token"]
    device_id = claimed["device"]["id"]
    assert authenticate_device_token("invalid", "chat", now=3) is None
    with pytest.raises(ValueError):
        authenticate_device_token(token, "invalid", now=3)
    assert authenticate_device_token(token, "read_private", now=3) is None
    # A later request updates last_seen_at and remains valid.
    assert authenticate_device_token(token, "chat", now=400) is not None
    assert list_devices(include_revoked=False)[0]["id"] == device_id
    assert revoke_device("bad") is None
    assert revoke_device("f" * 24) is None


def test_retired_host_scopes_are_removed_from_legacy_devices(pairing_store: Path) -> None:
    created = create_pairing_code(["chat"], now=100)
    claimed = claim_pairing_code(created["code"], "Legacy device", now=101)
    document = json.loads(pairing_store.read_text(encoding="utf-8"))
    legacy = document["devices"][claimed["device"]["id"]]
    legacy["scopes"] = ["system", "index", "agent", "modify"]
    legacy.pop("grants_version", None)  # records written before per-device grants
    pairing_store.write_text(json.dumps(document), encoding="utf-8")

    assert authenticate_device_token(claimed["token"], "system", now=102) is None
    assert authenticate_device_token(claimed["token"], "index", now=102) is None
    assert authenticate_device_token(claimed["token"], "agent", now=102) is None
    assert device_for_token(claimed["token"]) is None
    assert list_devices()[0]["scopes"] == []


ALL_ELEVATED = ["chat", "read_private", "web", "index", "agent", "modify"]


def _elevated_token(**kwargs) -> str:
    code = create_pairing_code(kwargs.get("scopes", ALL_ELEVATED), now=100)["code"]
    return claim_pairing_code(code, "Granted laptop", now=101)["token"]


def test_host_can_grant_elevated_scopes_but_never_host_only_ones(pairing_store: Path) -> None:
    token = _elevated_token()
    for scope in ("chat", "read_private", "web", "index", "agent", "modify"):
        assert authenticate_device_token(token, scope, now=102) is not None
    assert authenticate_device_token(token, "system", now=102) is None
    assert authenticate_device_token(token, "agent_yolo", now=102) is None
    with pytest.raises(ValueError):
        create_pairing_code(["chat", "system"])
    with pytest.raises(ValueError):
        create_pairing_code(["agent", "agent_yolo"])


def test_update_device_scopes_grants_revokes_and_upgrades_legacy_records(pairing_store: Path) -> None:
    claimed = claim_pairing_code(create_pairing_code(["chat"], now=100)["code"], "Tablet", now=101)
    device_id, token = claimed["device"]["id"], claimed["token"]
    assert authenticate_device_token(token, "agent", now=102) is None

    updated = update_device_scopes(device_id, ["chat", "agent"], now=103)
    assert updated is not None and updated["scopes"] == ["chat", "agent"]
    assert authenticate_device_token(token, "agent", now=104) is not None
    assert authenticate_device_token(token, "index", now=104) is None

    updated = update_device_scopes(device_id, ["chat"], now=105)
    assert updated is not None and updated["scopes"] == ["chat"]
    assert authenticate_device_token(token, "agent", now=106) is None

    for invalid in ([], ["system"], ["agent_yolo"], ["bogus"]):
        with pytest.raises(ValueError):
            update_device_scopes(device_id, invalid)
    assert update_device_scopes("f" * 24, ["chat"]) is None
    assert update_device_scopes("not-an-id", ["chat"]) is None

    # A legacy record is upgraded by an explicit host grant, not before.
    document = json.loads(pairing_store.read_text(encoding="utf-8"))
    document["devices"][device_id]["scopes"] = ["chat", "index"]
    document["devices"][device_id].pop("grants_version", None)
    pairing_store.write_text(json.dumps(document), encoding="utf-8")
    assert authenticate_device_token(token, "index", now=107) is None
    assert update_device_scopes(device_id, ["chat", "index"], now=108)["scopes"] == ["chat", "index"]
    assert authenticate_device_token(token, "index", now=109) is not None

    revoke_device(device_id, now=110)
    assert update_device_scopes(device_id, ["chat", "agent"], now=111) is None


@pytest.mark.parametrize(
    ("scope", "allowed", "denied"),
    [
        (
            "index",
            [
                ("POST", "/system/index-upload"),
                ("POST", "/v1/watch/start"),
                ("POST", "/collections"),
                ("DELETE", "/v1/sources/default/a.txt"),
                ("GET", "/system/index-jobs/abc"),
            ],
            [("POST", "/v1/agent"), ("POST", "/v1/memory"), ("PUT", "/v1/settings/web-search")],
        ),
        (
            "agent",
            [("POST", "/v1/agent"), ("POST", "/v1/agent/approve"), ("GET", "/v1/agent/browse")],
            [("POST", "/system/index-upload"), ("POST", "/v1/memory"), ("DELETE", "/attachments/abc")],
        ),
        (
            "modify",
            [
                ("POST", "/v1/memory"),
                ("PATCH", "/v1/memory/abc"),
                ("DELETE", "/v1/memory/abc"),
                ("PUT", "/v1/settings/web-search"),
                ("DELETE", "/attachments/abc"),
            ],
            [("POST", "/v1/agent"), ("POST", "/collections"), ("POST", "/v1/watch/start")],
        ),
    ],
)
def test_each_elevated_scope_unlocks_only_its_own_routes(
    pairing_store: Path,
    monkeypatch: pytest.MonkeyPatch,
    scope: str,
    allowed: list[tuple[str, str]],
    denied: list[tuple[str, str]],
) -> None:
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "")
    token = _elevated_token(scopes=["chat", scope])
    for method, path in allowed:
        admin_auth.authorize_system(_request(path, method=method, token=token))
    for method, path in denied:
        with pytest.raises(HTTPException) as raised:
            admin_auth.authorize_system(_request(path, method=method, token=token))
        assert raised.value.status_code == 403, (method, path)


def test_host_only_operations_stay_loopback_even_with_every_grant(
    pairing_store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "")
    token = _elevated_token()
    for method, path in [
        ("POST", "/system/shutdown"),
        ("POST", "/system/stop-all"),
        ("DELETE", "/app-state"),
        ("POST", "/attachments/abc/open"),
        ("PUT", "/v1/settings/other"),
        ("POST", "/not-a-known-route"),
    ]:
        with pytest.raises(HTTPException) as raised:
            admin_auth.authorize_system(_request(path, method=method, token=token))
        assert raised.value.status_code == 403, (method, path)
    with pytest.raises(HTTPException) as yolo:
        admin_auth.authorize_scope(_request("/v1/agent", method="POST", token=token), "agent_yolo")
    assert yolo.value.status_code == 403


def test_admin_token_over_the_network_does_not_unlock_elevated_scopes(
    pairing_store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "root-secret")
    for path, method in [("/v1/agent", "POST"), ("/system/index-upload", "POST"), ("/v1/memory", "POST")]:
        with pytest.raises(HTTPException) as raised:
            admin_auth.authorize_system(_request(path, method=method, admin_token="root-secret"))
        assert raised.value.status_code == 403, path
    # The same operator on the host itself is unaffected.
    admin_auth.authorize_system(_request("/v1/agent", method="POST", client="127.0.0.1", admin_token="root-secret"))


def test_only_localhost_can_change_device_permissions(pairing_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import shared_runtime

    monkeypatch.setattr(shared_runtime, "initialize_runtime", lambda: None)
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "admin")
    app = create_app()
    with TestClient(app, client=("127.0.0.1", 50100)) as local:
        code = local.post("/v1/pairing/start", json={"scopes": ["chat", "agent"]}).json()["code"]
    with TestClient(app, client=("192.168.1.44", 50101)) as remote:
        claim = remote.post("/v1/pairing/claim", json={"code": code, "device_name": "Phone"})
        device = claim.json()["device"]
        assert device["scopes"] == ["chat", "agent"]
        cookie = {"Cookie": claim.headers["set-cookie"].split(";", 1)[0]}
        path = f"/v1/pairing/devices/{device['id']}"
        # The device itself, and a remote admin token, cannot escalate.
        assert remote.patch(path, json={"scopes": ALL_ELEVATED}, headers=cookie).status_code == 403
        assert remote.patch(path, json={"scopes": ALL_ELEVATED}, headers={"X-Admin-Token": "admin"}).status_code == 403
    with TestClient(app, client=("127.0.0.1", 50102)) as local:
        updated = local.patch(path, json={"scopes": ["chat", "index"]})
        assert updated.status_code == 200
        assert updated.json()["device"]["scopes"] == ["chat", "index"]
        assert local.patch(path, json={"scopes": ["system"]}).status_code == 422
        assert local.patch(path, json={"scopes": []}).status_code == 422
        assert local.patch(f"/v1/pairing/devices/{'f' * 24}", json={"scopes": ["chat"]}).status_code == 404
        assert [d["scopes"] for d in local.get("/v1/pairing/devices").json()["devices"]] == [["chat", "index"]]
    with TestClient(app, client=("192.168.1.44", 50103)) as remote:
        me = remote.get("/v1/pairing/me", headers=cookie)
        assert me.json()["device"]["scopes"] == ["chat", "index"]
