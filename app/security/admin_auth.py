"""Admin authentication and LAN access control for TrinaxAI system endpoints.

Extracted from rag_api.py to keep the authorization logic in one place.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import threading
import time
from pathlib import Path

from fastapi import HTTPException, Request

from app.security.device_auth import DEVICE_TOKEN_HEADER, authenticate_device_token

# ``app.main`` imports this module before the rest of the application imports
# ``config.py``.  Load the project environment here so the authorization
# settings in .env are available when these module-level values are created.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    # Keep the API usable in minimal installations; process environment values
    # are still honored when python-dotenv is not installed.
    pass

_LOCAL_HOSTS: set[str] = {"127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"}

_LAN_NETWORKS = tuple(
    ipaddress.ip_network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)

_PROXY_HEADER = "X-TrinaxAI-Proxy"
_PROXY_CLIENT_HEADER = "X-TrinaxAI-Client-IP"
_PROXY_TIMESTAMP_HEADER = "X-TrinaxAI-Proxy-Timestamp"
_PROXY_NONCE_HEADER = "X-TrinaxAI-Proxy-Nonce"
_PROXY_SIGNATURE_HEADER = "X-TrinaxAI-Proxy-Signature"
_PROXY_VERSION = "v1"
_PROXY_MAX_SKEW_SECONDS = 30
_PROXY_NONCE_CACHE_MAX = 65_536
_PROXY_SECRET: bytes | None = None
_PROXY_SEEN_NONCES: dict[str, int] = {}
_PROXY_NONCE_LOCK = threading.Lock()

SAFE_DEFAULT_ORIGINS = (
    "https://localhost:3334",
    "http://localhost:3334",
    "https://127.0.0.1:3334",
    "http://127.0.0.1:3334",
    "https://localhost:3335",
    "http://localhost:3335",
    "https://127.0.0.1:3335",
    "http://127.0.0.1:3335",
    "http://localhost:5173",
)

ADMIN_TOKEN: str = os.getenv("TRINAXAI_ADMIN_TOKEN", "")

ALLOW_LAN_SYSTEM: bool = os.getenv("TRINAXAI_ALLOW_LAN_SYSTEM", "0").strip().lower() not in {"0", "false", "no", "off"}


def _is_lan_client(host: str) -> bool:
    """Check if a host is loopback, link-local, RFC1918, or IPv6 ULA.

    ``ipaddress.ip_address(...).is_private`` is intentionally not used: Python
    also classifies documentation and unspecified ranges as private on some
    versions.  Those addresses must not gain LAN privileges.
    """
    try:
        ip = ipaddress.ip_address(host.removeprefix("::ffff:"))
    except ValueError:
        return host in _LOCAL_HOSTS
    return ip.is_loopback or ip.is_link_local or any(ip in network for network in _LAN_NETWORKS)


def _is_local_client(host: str) -> bool:
    """Check if a host is any loopback address."""
    try:
        ip = ipaddress.ip_address(host.removeprefix("::ffff:"))
    except ValueError:
        return host in {"localhost"}
    return ip.is_loopback


def _is_trusted_proxy_peer(host: str) -> bool:
    """Allow loopback or explicitly configured runtime peers for HMAC proxies."""
    if _is_local_client(host):
        return True
    configured = os.getenv("TRINAXAI_PROXY_TRUSTED_PEERS", "")
    try:
        peer = ipaddress.ip_address(host.removeprefix("::ffff:"))
    except ValueError:
        return False
    for raw_network in configured.split(","):
        try:
            if peer in ipaddress.ip_network(raw_network.strip(), strict=False):
                return True
        except ValueError:
            continue
    return False


def _immediate_client_host(request: Request) -> str:
    """Return the transport peer without trusting any client-supplied header."""
    if request.client and request.client.host:
        return request.client.host
    # Missing ASGI peer metadata is not evidence of localhost.  Failing closed
    # prevents synthetic/misconfigured gateways from gaining local privileges.
    return "unknown"


def _proxy_secret_path() -> Path:
    configured = os.getenv("TRINAXAI_PROXY_SECRET_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[2] / "storage" / ".proxy_secret"


def _load_proxy_secret() -> bytes:
    """Load the gateway-only HMAC key, creating a mode-0600 key if needed."""
    global _PROXY_SECRET
    if _PROXY_SECRET is not None:
        return _PROXY_SECRET

    configured = os.getenv("TRINAXAI_PROXY_SECRET", "").strip()
    if configured:
        _PROXY_SECRET = configured.encode("utf-8")
        return _PROXY_SECRET

    path = _proxy_secret_path()
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        value = ""
    except OSError:
        _PROXY_SECRET = b""
        return _PROXY_SECRET
    if value:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        _PROXY_SECRET = value.encode("utf-8")
        return _PROXY_SECRET

    generated = secrets.token_hex(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(generated)
        value = generated
    except FileExistsError:
        try:
            value = path.read_text(encoding="utf-8").strip()
            os.chmod(path, 0o600)
        except OSError:
            value = ""
    except OSError:
        value = ""
    _PROXY_SECRET = value.encode("utf-8") if value else b""
    return _PROXY_SECRET


def _proxy_payload(
    client_ip: str,
    timestamp: str,
    nonce: str,
    method: str,
    path: str,
) -> bytes:
    return "\n".join((_PROXY_VERSION, client_ip, timestamp, nonce, method.upper(), path)).encode("utf-8")


def _proxy_signature(
    secret: bytes | str,
    client_ip: str,
    timestamp: str,
    nonce: str,
    method: str,
    path: str,
) -> str:
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    return hmac.new(
        key,
        _proxy_payload(client_ip, timestamp, nonce, method, path),
        hashlib.sha256,
    ).hexdigest()


def _consume_proxy_nonce(nonce: str, stamp: int) -> None:
    """Accept a signed nonce once within the assertion freshness window."""
    now = int(time.time())
    with _PROXY_NONCE_LOCK:
        for used_nonce, expires_at in list(_PROXY_SEEN_NONCES.items()):
            if expires_at < now:
                _PROXY_SEEN_NONCES.pop(used_nonce, None)
        if nonce in _PROXY_SEEN_NONCES:
            raise HTTPException(status_code=403, detail="Replayed trusted-proxy identity.")
        if len(_PROXY_SEEN_NONCES) >= _PROXY_NONCE_CACHE_MAX:
            raise HTTPException(status_code=503, detail="Trusted-proxy replay cache is full.")
        _PROXY_SEEN_NONCES[nonce] = stamp + _PROXY_MAX_SKEW_SECONDS


def _verified_proxy_client(request: Request, immediate_host: str) -> str | None:
    """Return the signed original peer, or ``None`` for a direct request.

    Only the local Vite gateway or an explicitly configured runtime peer can
    assert an original address. Ordinary ``Forwarded``/``X-Forwarded-For``
    headers remain untrusted, and any partial or invalid TrinaxAI proxy
    assertion is rejected rather than ignored.
    """
    marker = request.headers.get(_PROXY_HEADER, "").strip()
    signed_headers = (
        _PROXY_CLIENT_HEADER,
        _PROXY_TIMESTAMP_HEADER,
        _PROXY_NONCE_HEADER,
        _PROXY_SIGNATURE_HEADER,
    )
    if not marker and not any(request.headers.get(name) for name in signed_headers):
        return None
    if marker != _PROXY_VERSION or not _is_trusted_proxy_peer(immediate_host):
        raise HTTPException(status_code=403, detail="Invalid trusted-proxy identity.")

    client_ip = request.headers.get(_PROXY_CLIENT_HEADER, "").strip().removeprefix("::ffff:")
    timestamp = request.headers.get(_PROXY_TIMESTAMP_HEADER, "").strip()
    nonce = request.headers.get(_PROXY_NONCE_HEADER, "").strip().lower()
    signature = request.headers.get(_PROXY_SIGNATURE_HEADER, "").strip().lower()
    try:
        ipaddress.ip_address(client_ip)
        stamp = int(timestamp)
    except (ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Invalid trusted-proxy identity.") from None
    if abs(int(time.time()) - stamp) > _PROXY_MAX_SKEW_SECONDS:
        raise HTTPException(status_code=403, detail="Expired trusted-proxy identity.")
    if not re.fullmatch(r"[0-9a-f]{32}", nonce) or not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise HTTPException(status_code=403, detail="Invalid trusted-proxy identity.")

    secret = _load_proxy_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Trusted proxy is not configured.")
    expected = _proxy_signature(
        secret,
        client_ip,
        timestamp,
        nonce,
        request.method,
        request.url.path,
    )
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Invalid trusted-proxy identity.")
    _consume_proxy_nonce(nonce, stamp)
    return client_ip


def _client_host(request: Request) -> str:
    """Return a verified original IP or the direct transport peer.

    The only forwarded identity accepted is the short-lived HMAC assertion
    emitted by TrinaxAI's local gateway.  Client-supplied X-Forwarded-For is
    never consulted.
    """
    cached = getattr(request.state, "trinaxai_verified_client", None)
    if isinstance(cached, str):
        return cached
    immediate = _immediate_client_host(request)
    client = _verified_proxy_client(request, immediate) or immediate
    request.state.trinaxai_verified_client = client
    return client


def _validate_browser_origin(request: Request) -> None:
    origin = request.headers.get("Origin", "").strip()
    if not origin:
        return
    allowed = {
        item.strip()
        for item in os.getenv("TRINAXAI_CORS_ORIGINS", ",".join(SAFE_DEFAULT_ORIGINS)).split(",")
        if item.strip()
    }
    pattern = os.getenv(
        "TRINAXAI_CORS_ORIGIN_REGEX",
        r"https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+):(3334|3335)",
    )
    if origin not in allowed and not re.fullmatch(pattern, origin):
        raise HTTPException(status_code=403, detail="Untrusted browser origin.")


def required_scopes_for_request(request: Request) -> tuple[str, ...]:
    """Map existing API paths to their least-privileged device scopes.

    Older service modules call :func:`authorize_system` internally. Keeping the
    mapping here lets those calls gain scoped device authorization without a
    risky all-at-once rewrite of every service function.
    """
    raw_path = getattr(request.url, "path", None)
    raw_method = getattr(request, "method", None)
    if not isinstance(raw_path, str) or not isinstance(raw_method, str):
        return ("system",)
    path = raw_path.rstrip("/") or "/"
    method = raw_method.upper()
    if path.startswith("/v1/agent"):
        return ("agent",)
    if path.startswith("/v1/watch") or path.startswith("/system/index"):
        return ("index",)
    if path.startswith("/system"):
        return ("system",)
    if path.startswith("/collections"):
        return ("read_private",) if method == "GET" else ("index",)
    if path.startswith("/v1/sources"):
        return ("index",) if method == "DELETE" else ("read_private",)
    if path.startswith(("/app-state", "/attachments", "/v1/memory", "/v1/stats")):
        return ("read_private",)
    if path.startswith("/v1/usage"):
        return ("chat",)
    if path.startswith(("/v1/chat", "/v1/research", "/v1/voice", "/documents")):
        return ("chat",)
    # Unknown callers of the legacy helper remain privileged and fail closed.
    return ("system",)


def _valid_admin_token(request: Request) -> bool:
    token = request.headers.get("X-Admin-Token", "")
    return bool(ADMIN_TOKEN and token and hmac.compare_digest(token, ADMIN_TOKEN))


def authorize_scope(
    request: Request,
    required_scope: str,
    *,
    allow_local: bool = True,
    allow_legacy_lan_system: bool = False,
) -> None:
    """Authorize one device scope, an administrator, or a safe local peer."""
    client_ip = _client_host(request)
    admin_token = request.headers.get("X-Admin-Token", "")
    device_token = request.headers.get(DEVICE_TOKEN_HEADER, "")

    _validate_browser_origin(request)
    if admin_token:
        if _valid_admin_token(request):
            request.state.trinaxai_identity = {"kind": "admin", "scopes": ["*"]}
            return
        raise HTTPException(status_code=403, detail="Invalid admin token.")
    if device_token:
        device = authenticate_device_token(device_token, required_scope)
        if device is not None:
            request.state.trinaxai_identity = {"kind": "device", **device}
            return
        # Web search is a low-risk scope available to any browser on the
        # owner's LAN.  A device token that lacks the "web" scope should
        # not block LAN access; fall through to the network checks below.
        if required_scope != "web":
            raise HTTPException(
                status_code=403,
                detail=f"Device credential does not grant the {required_scope} scope.",
            )
    if allow_local and _is_local_client(client_ip):
        request.state.trinaxai_identity = {"kind": "local", "scopes": ["*"]}
        return
    # Web-only research contains no private TrinaxAI data and is available to
    # browsers on the owner's LAN. The research service separately prevents
    # this scope from including the local knowledge index.
    if required_scope == "web" and _is_lan_client(client_ip):
        request.state.trinaxai_identity = {"kind": "lan", "scopes": ["web"]}
        return
    if (
        allow_legacy_lan_system
        and required_scope == "system"
        and not ADMIN_TOKEN
        and ALLOW_LAN_SYSTEM
        and _is_lan_client(client_ip)
    ):
        request.state.trinaxai_identity = {"kind": "legacy_lan", "scopes": ["system"]}
        return
    if ADMIN_TOKEN:
        detail = f"Remote access requires X-Admin-Token or a paired device with the {required_scope} scope."
    else:
        detail = f"Remote access requires a paired device with the {required_scope} scope."
    raise HTTPException(status_code=403, detail=detail)


def authorize_local_or_admin(request: Request) -> None:
    """Authorize sensitive pairing administration without accepting devices."""
    client_ip = _client_host(request)
    _validate_browser_origin(request)
    supplied = request.headers.get("X-Admin-Token", "")
    if supplied:
        if _valid_admin_token(request):
            return
        raise HTTPException(status_code=403, detail="Invalid admin token.")
    if _is_local_client(client_ip):
        return
    raise HTTPException(status_code=403, detail="Pairing administration is local or admin only.")


def require_scope(scope: str):
    """FastAPI dependency factory for routes that lacked legacy auth calls."""

    def dependency(request: Request) -> None:
        authorize_scope(request, scope)

    return dependency


def authorize_lan_or_scope(request: Request, scope: str) -> None:
    """Allow an unauthenticated LAN peer or an explicitly scoped identity.

    This is intentionally narrower than ``authorize_scope`` and is suitable
    only for stateless features that neither read nor persist private TrinaxAI
    data. Supplied credentials are still validated so an invalid/revoked token
    cannot silently fall back to anonymous LAN access.
    """
    if request.headers.get("X-Admin-Token") or request.headers.get(DEVICE_TOKEN_HEADER):
        authorize_scope(request, scope)
        return
    client_ip = _client_host(request)
    _validate_browser_origin(request)
    if not _is_lan_client(client_ip):
        raise HTTPException(
            status_code=403,
            detail="This feature is available without pairing only on the local network or VPN.",
        )
    request.state.trinaxai_identity = {"kind": "lan", "scopes": [scope]}


def require_lan_or_scope(scope: str):
    """FastAPI dependency for a stateless LAN feature with scoped fallback."""

    def dependency(request: Request) -> None:
        authorize_lan_or_scope(request, scope)

    return dependency


def authorize_system(request: Request) -> None:
    """Compatibility authorization using the request's least privilege.

    When ADMIN_TOKEN is set:
      - Requests with the correct X-Admin-Token header are allowed.
      - Localhost remains usable without a token.
      - Every non-local request must provide the token, even when LAN system
        access is enabled.

    When ADMIN_TOKEN is NOT set:
      - Localhost requests are always allowed.
      - LAN access is allowed only when TRINAXAI_ALLOW_LAN_SYSTEM is enabled.
    """
    required = required_scopes_for_request(request)
    for scope in required:
        authorize_scope(
            request,
            scope,
            allow_legacy_lan_system=scope == "system",
        )
