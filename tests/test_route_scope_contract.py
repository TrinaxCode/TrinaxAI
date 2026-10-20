"""Contract: every HTTP route has an intentional, reviewed device scope.

``required_scopes_for_request`` maps URL prefixes to scopes, which is brittle on
its own: a new route under an unexpected prefix silently inherits whatever the
prefix table returns. This test pins the scope of every registered route so that
adding, moving or re-scoping an endpoint is an explicit, reviewed change.

Scope meanings: ``system`` is host-only (loopback); ``agent``, ``index`` and
``modify`` are grantable per paired device; ``chat`` and ``read_private`` are
the baseline remote scopes.
"""

from __future__ import annotations

from starlette.requests import Request

from app.routes import ROUTERS
from app.security.admin_auth import required_scopes_for_request

KNOWN_SCOPES = {"chat", "read_private", "index", "modify", "agent", "system"}

# (method, path) -> first required scope, as reviewed on 2026-10-19.
# /health, /ready, /resources and /v1/pairing/* enforce their own policy in the
# handler (public health probes; pairing uses authorize_scope directly), so the
# prefix-derived "system" below is the safe fallback, not the applied policy.
EXPECTED_SCOPES: dict[tuple[str, str], str] = {
    ("DELETE", "/app-state"): "system",
    ("GET", "/app-state"): "read_private",
    ("PUT", "/app-state"): "read_private",
    ("POST", "/attachments"): "read_private",
    ("DELETE", "/attachments/{attachment_id}"): "modify",
    ("GET", "/attachments/{attachment_id}"): "read_private",
    ("POST", "/attachments/{attachment_id}/open"): "system",
    ("GET", "/collections"): "read_private",
    ("POST", "/collections"): "index",
    ("DELETE", "/collections/{collection_id}"): "index",
    ("PATCH", "/collections/{collection_id}"): "index",
    ("POST", "/documents/extract"): "chat",
    ("GET", "/health"): "system",
    ("GET", "/ready"): "system",
    ("GET", "/resources"): "system",
    ("DELETE", "/system/index-imports"): "index",
    ("GET", "/system/index-jobs/{job_id}"): "index",
    ("POST", "/system/index-jobs/{job_id}/cancel"): "index",
    ("POST", "/system/index-jobs/{job_id}/retry"): "index",
    ("POST", "/system/index-upload"): "index",
    ("POST", "/system/reload"): "system",
    ("POST", "/system/self-test"): "system",
    ("POST", "/system/shutdown"): "system",
    ("POST", "/system/startup"): "system",
    ("POST", "/system/stop-all"): "system",
    ("POST", "/v1/agent"): "agent",
    ("POST", "/v1/agent/approve"): "agent",
    ("GET", "/v1/agent/browse"): "agent",
    ("POST", "/v1/agent/cancel"): "agent",
    ("POST", "/v1/chat/completions"): "chat",
    ("GET", "/v1/memory"): "read_private",
    ("POST", "/v1/memory"): "modify",
    ("POST", "/v1/memory/context"): "read_private",
    ("POST", "/v1/memory/refresh"): "modify",
    ("GET", "/v1/memory/summary"): "read_private",
    ("DELETE", "/v1/memory/{memory_id}"): "modify",
    ("PATCH", "/v1/memory/{memory_id}"): "modify",
    ("POST", "/v1/pairing/claim"): "system",
    ("GET", "/v1/pairing/devices"): "system",
    ("DELETE", "/v1/pairing/devices/{device_id}"): "system",
    ("PATCH", "/v1/pairing/devices/{device_id}"): "system",
    ("DELETE", "/v1/pairing/me"): "system",
    ("GET", "/v1/pairing/me"): "system",
    ("POST", "/v1/pairing/new-device"): "system",
    ("POST", "/v1/pairing/start"): "system",
    ("POST", "/v1/research"): "chat",
    ("POST", "/v1/research/preflight"): "chat",
    ("DELETE", "/v1/settings/web-search"): "modify",
    ("GET", "/v1/settings/web-search"): "modify",
    ("PUT", "/v1/settings/web-search"): "modify",
    ("DELETE", "/v1/settings/web-search/credentials/{provider}"): "modify",
    ("POST", "/v1/settings/web-search/test"): "modify",
    ("GET", "/v1/sources"): "read_private",
    ("DELETE", "/v1/sources/{collection}"): "index",
    ("DELETE", "/v1/sources/{collection}/{file:path}"): "index",
    ("GET", "/v1/sources/{collection}/{file:path}/chunks"): "read_private",
    ("GET", "/v1/stats"): "read_private",
    ("POST", "/v1/usage"): "chat",
    ("GET", "/v1/voice/capabilities"): "chat",
    ("POST", "/v1/voice/stt"): "chat",
    ("POST", "/v1/voice/tts"): "chat",
    ("POST", "/v1/watch/start"): "index",
    ("GET", "/v1/watch/status"): "index",
    ("POST", "/v1/watch/stop"): "index",
}


def _registered_routes() -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for router in ROUTERS
        for route in router.routes
        for method in route.methods - {"HEAD", "OPTIONS"}
    }


def _derived(method: str, path: str) -> tuple[str, ...]:
    request = Request({"type": "http", "method": method, "path": path, "headers": [], "query_string": b""})
    return required_scopes_for_request(request)


def test_every_route_has_a_reviewed_scope_and_no_stale_entries() -> None:
    registered = _registered_routes()
    missing = sorted(registered - set(EXPECTED_SCOPES))
    stale = sorted(set(EXPECTED_SCOPES) - registered)
    assert not missing, f"New routes need a reviewed entry in EXPECTED_SCOPES: {missing}"
    assert not stale, f"EXPECTED_SCOPES lists routes that no longer exist: {stale}"


def test_prefix_mapping_matches_the_reviewed_scope_of_each_route() -> None:
    mismatches = {
        key: (EXPECTED_SCOPES[key], _derived(*key))
        for key in sorted(_registered_routes() & set(EXPECTED_SCOPES))
        if _derived(*key) != (EXPECTED_SCOPES[key],)
    }
    assert not mismatches, f"Scope drift (expected, derived): {mismatches}"


def test_only_known_scopes_are_used_and_host_only_routes_stay_system() -> None:
    assert set(EXPECTED_SCOPES.values()) <= KNOWN_SCOPES
    for method, path in (
        ("POST", "/system/shutdown"),
        ("POST", "/system/stop-all"),
        ("POST", "/system/startup"),
        ("DELETE", "/app-state"),
        ("POST", "/attachments/{attachment_id}/open"),
    ):
        assert EXPECTED_SCOPES[(method, path)] == "system", (method, path)


def test_unknown_paths_fail_closed_to_system() -> None:
    assert _derived("GET", "/v1/not-a-real-route") == ("system",)
    assert _derived("POST", "/system-extra") == ("system",)
