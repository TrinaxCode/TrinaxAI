"""Device pairing, inventory, and revocation endpoints."""

from __future__ import annotations

import threading
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.security.admin_auth import (
    DEVICE_TOKEN_COOKIE,
    DEVICE_TOKEN_COOKIE_PATH,
    _client_host,
    _device_token,
    _is_lan_client,
    _is_local_client,
    authorize_scope,
)
from app.security.device_auth import (
    ALL_DEVICE_SCOPES,
    DEVICE_TOKEN_HEADER,
    DeviceRegistryError,
    claim_pairing_code,
    create_pairing_code,
    device_for_token,
    list_devices,
    revoke_device,
    validate_device_token,
)

router = APIRouter(prefix="/v1/pairing", tags=["pairing"])
_CLAIM_LOCK = threading.Lock()
_CLAIM_WINDOWS: dict[str, list[float]] = {}
_CLAIM_LIMIT = 5
_CLAIM_WINDOW_SECONDS = 300.0


class PairingStartRequest(BaseModel):
    scopes: list[str] = Field(default_factory=lambda: ["chat", "read_private"], max_length=6)
    ttl_seconds: int = Field(default=300, ge=60, le=900)
    device_ttl_days: int | None = Field(default=None, ge=1, le=3650)


class PairingClaimRequest(BaseModel):
    code: str = Field(min_length=8, max_length=16)
    device_name: str = Field(min_length=1, max_length=80)


def _cookie_secure(request: Request) -> bool:
    if request.url.scheme.lower() == "https":
        return True
    return (
        request.headers.get("X-TrinaxAI-Proxy") == "v1"
        and request.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower() == "https"
    )


def _set_device_cookie(response: Response, request: Request, token: str, expires_at: object = None) -> None:
    safe_token = validate_device_token(token)
    if safe_token is None:
        raise ValueError("Invalid device credential.")
    max_age = None
    if expires_at is not None:
        try:
            max_age = max(0, int(float(expires_at) - time.time()))
        except (TypeError, ValueError):
            max_age = None
    response.set_cookie(
        key=DEVICE_TOKEN_COOKIE,
        value=safe_token,
        max_age=max_age,
        path=DEVICE_TOKEN_COOKIE_PATH,
        secure=_cookie_secure(request),
        httponly=True,
        samesite="strict",
    )


def _clear_device_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=DEVICE_TOKEN_COOKIE,
        path=DEVICE_TOKEN_COOKIE_PATH,
        secure=_cookie_secure(request),
        httponly=True,
        samesite="strict",
    )


def _enforce_claim_rate_limit(request: Request) -> None:
    key = _client_host(request)
    now = time.monotonic()
    with _CLAIM_LOCK:
        active = [stamp for stamp in _CLAIM_WINDOWS.get(key, []) if now - stamp < _CLAIM_WINDOW_SECONDS]
        if len(active) >= _CLAIM_LIMIT:
            _CLAIM_WINDOWS[key] = active
            raise HTTPException(
                status_code=429,
                detail="Too many pairing attempts. Wait before trying again.",
                headers={"Retry-After": str(int(_CLAIM_WINDOW_SECONDS))},
            )
        active.append(now)
        _CLAIM_WINDOWS[key] = active
        if len(_CLAIM_WINDOWS) > 2000:
            stale = [
                host
                for host, stamps in _CLAIM_WINDOWS.items()
                if not stamps or now - stamps[-1] >= _CLAIM_WINDOW_SECONDS
            ]
            for host in stale:
                _CLAIM_WINDOWS.pop(host, None)


@router.post("/start")
async def pairing_start(req: PairingStartRequest, request: Request):
    """Create a one-time code from the verified localhost host only."""
    if not _is_local_client(_client_host(request)):
        raise HTTPException(status_code=403, detail="Only the localhost host can generate pairing codes.")
    authorize_scope(request, "system")
    try:
        result = create_pairing_code(
            req.scopes,
            ttl_seconds=req.ttl_seconds,
            device_ttl_days=req.device_ttl_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Pairing settings are invalid.") from exc
    except DeviceRegistryError as exc:
        raise HTTPException(status_code=503, detail="Pairing storage is unavailable. Try again shortly.") from exc
    return {"ok": True, **result, "available_scopes": sorted(ALL_DEVICE_SCOPES)}


@router.post("/claim")
async def pairing_claim(req: PairingClaimRequest, request: Request, response: Response = None):
    """Consume a short code and deliver the device credential in an HttpOnly cookie."""
    response = response or Response()
    client_ip = _client_host(request)
    if not _is_lan_client(client_ip):
        raise HTTPException(status_code=403, detail="Device pairing is only available on the local network or VPN.")
    _enforce_claim_rate_limit(request)
    try:
        result = claim_pairing_code(req.code, req.device_name)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="The pairing code is invalid or expired.") from exc
    except DeviceRegistryError as exc:
        raise HTTPException(status_code=503, detail="Pairing storage is unavailable. Try again shortly.") from exc
    _set_device_cookie(response, request, result["token"], result["device"].get("expires_at"))
    return {"ok": True, "device": result["device"]}


@router.get("/devices")
async def pairing_devices(request: Request):
    authorize_scope(request, "system")
    try:
        return {"ok": True, "devices": list_devices()}
    except DeviceRegistryError as exc:
        raise HTTPException(status_code=503, detail="Pairing storage is unavailable. Try again shortly.") from exc


@router.delete("/devices/{device_id}")
async def pairing_revoke(device_id: str, request: Request):
    authorize_scope(request, "system")
    try:
        device = revoke_device(device_id)
    except DeviceRegistryError as exc:
        raise HTTPException(status_code=503, detail="Pairing storage is unavailable. Try again shortly.") from exc
    if device is None:
        raise HTTPException(status_code=404, detail="Unknown device.")
    return {"ok": True, "device": device}


@router.get("/me")
async def pairing_me(request: Request, response: Response = None):
    response = response or Response()
    token = _device_token(request)
    device = device_for_token(token) if token else None
    if device is None:
        raise HTTPException(status_code=403, detail="A valid device credential is required.")
    _client_host(request)
    if request.headers.get(DEVICE_TOKEN_HEADER, "").strip():
        _set_device_cookie(response, request, token, device.get("expires_at"))
    return {"ok": True, "device": device}


@router.delete("/me")
async def pairing_revoke_me(request: Request, response: Response = None):
    response = response or Response()
    token = _device_token(request)
    device = device_for_token(token) if token else None
    if device is None:
        raise HTTPException(status_code=403, detail="A valid device credential is required.")
    _client_host(request)
    revoked = revoke_device(device["id"])
    _clear_device_cookie(response, request)
    return {"ok": True, "device": revoked}


__all__ = ["router"]
