import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import web_search_settings_service as settings


def _isolated(monkeypatch, tmp_path, *, authorize=True):
    path = tmp_path / "web_search_settings.json"
    monkeypatch.setattr(settings, "_PATH", path)
    for name in settings._ENV.values():
        monkeypatch.delenv(name, raising=False)
    if authorize:
        monkeypatch.setattr(settings, "authorize_system", lambda _request: None)
    return path


def test_settings_persist_without_exposing_secret(monkeypatch, tmp_path):
    path = _isolated(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.put(
            "/v1/settings/web-search",
            json={"preferred_provider": "brave", "brave_api_key": "test-secret-value"},
        )
        assert response.status_code == 200
        assert response.json()["providers"]["brave"]["configured"] is True
        assert "test-secret-value" not in response.text
        assert "test-secret-value" not in client.get("/v1/settings/web-search").text
    assert json.loads(path.read_text())["brave_api_key"] == "test-secret-value"
    assert path.stat().st_mode & 0o777 == 0o600


def test_empty_key_does_not_delete_and_delete_is_explicit(monkeypatch, tmp_path):
    _isolated(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put("/v1/settings/web-search", json={"brave_api_key": "kept"})
        assert client.put("/v1/settings/web-search", json={"brave_api_key": ""}).json()["providers"]["brave"][
            "configured"
        ]
        response = client.delete("/v1/settings/web-search/credentials/brave")
        assert response.status_code == 200
        assert response.json()["providers"]["brave"]["configured"] is False


def test_reset_removes_only_managed_search_settings(monkeypatch, tmp_path):
    path = _isolated(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put("/v1/settings/web-search", json={"preferred_provider": "brave", "brave_api_key": "temporary"})
        response = client.delete("/v1/settings/web-search")
    assert response.status_code == 200
    assert response.json()["source"] == "default"
    assert not path.exists()


def test_provider_validation_and_environment_precedence(monkeypatch, tmp_path):
    _isolated(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.put("/v1/settings/web-search", json={"preferred_provider": "unknown"}).status_code == 422
        client.put("/v1/settings/web-search", json={"preferred_provider": "duckduckgo"})
        monkeypatch.setenv("TRINAXAI_WEB_SEARCH_PROVIDER", "brave")
        monkeypatch.setenv("TRINAXAI_BRAVE_SEARCH_API_KEY", "environment-secret")
        data = client.get("/v1/settings/web-search").json()
        assert data["preferred_provider"] == "brave"
        assert data["source"] == "environment"
        assert "environment-secret" not in json.dumps(data)


@pytest.mark.parametrize("field", ["enabled", "preferred_provider", "brave_api_key", "searxng_url"])
def test_settings_reject_explicit_null(monkeypatch, tmp_path, field):
    _isolated(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.put("/v1/settings/web-search", json={field: None})
    assert response.status_code == 422


def test_searxng_rejects_private_target(monkeypatch, tmp_path):
    _isolated(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.put("/v1/settings/web-search", json={"searxng_url": "http://127.0.0.1"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_searxng_url"


def test_connection_uses_selected_provider(monkeypatch, tmp_path):
    _isolated(monkeypatch, tmp_path)
    observed = {}

    settings._apply()
    original = settings.config.WEB_SEARCH_PROVIDER

    def fake_search(query, limit, *, provider=None):
        observed.update(query=query, limit=limit, provider=provider)
        return ([{"title": "Python", "url": "https://python.org", "snippet": "Python"}], "duckduckgo")

    monkeypatch.setattr(settings.web_search_service, "search_web", fake_search)
    with TestClient(app) as client:
        response = client.post("/v1/settings/web-search/test", json={"provider": "duckduckgo"})
    assert response.json() == {"ok": True, "provider": "duckduckgo", "result_count": 1}
    assert observed == {"query": "Python programming language", "limit": 1, "provider": "duckduckgo"}
    assert settings.config.WEB_SEARCH_PROVIDER == original


def test_concurrent_updates_are_serialized(monkeypatch, tmp_path):
    path = _isolated(monkeypatch, tmp_path)
    original_read = settings._read
    active = maximum = 0
    guard = threading.Lock()

    def slow_read():
        nonlocal active, maximum
        with guard:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.02)
        try:
            return original_read()
        finally:
            with guard:
                active -= 1

    monkeypatch.setattr(settings, "_read", slow_read)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda payload: client.put("/v1/settings/web-search", json=payload),
                [
                    {"preferred_provider": "brave"},
                    {"brave_api_key": "kept"},
                ],
            )
        )
    assert all(response.status_code == 200 for response in responses)
    assert maximum == 1
    assert json.loads(path.read_text()) == {"preferred_provider": "brave", "brave_api_key": "kept"}


def test_remote_device_without_system_scope_is_rejected(monkeypatch, tmp_path):
    _isolated(monkeypatch, tmp_path, authorize=False)
    with TestClient(app, client=("203.0.113.10", 1234)) as client:
        response = client.get("/v1/settings/web-search")
    assert response.status_code == 403
