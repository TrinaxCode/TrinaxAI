"""Pairing and scoped device credentials for remote TrinaxAI clients.

The on-disk registry deliberately contains only keyed hashes. Pairing codes and
device bearer tokens are returned once and can never be recovered from the
registry. The small JSON document is replaced atomically with mode 0600 so the
Vite gateway can safely read a complete generation while FastAPI updates it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from trinaxai_core import exclusive_process_lock

SCHEMA_VERSION = 1
DEVICE_TOKEN_HEADER = "X-TrinaxAI-Device-Token"
ALL_DEVICE_SCOPES = frozenset({"chat", "read_private", "index", "system", "agent", "agent_yolo", "web"})
DEFAULT_DEVICE_SCOPES = ("chat", "read_private")
_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_CODE_LENGTH = 8
_TOKEN_RE = re.compile(r"^txd_([0-9a-f]{24})_([A-Za-z0-9_-]{40,})$")
_LOCK = threading.RLock()


class DeviceRegistryError(RuntimeError):
    """The credential registry could not be read or safely updated."""


def _registry_path() -> Path:
    configured = os.getenv("TRINAXAI_DEVICE_REGISTRY", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_absolute() else Path(__file__).resolve().parents[2] / candidate
    return Path(__file__).resolve().parents[2] / "storage" / "device_pairing.json"


def _secret_path() -> Path:
    configured = os.getenv("TRINAXAI_DEVICE_SECRET_FILE", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_absolute() else Path(__file__).resolve().parents[2] / candidate
    return Path(__file__).resolve().parents[2] / "storage" / ".device_secret"


def _ensure_private_secret(path: Path) -> bytes:
    existed = True
    try:
        value = path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        existed = False
        value = ""
    except OSError as exc:
        raise DeviceRegistryError("Device credential secret is unavailable.") from exc
    if value:
        try:
            raw = bytes.fromhex(value)
        except ValueError as exc:
            raise DeviceRegistryError("Device credential secret is invalid.") from exc
        if len(raw) < 32:
            raise DeviceRegistryError("Device credential secret is too short.")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return raw

    if existed:
        raise DeviceRegistryError("Device credential secret is empty.")

    generated = secrets.token_bytes(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(generated.hex())
            stream.flush()
            os.fsync(stream.fileno())
        return generated
    except FileExistsError:
        # Another process won the create race. It should have fsync'ed before
        # exposing the secret; retry once and fail closed if the file is empty.
        return _ensure_private_secret(path)
    except OSError as exc:
        raise DeviceRegistryError("Device credential secret could not be created.") from exc


def _empty_registry() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "devices": {}, "pairing_codes": {}}


def _read_registry(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _empty_registry()
    except (OSError, ValueError, TypeError) as exc:
        raise DeviceRegistryError("Device credential registry is invalid.") from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema_version") != SCHEMA_VERSION
        or not isinstance(raw.get("devices"), dict)
        or not isinstance(raw.get("pairing_codes"), dict)
    ):
        raise DeviceRegistryError("Unsupported device credential registry schema.")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return raw


def _write_registry(path: Path, registry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp")
    body = json.dumps(registry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise DeviceRegistryError("Device credential registry could not be saved.") from exc


def _keyed_hash(secret: bytes, purpose: str, value: str) -> str:
    return hmac.new(secret, f"{purpose}\0{value}".encode(), hashlib.sha256).hexdigest()


def _process_lock(path: Path):
    return exclusive_process_lock(
        path.with_name(f".{path.name}.lock"),
        timeout=10.0,
        poll_interval=0.02,
    )


def normalize_pairing_code(code: str) -> str:
    return "".join(character for character in str(code).upper() if character.isalnum())


def validate_scopes(scopes: Iterable[str] | None) -> tuple[str, ...]:
    source = DEFAULT_DEVICE_SCOPES if scopes is None else scopes
    requested = tuple(dict.fromkeys(str(scope).strip() for scope in source))
    if not requested or any(scope not in ALL_DEVICE_SCOPES for scope in requested):
        raise ValueError("Unknown or empty device scope set.")
    # Automatic execution is never useful without the ordinary agent scope.
    if "agent_yolo" in requested and "agent" not in requested:
        raise ValueError("agent_yolo requires the agent scope.")
    return requested


def sanitize_device_name(name: str) -> str:
    cleaned = " ".join(str(name).split()).strip()
    if not cleaned or len(cleaned) > 80 or any(ord(char) < 32 for char in cleaned):
        raise ValueError("Device name must contain 1-80 printable characters.")
    return cleaned


def _prune_codes(registry: dict[str, Any], now: float) -> bool:
    codes = registry["pairing_codes"]
    expired = [key for key, value in codes.items() if float(value.get("expires_at") or 0) <= now]
    for key in expired:
        codes.pop(key, None)
    return bool(expired)


def create_pairing_code(
    scopes: Iterable[str] | None = None,
    *,
    ttl_seconds: int = 300,
    device_ttl_days: int | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Create a short, single-use pairing code and return its clear value once."""
    active_scopes = validate_scopes(scopes)
    ttl = max(60, min(int(ttl_seconds), 900))
    if device_ttl_days is not None and not 1 <= int(device_ttl_days) <= 3650:
        raise ValueError("Device lifetime must be between 1 and 3650 days.")
    stamp = float(time.time() if now is None else now)
    secret = _ensure_private_secret(_secret_path())
    path = _registry_path()
    with _LOCK, _process_lock(path):
        registry = _read_registry(path)
        _prune_codes(registry, stamp)
        while True:
            raw_code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            code_hash = _keyed_hash(secret, "pairing-code", raw_code)
            if code_hash not in registry["pairing_codes"]:
                break
        expires_at = stamp + ttl
        registry["pairing_codes"][code_hash] = {
            "created_at": stamp,
            "expires_at": expires_at,
            "scopes": list(active_scopes),
            "device_ttl_days": int(device_ttl_days) if device_ttl_days is not None else None,
        }
        _write_registry(path, registry)
    display = f"{raw_code[:4]}-{raw_code[4:]}"
    return {"code": display, "expires_at": expires_at, "scopes": list(active_scopes)}


def claim_pairing_code(code: str, device_name: str, *, now: float | None = None) -> dict[str, Any]:
    """Consume a valid pairing code and issue one high-entropy device token."""
    normalized = normalize_pairing_code(code)
    if len(normalized) != _CODE_LENGTH or any(char not in _CODE_ALPHABET for char in normalized):
        raise PermissionError("Invalid or expired pairing code.")
    name = sanitize_device_name(device_name)
    stamp = float(time.time() if now is None else now)
    secret = _ensure_private_secret(_secret_path())
    code_hash = _keyed_hash(secret, "pairing-code", normalized)
    path = _registry_path()
    with _LOCK, _process_lock(path):
        registry = _read_registry(path)
        changed = _prune_codes(registry, stamp)
        record = registry["pairing_codes"].pop(code_hash, None)
        if not isinstance(record, dict) or float(record.get("expires_at") or 0) <= stamp:
            if changed or record is not None:
                _write_registry(path, registry)
            raise PermissionError("Invalid or expired pairing code.")

        device_id = secrets.token_hex(12)
        token = f"txd_{device_id}_{secrets.token_urlsafe(32)}"
        ttl_days = record.get("device_ttl_days")
        expires_at = stamp + int(ttl_days) * 86400 if ttl_days else None
        device = {
            "id": device_id,
            "name": name,
            "token_hash": _keyed_hash(secret, "device-token", token),
            "scopes": list(validate_scopes(record.get("scopes"))),
            "created_at": stamp,
            "last_seen_at": None,
            "expires_at": expires_at,
            "revoked_at": None,
        }
        registry["devices"][device_id] = device
        _write_registry(path, registry)
    return {"token": token, "device": public_device(device)}


def public_device(device: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(device.get("id") or ""),
        "name": str(device.get("name") or ""),
        "scopes": list(device.get("scopes") or []),
        "created_at": float(device.get("created_at") or 0),
        "last_seen_at": device.get("last_seen_at"),
        "expires_at": device.get("expires_at"),
        "revoked_at": device.get("revoked_at"),
    }


def authenticate_device_token(
    token: str,
    required_scope: str,
    *,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Return the matching active device if its token grants ``required_scope``."""
    if required_scope not in ALL_DEVICE_SCOPES:
        raise ValueError(f"Unknown device scope: {required_scope}")
    match = _TOKEN_RE.fullmatch(str(token).strip())
    if not match:
        return None
    device_id = match.group(1)
    stamp = float(time.time() if now is None else now)
    try:
        secret = _ensure_private_secret(_secret_path())
        path = _registry_path()
        with _LOCK, _process_lock(path):
            registry = _read_registry(path)
            device = registry["devices"].get(device_id)
            if not isinstance(device, dict):
                return None
            expected = str(device.get("token_hash") or "")
            actual = _keyed_hash(secret, "device-token", token)
            if not expected or not hmac.compare_digest(actual, expected):
                return None
            if device.get("revoked_at") is not None:
                return None
            expires_at = device.get("expires_at")
            if expires_at is not None and float(expires_at) <= stamp:
                return None
            if required_scope not in set(device.get("scopes") or []):
                return None
            last_seen = float(device.get("last_seen_at") or 0)
            if stamp - last_seen >= 300:
                device["last_seen_at"] = stamp
                _write_registry(path, registry)
            return public_device(device)
    except DeviceRegistryError:
        return None


def list_devices(*, include_revoked: bool = True) -> list[dict[str, Any]]:
    path = _registry_path()
    with _LOCK, _process_lock(path):
        registry = _read_registry(path)
        devices = [public_device(value) for value in registry["devices"].values()]
    if not include_revoked:
        devices = [device for device in devices if device["revoked_at"] is None]
    return sorted(devices, key=lambda item: (-item["created_at"], item["name"]))


def revoke_device(device_id: str, *, now: float | None = None) -> dict[str, Any] | None:
    if not re.fullmatch(r"[0-9a-f]{24}", str(device_id)):
        return None
    stamp = float(time.time() if now is None else now)
    path = _registry_path()
    with _LOCK, _process_lock(path):
        registry = _read_registry(path)
        device = registry["devices"].get(device_id)
        if not isinstance(device, dict):
            return None
        if device.get("revoked_at") is None:
            device["revoked_at"] = stamp
            _write_registry(path, registry)
        return public_device(device)


def device_for_token(token: str) -> dict[str, Any] | None:
    """Identify a device token without granting a scope (used by ``/me``)."""
    for scope in ALL_DEVICE_SCOPES:
        device = authenticate_device_token(token, scope)
        if device is not None:
            return device
    return None


__all__ = [
    "ALL_DEVICE_SCOPES",
    "DEFAULT_DEVICE_SCOPES",
    "DEVICE_TOKEN_HEADER",
    "DeviceRegistryError",
    "authenticate_device_token",
    "claim_pairing_code",
    "create_pairing_code",
    "device_for_token",
    "list_devices",
    "normalize_pairing_code",
    "revoke_device",
    "validate_scopes",
]
