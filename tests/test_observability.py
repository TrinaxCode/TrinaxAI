from __future__ import annotations

from starlette.testclient import TestClient

from app.main import create_app


def test_api_responses_have_correlation_timing_and_security_headers() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"X-Request-ID": "audit-123"})

    assert response.headers["x-request-id"] == "audit-123"
    assert response.headers["server-timing"].startswith("app;dur=")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_invalid_correlation_id_is_replaced() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"X-Request-ID": "bad id value"})

    request_id = response.headers["x-request-id"]
    assert request_id != "bad id value"
    assert len(request_id) == 32


def test_private_state_is_never_browser_cached() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/app-state")

    assert response.headers["cache-control"] == "no-store"
