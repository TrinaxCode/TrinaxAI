from __future__ import annotations

from fastapi import HTTPException
from starlette.testclient import TestClient

from app.main import create_app
from app.services import health_service, shared_runtime


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


def test_readiness_fails_when_ollama_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(health_service, "_ollama_available_cached", lambda: False)

    with TestClient(create_app()) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["ok"] is False
    assert response.json()["ollama"] is False


def test_private_state_is_never_browser_cached() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/app-state")

    assert response.headers["cache-control"] == "no-store"


def test_unhandled_failures_are_logged_but_not_exposed(monkeypatch) -> None:
    monkeypatch.setattr(shared_runtime, "initialize_runtime", lambda: None)
    app = create_app()

    @app.get("/test-failure")
    def fail():
        raise RuntimeError("database password=secret at /home/service.py:42")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-failure", headers={"X-Request-ID": "failure-123"})

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "failure-123"
    body = response.json()
    assert body["detail"]["code"] == "ERR_INTERNAL_SERVER_ERROR"
    assert body["request_id"] == "failure-123"
    assert "password" not in response.text
    assert "RuntimeError" not in response.text
    assert "/home/" not in response.text


def test_server_http_errors_are_sanitized(monkeypatch) -> None:
    monkeypatch.setattr(shared_runtime, "initialize_runtime", lambda: None)
    app = create_app()

    @app.get("/test-http-failure")
    def fail():
        raise HTTPException(status_code=503, detail="ConnectionError: private upstream failed")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-http-failure")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ERR_EXTERNAL_SERVICE_UNAVAILABLE"
    assert "ConnectionError" not in response.text


def test_runtime_starts_when_optional_model_subsystems_fail(monkeypatch) -> None:
    def fail():
        raise RuntimeError("subsystem unavailable")

    monkeypatch.setattr(shared_runtime.config, "make_embed", fail)
    monkeypatch.setattr(shared_runtime.config, "make_reranker", fail)
    monkeypatch.setattr(shared_runtime, "build_engine", fail)

    shared_runtime.initialize_runtime()

    assert shared_runtime.state.reranker is None
