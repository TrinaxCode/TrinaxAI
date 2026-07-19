"""Regression guards for the modular FastAPI architecture."""

from __future__ import annotations

import rag_api
from app.main import app
from app.services.engine_state import EngineState, state

EXPECTED_OPERATIONS = {
    ("GET", "/v1/voice/capabilities"),
    ("POST", "/v1/voice/stt"),
    ("POST", "/v1/voice/tts"),
    ("POST", "/v1/chat/completions"),
    ("POST", "/v1/agent"),
    ("POST", "/v1/agent/approve"),
    ("POST", "/v1/agent/cancel"),
    ("GET", "/v1/agent/browse"),
    ("GET", "/v1/sources"),
    ("GET", "/v1/sources/{collection}/{file}/chunks"),
    ("DELETE", "/v1/sources/{collection}/{file}"),
    ("DELETE", "/v1/sources/{collection}"),
    ("POST", "/v1/research"),
    ("POST", "/v1/research/preflight"),
    ("GET", "/v1/settings/web-search"),
    ("PUT", "/v1/settings/web-search"),
    ("DELETE", "/v1/settings/web-search"),
    ("POST", "/v1/settings/web-search/test"),
    ("DELETE", "/v1/settings/web-search/credentials/{provider}"),
    ("POST", "/v1/watch/start"),
    ("POST", "/v1/watch/stop"),
    ("GET", "/v1/watch/status"),
    ("GET", "/v1/memory"),
    ("POST", "/v1/memory"),
    ("DELETE", "/v1/memory/{memory_id}"),
    ("PATCH", "/v1/memory/{memory_id}"),
    ("POST", "/v1/memory/refresh"),
    ("POST", "/v1/memory/context"),
    ("GET", "/v1/memory/summary"),
    ("POST", "/v1/pairing/start"),
    ("POST", "/v1/pairing/claim"),
    ("GET", "/v1/pairing/devices"),
    ("DELETE", "/v1/pairing/devices/{device_id}"),
    ("GET", "/v1/pairing/me"),
    ("DELETE", "/v1/pairing/me"),
    ("POST", "/v1/usage"),
    ("GET", "/v1/stats"),
    ("GET", "/health"),
    ("GET", "/resources"),
    ("GET", "/app-state"),
    ("PUT", "/app-state"),
    ("DELETE", "/app-state"),
    ("POST", "/attachments"),
    ("GET", "/attachments/{attachment_id}"),
    ("DELETE", "/attachments/{attachment_id}"),
    ("POST", "/documents/extract"),
    ("GET", "/collections"),
    ("POST", "/collections"),
    ("PATCH", "/collections/{collection_id}"),
    ("DELETE", "/collections/{collection_id}"),
    ("POST", "/system/shutdown"),
    ("POST", "/system/startup"),
    ("POST", "/system/stop-all"),
    ("POST", "/system/reload"),
    ("POST", "/system/index-upload"),
    ("DELETE", "/system/index-imports"),
    ("GET", "/system/index-jobs/{job_id}"),
    ("POST", "/system/index-jobs/{job_id}/cancel"),
    ("POST", "/system/index-jobs/{job_id}/retry"),
    ("POST", "/system/self-test"),
}


def test_canonical_and_compatibility_apps_are_identical() -> None:
    assert rag_api.app is app


def test_openapi_operation_contract_has_no_missing_or_duplicate_routes() -> None:
    operations = {
        (method.upper(), path) for path, definition in app.openapi()["paths"].items() for method in definition
    }
    assert operations == EXPECTED_OPERATIONS


def test_engine_state_instances_do_not_share_mutable_defaults() -> None:
    first = EngineState()
    second = EngineState()
    first.known_projects.append("first")
    first.retrieval_cache[("query",)] = (1.0, [])
    assert second.known_projects == []
    assert second.retrieval_cache == {}
    assert first.engine_lock is not second.engine_lock


def test_legacy_state_alias_points_to_canonical_state(monkeypatch) -> None:
    marker = object()
    monkeypatch.setattr(rag_api, "_fusion_retriever", marker)
    assert state.fusion_retriever is marker
    assert rag_api._fusion_retriever is marker
