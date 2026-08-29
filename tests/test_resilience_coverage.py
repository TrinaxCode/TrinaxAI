from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException, UploadFile
from starlette.requests import Request

from app.generation import validate as generation_validate
from app.routes import pairing
from app.schemas import AppStateRequest, IndexImportDeleteRequest
from app.schemas.api import WebSearchConnectionTest
from app.security import admin_auth, device_auth, rate_limit
from app.services import (
    agent_service,
    app_state_service,
    health_service,
    rag_service,
    shared_runtime,
    system_service,
    watcher_service,
)
from app.services import web_search_settings_service as settings
from app.services.engine_state import state
from trinaxai_cli import app as cli_app
from trinaxai_cli import branding
from trinaxai_cli import ui as cli_ui
from trinaxai_cli.commands import _lifecycle, ask
from trinaxai_cli.commands import index as index_command
from trinaxai_cli.session import Session


def _request(client: str = "127.0.0.1", headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "scheme": "http",
        "server": ("localhost", 3333),
        "client": (client, 50000),
        "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_pairing_route_failures_are_typed_and_rate_limit_prunes(monkeypatch) -> None:
    request = _request()
    monkeypatch.setattr(pairing, "authorize_scope", lambda *_args: None)
    monkeypatch.setattr(
        pairing, "create_pairing_code", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad"))
    )
    with pytest.raises(HTTPException) as exc:
        await pairing.pairing_start(pairing.PairingStartRequest(), request)
    assert exc.value.status_code == 422

    monkeypatch.setattr(
        pairing,
        "create_pairing_code",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(pairing.DeviceRegistryError("store unavailable")),
    )
    with pytest.raises(HTTPException) as exc:
        await pairing.pairing_start(pairing.PairingStartRequest(), request)
    assert exc.value.status_code == 503

    monkeypatch.setattr(pairing, "_is_lan_client", lambda _ip: False)
    with pytest.raises(HTTPException) as exc:
        await pairing.pairing_claim(pairing.PairingClaimRequest(code="ABCDEFGH", device_name="Phone"), request)
    assert exc.value.status_code == 403

    monkeypatch.setattr(pairing, "_is_lan_client", lambda _ip: True)
    enforce_rate_limit = pairing._enforce_claim_rate_limit
    monkeypatch.setattr(pairing, "_enforce_claim_rate_limit", lambda _request: None)
    monkeypatch.setattr(
        pairing, "claim_pairing_code", lambda *_args: (_ for _ in ()).throw(PermissionError("bad code"))
    )
    with pytest.raises(HTTPException) as exc:
        await pairing.pairing_claim(pairing.PairingClaimRequest(code="ABCDEFGH", device_name="Phone"), request)
    assert exc.value.status_code == 403
    monkeypatch.setattr(
        pairing,
        "claim_pairing_code",
        lambda *_args: (_ for _ in ()).throw(pairing.DeviceRegistryError("store unavailable")),
    )
    with pytest.raises(HTTPException) as exc:
        await pairing.pairing_claim(pairing.PairingClaimRequest(code="ABCDEFGH", device_name="Phone"), request)
    assert exc.value.status_code == 503

    monkeypatch.setattr(pairing, "_CLAIM_LIMIT", 1)
    pairing._CLAIM_WINDOWS.clear()
    pairing._CLAIM_WINDOWS.update({f"stale-{i}": [0.0] for i in range(2001)})
    monkeypatch.setattr(pairing.time, "monotonic", lambda: pairing._CLAIM_WINDOW_SECONDS + 1)
    enforce_rate_limit(request)
    assert not any(key.startswith("stale-") for key in pairing._CLAIM_WINDOWS)


@pytest.mark.asyncio
async def test_pairing_inventory_and_device_routes_handle_missing_and_storage_errors(monkeypatch) -> None:
    request = _request()
    monkeypatch.setattr(pairing, "authorize_scope", lambda *_args: None)
    monkeypatch.setattr(pairing, "list_devices", lambda: [{"id": "one"}])
    assert await pairing.pairing_devices(request) == {"ok": True, "devices": [{"id": "one"}]}
    monkeypatch.setattr(pairing, "list_devices", lambda: (_ for _ in ()).throw(pairing.DeviceRegistryError("down")))
    with pytest.raises(HTTPException) as exc:
        await pairing.pairing_devices(request)
    assert exc.value.status_code == 503

    monkeypatch.setattr(pairing, "revoke_device", lambda _device: None)
    with pytest.raises(HTTPException) as exc:
        await pairing.pairing_revoke("missing", request)
    assert exc.value.status_code == 404
    monkeypatch.setattr(
        pairing, "revoke_device", lambda _device: (_ for _ in ()).throw(pairing.DeviceRegistryError("down"))
    )
    with pytest.raises(HTTPException) as exc:
        await pairing.pairing_revoke("one", request)
    assert exc.value.status_code == 503

    with pytest.raises(HTTPException) as exc:
        await pairing.pairing_me(_request(headers={}))
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        await pairing.pairing_revoke_me(_request(headers={}))
    assert exc.value.status_code == 403
    monkeypatch.setattr(pairing, "device_for_token", lambda _token: {"id": "one"})
    monkeypatch.setattr(pairing, "revoke_device", lambda _device: {"id": "one", "revoked_at": 1})
    token = "txd_" + "a" * 24 + "_" + "b" * 40
    assert (await pairing.pairing_me(_request(headers={pairing.DEVICE_TOKEN_HEADER: token})))["device"]["id"] == "one"
    assert (await pairing.pairing_revoke_me(_request(headers={pairing.DEVICE_TOKEN_HEADER: token})))["device"][
        "revoked_at"
    ] == 1


def test_app_state_validation_and_atomic_write_edges(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    monkeypatch.setattr(app_state_service, "APP_STATE_PATH", str(path))
    assert app_state_service._clean_app_state_values(["bad"]) == {}
    path.write_text(json.dumps({"schema_version": 2, "revision": -1, "values": {"tc-a": "ok", "bad": "x"}}))
    document, legacy = app_state_service._read_app_state_document()
    assert not legacy and document["revision"] == 0 and document["values"] == {"tc-a": "ok"}
    path.write_text("[]")
    assert app_state_service._read_app_state_document()[1] is True
    assert app_state_service._if_match_revision(_request(headers={"If-Match": "17"})) == 17
    assert app_state_service._if_match_revision(_request(headers={"If-Match": 'W/"trinaxai-app-state-v2-3"'})) == 3
    with pytest.raises(HTTPException) as exc:
        app_state_service._if_match_revision(_request(headers={"If-Match": "bad"}))
    assert exc.value.status_code == 400
    monkeypatch.setattr(app_state_service, "APP_STATE_MAX_BYTES", 10)
    with pytest.raises(HTTPException) as exc:
        app_state_service._write_app_state_document({"revision": 1, "values": {"tc-a": "x"}})
    assert exc.value.status_code == 413


def test_rate_limiter_prunes_stale_clients_and_evicts_oldest(monkeypatch) -> None:
    monkeypatch.setattr(rate_limit.state, "rate_limit_clients", {})
    monkeypatch.setattr(rate_limit.state, "rate_limit_last_prune", 0.0)
    monkeypatch.setattr(rate_limit, "_RATE_LIMIT_MAX_CLIENTS", 1)
    monkeypatch.setattr(rate_limit, "_RATE_LIMIT_WINDOW", 10.0)
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 100.0)

    rate_limit.state.rate_limit_clients["stale"] = (1.0, 0.0)
    assert rate_limit._check_rate_limit("fresh") is True
    assert "stale" not in rate_limit.state.rate_limit_clients

    rate_limit.state.rate_limit_clients.clear()
    rate_limit.state.rate_limit_clients["oldest"] = (1.0, 99.0)
    assert rate_limit._check_rate_limit("new") is True
    assert "oldest" not in rate_limit.state.rate_limit_clients
    assert "new" in rate_limit.get_rate_limit_state()


def test_output_validation_catches_language_specific_incomplete_results() -> None:
    assert generation_validate._check_python("def broken(:")
    assert generation_validate._check_python("def incomplete():\n    ...")
    masked = generation_validate._mask_js_literals(
        "const text = 'quo\\'ted'; const template = `value`; // comment\nconst pattern = /a\\//; /* block */"
    )
    assert "quoted" not in masked and "comment" not in masked
    assert "placeholder" in generation_validate._check_js_ts("rest of code")[0]
    assert "errors:" in generation_validate.ValidationResult(False, errors=["broken"]).summary()
    assert generation_validate._check_balanced_pairs(")", "JS")
    assert generation_validate._check_balanced_pairs("(", "JS")
    assert generation_validate._check_html("<html><body>missing", True)
    assert generation_validate._check_css(".card { color: red;", True)


@pytest.mark.asyncio
async def test_app_state_put_and_delete_reject_bad_cas_and_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(app_state_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(app_state_service, "_read_app_state_document", lambda: ({"revision": 2, "values": {}}, False))
    with pytest.raises(HTTPException) as exc:
        await app_state_service.app_state_put(
            AppStateRequest(base_revision=1, operations=[]),
            _request(headers={"If-Match": '"trinaxai-app-state-v2-2"'}),
        )
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException) as exc:
        await app_state_service.app_state_delete(_request())
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_app_state_delete_success_and_directory_sync_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app_state_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(
        app_state_service,
        "_factory_reset_runtime_state",
        lambda _values: {"removed": [], "indexed": False, "collections": []},
    )
    monkeypatch.setattr(app_state_service, "_read_app_state_document", lambda: ({"revision": 4, "values": {}}, False))
    result = await app_state_service.app_state_delete(_request(headers={"X-TrinaxAI-Confirm": "reset-app-state"}))
    assert result["ok"] and result["revision"] == 4

    path = tmp_path / "state.json"
    monkeypatch.setattr(app_state_service, "APP_STATE_PATH", str(path))

    original_open = app_state_service.os.open

    def fail_directory_fsync(candidate, *args, **kwargs):
        if candidate == str(path.parent):
            raise OSError("unsupported")
        return original_open(candidate, *args, **kwargs)

    monkeypatch.setattr(
        app_state_service.os,
        "open",
        fail_directory_fsync,
    )
    app_state_service._write_app_state_document({"revision": 1, "values": {"tc-mode": "offline"}})
    assert json.loads(path.read_text(encoding="utf-8"))["revision"] == 1


def test_app_state_reset_helpers_are_best_effort_and_path_safe(monkeypatch, tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    monkeypatch.setattr(app_state_service.config, "BASE_DIR", str(base))
    with pytest.raises(HTTPException):
        app_state_service._clear_directory_contents(str(base))
    assert app_state_service._clear_directory_contents(str(base / "missing")) == []
    target = base / "target"
    target.mkdir()
    (target / "file.txt").write_text("x", encoding="utf-8")
    (target / "nested").mkdir()
    monkeypatch.setattr(app_state_service.shutil, "rmtree", lambda *_args: (_ for _ in ()).throw(OSError("locked")))
    monkeypatch.setattr(app_state_service.os, "remove", lambda _path: (_ for _ in ()).throw(OSError("locked")))
    assert app_state_service._clear_directory_contents(str(target)) == []

    class Observer:
        def stop(self):
            raise RuntimeError("stopped")

        def join(self, **_kwargs):
            return None

    class Handler:
        def shutdown(self):
            raise RuntimeError("worker")

    monkeypatch.setitem(state.watcher, "observer", Observer())
    monkeypatch.setitem(state.watcher, "handler", Handler())
    app_state_service._stop_watcher_for_reset()

    class JoiningObserver:
        def stop(self):
            return None

        def join(self, **_kwargs):
            raise RuntimeError("join")

    monkeypatch.setitem(state.watcher, "observer", JoiningObserver())
    app_state_service._stop_watcher_for_reset()
    process = SimpleNamespace(poll=lambda: None, terminate=lambda: (_ for _ in ()).throw(OSError("busy")))
    with state.index_jobs_lock:
        previous = dict(state.index_jobs)
        state.index_jobs.clear()
        state.index_jobs["job"] = {"process": process}
    try:
        app_state_service._cancel_index_jobs_for_reset()
        assert state.index_jobs == {}
    finally:
        state.index_jobs.update(previous)


def test_agent_workspace_defaults_and_tool_failures(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(agent_service.config, "BASE_DIR", str(root))
    monkeypatch.setattr(agent_service.config, "PROJECTS_DIRS", [str(root / "missing")])
    monkeypatch.delenv("TRINAXAI_AGENT_WORKSPACE_ROOTS", raising=False)
    assert agent_service._configured_workspace_roots() == (root.resolve(),)
    monkeypatch.setattr(agent_service, "_read_app_state", lambda: (_ for _ in ()).throw(RuntimeError("state")))
    assert agent_service._resolve_workspace("") == root.resolve()
    monkeypatch.setattr(agent_service, "_configured_workspace_roots", lambda: ())
    with pytest.raises(HTTPException) as exc:
        agent_service._resolve_workspace("")
    assert exc.value.status_code == 503
    req = SimpleNamespace(yolo=True)
    monkeypatch.setattr(agent_service, "_http_yolo_enabled", lambda: False)
    monkeypatch.setattr(agent_service, "authorize_scope", lambda *_args: None)
    with pytest.raises(HTTPException) as exc:
        agent_service._authorize_http_yolo(req, _request())
    assert exc.value.status_code == 403
    monkeypatch.setattr(
        agent_service.config,
        "route_model_for_messages",
        lambda _m: (_ for _ in ()).throw(RuntimeError("route")),
    )
    assert agent_service._resolve_model("auto", [{"role": "user", "content": "x"}])

    class ApprovalQueue:
        def put(self, item):
            if item.get("type") == "approval_request":
                session["approvals"][item["approval_id"]]["approved"] = True

    session = {"queue": ApprovalQueue(), "approvals": {}, "closed": False}
    monkeypatch.setattr(agent_service, "_APPROVAL_TIMEOUT_SECONDS", 1)
    ready = __import__("threading").Event()
    ready.set()
    monkeypatch.setattr(agent_service.threading, "Event", lambda: ready)
    monkeypatch.setattr(agent_service, "_safe_args", lambda args: args)
    monkeypatch.setattr(agent_service.uuid, "uuid4", lambda: SimpleNamespace(hex="id"))
    session["approvals"]["id"] = {"event": ready, "approved": True}
    assert agent_service._wait_for_approval(session, SimpleNamespace(name="tool"), {}) is True
    monkeypatch.setattr(
        agent_service.state,
        "fusion_retriever",
        SimpleNamespace(retrieve=lambda _q: [SimpleNamespace(metadata={}, get_content=lambda: "x" * 700)]),
    )
    assert "…" in agent_service._search_knowledge(None, "query")


def test_agent_external_search_and_research_results_degrade_cleanly(monkeypatch) -> None:
    import sys

    web = sys.modules["app.services.web_search_service"]
    monkeypatch.setattr(
        web, "search_web", lambda _q: ([{"title": "Result", "url": "https://x", "snippet": "x" * 700}], "duck")
    )
    assert "Result" in agent_service._web_search(None, "query")
    monkeypatch.setattr(web, "search_web", lambda _q: ([], "duck"))
    assert "no results" in agent_service._web_search(None, "query")
    monkeypatch.setattr(web, "search_web", lambda _q: (_ for _ in ()).throw(web.WebSearchError("offline")))
    assert "tool_status=degraded" in agent_service._web_search(None, "query")
    monkeypatch.setattr(
        agent_service.state,
        "fusion_retriever",
        SimpleNamespace(retrieve=lambda _q: (_ for _ in ()).throw(RuntimeError("rag"))),
    )
    assert "tool_status=degraded" in agent_service._search_knowledge(None, "query")
    research = sys.modules["app.services.research_service"]
    monkeypatch.setattr(research, "_research_sync", lambda _request: {"error_code": "offline", "error_detail": "down"})
    assert "tool_status=degraded" in agent_service._deep_research(None, "query")
    monkeypatch.setattr(research, "_research_sync", lambda _request: {"answer": "answer", "sources": []})
    assert "tool_status=degraded" in agent_service._deep_research(None, "query")


@pytest.mark.asyncio
async def test_index_upload_rejects_unsafe_empty_large_and_duplicate_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(system_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "sources"))
    monkeypatch.setattr(system_service.config, "PERSIST_DIR", str(tmp_path / "persist"))
    monkeypatch.setattr(system_service, "_ensure_collection", lambda _cid: {"id": "docs", "name": "Docs"})
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)

    original_commonpath = system_service.os.path.commonpath
    system_service.os.path.commonpath = lambda _paths: "/outside"
    try:
        with pytest.raises(HTTPException) as unsafe:
            await system_service.system_index_upload(
                object(),
                label="import",
                collection_id="docs",
                embed_model="",
                aggressive_quant=False,
                watch_id="",
                files=[UploadFile(filename="note.txt", file=BytesIO(b"x"))],
            )
        assert unsafe.value.status_code == 400
    finally:
        system_service.os.path.commonpath = original_commonpath

    with pytest.raises(HTTPException) as empty:
        await system_service.system_index_upload(
            object(),
            label="import",
            collection_id="docs",
            embed_model="",
            aggressive_quant=False,
            watch_id="",
            files=[UploadFile(filename="..", file=BytesIO(b"x"))],
        )
    assert empty.value.status_code == 400

    monkeypatch.setattr(system_service.config, "max_file_bytes", lambda _path: 1)
    with pytest.raises(HTTPException) as per_file:
        await system_service.system_index_upload(
            object(),
            label="import",
            collection_id="docs",
            embed_model="",
            aggressive_quant=False,
            watch_id="",
            files=[UploadFile(filename="note.txt", file=BytesIO(b"xx"))],
        )
    assert per_file.value.status_code == 400

    monkeypatch.setattr(system_service.config, "max_file_bytes", lambda _path: 100)
    monkeypatch.setattr(system_service.config, "UPLOAD_MAX_BYTES", 1)
    with pytest.raises(HTTPException) as total:
        await system_service.system_index_upload(
            object(),
            label="import",
            collection_id="docs",
            embed_model="",
            aggressive_quant=False,
            watch_id="",
            files=[UploadFile(filename="note.txt", file=BytesIO(b"xx"))],
        )
    assert total.value.status_code == 413

    monkeypatch.setattr(system_service.config, "UPLOAD_MAX_BYTES", 100)
    digest = hashlib.sha256(b"note.txt" + b"xx").hexdigest()
    with state.index_jobs_lock:
        state.index_jobs.clear()
        state.index_jobs["existing"] = {
            "id": "existing",
            "dedupe_key": f"docs:{digest}",
            "status": "completed",
        }
    monkeypatch.setattr(system_service.threading, "Thread", lambda **_kwargs: SimpleNamespace(start=lambda: None))
    duplicate = await system_service.system_index_upload(
        object(),
        label="import",
        collection_id="docs",
        embed_model="",
        aggressive_quant=False,
        watch_id="",
        files=[UploadFile(filename="note.txt", file=BytesIO(b"xx"))],
    )
    assert duplicate["duplicate"] is True and duplicate["job_id"] == "existing"
    with state.index_jobs_lock:
        state.index_jobs.clear()


@pytest.mark.asyncio
async def test_index_upload_watch_mirror_removes_stale_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(system_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "sources"))
    monkeypatch.setattr(system_service.config, "PERSIST_DIR", str(tmp_path / "persist"))
    monkeypatch.setattr(system_service, "_ensure_collection", lambda _cid: {"id": "docs", "name": "Docs"})
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    monkeypatch.setattr(system_service.threading, "Thread", lambda **_kwargs: SimpleNamespace(start=lambda: None))
    target = tmp_path / "sources" / "collections" / "docs" / "watchers" / "sync-watch"
    target.mkdir(parents=True)
    stale = target / "stale.txt"
    stale.write_text("old", encoding="utf-8")
    result = await system_service.system_index_upload(
        object(),
        label="sync",
        collection_id="docs",
        embed_model="",
        aggressive_quant=False,
        watch_id="watch",
        files=[UploadFile(filename="fresh.txt", file=BytesIO(b"new"))],
    )
    assert result["saved"] == 1 and not stale.exists()
    with state.index_jobs_lock:
        state.index_jobs.clear()


def test_web_search_settings_file_and_environment_failures(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_PATH", path)
    path.write_text("{broken")
    assert settings._read() == {}
    monkeypatch.setattr(settings.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("read-only")))
    with pytest.raises(HTTPException) as exc:
        settings._write({"preferred_provider": "auto"})
    assert exc.value.status_code == 500
    for name in settings._ENV.values():
        monkeypatch.delenv(name, raising=False)
    assert settings._apply({"enabled": False})["enabled"] is False
    assert settings.config.WEB_SEARCH_PROVIDER == "disabled"


@pytest.mark.asyncio
async def test_web_search_settings_connection_error_contracts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "authorize_system", lambda _request: None)
    monkeypatch.setattr(settings.config, "WEB_SEARCH_BRAVE_API_KEY", "")
    with pytest.raises(HTTPException) as exc:
        await settings.test_web_search_connection(WebSearchConnectionTest(query="x", provider="brave"), _request())
    assert exc.value.status_code == 424

    monkeypatch.setattr(
        settings.web_search_service, "search_web", MagicMock(side_effect=httpx.TimeoutException("late"))
    )
    with pytest.raises(HTTPException) as exc:
        await settings.test_web_search_connection(WebSearchConnectionTest(query="x", provider="duckduckgo"), _request())
    assert exc.value.status_code == 504
    response = httpx.Response(401, request=httpx.Request("GET", "https://example.test"))
    monkeypatch.setattr(
        settings.web_search_service,
        "search_web",
        MagicMock(side_effect=httpx.HTTPStatusError("bad", request=response.request, response=response)),
    )
    with pytest.raises(HTTPException) as exc:
        await settings.test_web_search_connection(WebSearchConnectionTest(query="x", provider="duckduckgo"), _request())
    assert exc.value.status_code == 401 and exc.value.detail["code"] == "invalid_credential"
    monkeypatch.setattr(settings.web_search_service, "search_web", lambda *_args, **_kwargs: ([], "duckduckgo"))
    with pytest.raises(HTTPException) as exc:
        await settings.test_web_search_connection(WebSearchConnectionTest(query="x", provider="duckduckgo"), _request())
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_health_handles_transport_failure_and_sysconf_fallback(monkeypatch) -> None:
    class BrokenClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url):
            raise OSError("offline")

    monkeypatch.setattr(health_service.httpx, "Client", BrokenClient)
    monkeypatch.setattr(state, "health_ollama_checked_at", 0.0)
    assert health_service._ollama_available_cached() is False
    monkeypatch.setitem(__import__("sys").modules, "psutil", None)
    monkeypatch.setattr(health_service.os, "sysconf", lambda key: 4 if key == "SC_PHYS_PAGES" else 1024, raising=False)
    result = await health_service.resources()
    assert result["ram"]["total"] == 4096
    monkeypatch.setattr(
        health_service.os,
        "sysconf",
        lambda _key: (_ for _ in ()).throw(OSError("missing")),
        raising=False,
    )
    assert (await health_service.resources())["ram"] is None


@pytest.mark.asyncio
async def test_system_service_degrades_when_self_test_capabilities_fail(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url):
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"models": [{"name": "m"}]})

    monkeypatch.setattr(system_service.httpx, "Client", Client)
    monkeypatch.setattr(
        system_service.Settings,
        "_embed_model",
        SimpleNamespace(get_text_embedding=lambda _x: (_ for _ in ()).throw(RuntimeError("embed"))),
    )
    monkeypatch.setattr(
        state, "fusion_retriever", SimpleNamespace(retrieve=lambda _x: (_ for _ in ()).throw(RuntimeError("rag")))
    )
    original_import = __import__("builtins").__import__

    def missing_optional(name, *args, **kwargs):
        if name.split(".")[0] in {"openpyxl", "pptx", "striprtf", "watchdog"}:
            raise ImportError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(__import__("builtins"), "__import__", missing_optional)
    request = SimpleNamespace(app=SimpleNamespace(openapi=lambda: {"paths": {}}))
    result = system_service.system_self_test(request)
    assert result["ok"] is False
    assert result["results"]["ollama"] is True
    assert result["results"]["embedding"] is False
    assert result["results"]["watcher"] is False

    with pytest.raises(HTTPException) as missing:
        await system_service.system_delete_index_import(IndexImportDeleteRequest(path=""), request)
    assert missing.value.status_code == 400
    target = tmp_path / "storage" / "collections" / "docs" / "upload"
    target.mkdir(parents=True)
    (target / "a.txt").write_text("a", encoding="utf-8")
    monkeypatch.setattr(system_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(system_service.config, "PERSIST_DIR", str(tmp_path / "persist"))
    monkeypatch.setattr(
        system_service,
        "_delete_indexed_rel_paths",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("index")),
    )
    (tmp_path / "persist").mkdir()
    (tmp_path / "persist" / "docstore.json").write_text("{}", encoding="utf-8")
    with pytest.raises(HTTPException) as failed:
        await system_service.system_delete_index_import(IndexImportDeleteRequest(path=str(target)), request)
    assert failed.value.status_code == 500


def test_admin_auth_scope_mapping_and_proxy_rejection(monkeypatch, tmp_path: Path) -> None:
    assert admin_auth._is_lan_client("not-an-ip") is False
    assert admin_auth._is_local_client("localhost") is True
    monkeypatch.setenv("TRINAXAI_PROXY_TRUSTED_PEERS", "bad-network,192.168.1.0/24")
    assert admin_auth._is_trusted_proxy_peer("192.168.1.20") is True
    assert admin_auth._is_trusted_proxy_peer("203.0.113.10") is False
    assert admin_auth.required_scopes_for_request(_request()) == ("system",)
    for path, method, expected in (
        ("/v1/agent", "POST", "agent"),
        ("/v1/watch", "GET", "index"),
        ("/collections", "GET", "read_private"),
        ("/collections", "POST", "index"),
        ("/v1/sources/a", "DELETE", "index"),
        ("/v1/usage", "POST", "chat"),
        ("/v1/chat", "POST", "chat"),
    ):
        request = _request()
        request.scope["path"] = path
        request.scope["method"] = method
        assert admin_auth.required_scopes_for_request(request) == (expected,)
    monkeypatch.setattr(admin_auth, "ADMIN_TOKEN", "secret")
    with pytest.raises(HTTPException) as exc:
        admin_auth.authorize_lan_or_scope(_request(client="203.0.113.5"), "web")
    assert exc.value.status_code == 403


def test_signed_proxy_identity_is_single_use_and_fails_closed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(admin_auth, "_PROXY_SECRET", b"secret")
    admin_auth._PROXY_SEEN_NONCES.clear()
    timestamp = str(int(admin_auth.time.time()))
    nonce = "a" * 32
    client_ip = "192.168.1.44"
    signature = admin_auth._proxy_signature(b"secret", client_ip, timestamp, nonce, "GET", "/")
    request = _request(
        client="127.0.0.1",
        headers={
            admin_auth._PROXY_HEADER: admin_auth._PROXY_VERSION,
            admin_auth._PROXY_CLIENT_HEADER: client_ip,
            admin_auth._PROXY_TIMESTAMP_HEADER: timestamp,
            admin_auth._PROXY_NONCE_HEADER: nonce,
            admin_auth._PROXY_SIGNATURE_HEADER: signature,
        },
    )
    assert admin_auth._verified_proxy_client(request, "127.0.0.1") == client_ip
    with pytest.raises(HTTPException) as replay:
        admin_auth._verified_proxy_client(request, "127.0.0.1")
    assert replay.value.status_code == 403
    with pytest.raises(HTTPException) as invalid:
        admin_auth._verified_proxy_client(_request(headers={admin_auth._PROXY_HEADER: "v2"}), "127.0.0.1")
    assert invalid.value.status_code == 403
    with pytest.raises(HTTPException) as bad_ip:
        admin_auth._verified_proxy_client(
            _request(headers={admin_auth._PROXY_HEADER: "v1", admin_auth._PROXY_CLIENT_HEADER: "bad"}),
            "127.0.0.1",
        )
    assert bad_ip.value.status_code == 403
    monkeypatch.setattr(admin_auth, "_PROXY_SECRET", None)
    proxy_path = admin_auth._proxy_secret_path
    monkeypatch.setattr(
        admin_auth,
        "_proxy_secret_path",
        lambda: SimpleNamespace(read_text=lambda **_kwargs: (_ for _ in ()).throw(OSError("denied"))),
    )
    assert admin_auth._load_proxy_secret() == b""
    monkeypatch.setattr(admin_auth, "_proxy_secret_path", proxy_path)
    monkeypatch.delenv("TRINAXAI_PROXY_SECRET", raising=False)
    assert admin_auth._proxy_secret_path().name == ".proxy_secret"
    admin_auth._PROXY_SECRET = b"secret"


def test_device_registry_storage_errors_fail_closed(monkeypatch, tmp_path: Path) -> None:
    secret = tmp_path / "secret"
    secret.write_text("", encoding="ascii")
    with pytest.raises(device_auth.DeviceRegistryError):
        device_auth._ensure_private_secret(secret)

    class DeniedPath:
        def read_text(self, **_kwargs):
            raise OSError("denied")

    with pytest.raises(device_auth.DeviceRegistryError):
        device_auth._ensure_private_secret(DeniedPath())
    existing = tmp_path / "existing"
    existing.write_text("00" * 32, encoding="ascii")
    monkeypatch.setattr(device_auth.os, "chmod", lambda *_args: (_ for _ in ()).throw(OSError("no chmod")))
    assert len(device_auth._ensure_private_secret(existing)) == 32
    registry = tmp_path / "registry.json"
    monkeypatch.setattr(device_auth.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("read only")))
    with pytest.raises(device_auth.DeviceRegistryError):
        device_auth._write_registry(registry, device_auth._empty_registry())


def test_watcher_helpers_bound_processes_and_paths(monkeypatch, tmp_path: Path) -> None:
    original_import = __import__("builtins").__import__

    def no_watchdog(name, *args, **kwargs):
        if name.startswith("watchdog"):
            raise ImportError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(__import__("builtins"), "__import__", no_watchdog)
    assert watcher_service._watch_try_import() is None

    class BrokenStream:
        def flush(self):
            raise OSError("closed")

    assert watcher_service._tail_stream(BrokenStream(), 20) == ""

    class Process:
        pid = 44

        def __init__(self):
            self.killed = False
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            raise __import__("subprocess").TimeoutExpired(["index"], timeout)

    process = Process()
    monkeypatch.setattr(watcher_service.os, "name", "other")
    watcher_service._terminate_process_tree(process, grace_seconds=0)
    assert process.terminated and process.killed
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "visible.txt").write_text("visible", encoding="utf-8")
    (source / ".hidden").write_text("hidden", encoding="utf-8")
    monkeypatch.setattr(watcher_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "local"))
    monkeypatch.setattr(watcher_service.config, "PERSIST_DIR", str(tmp_path / "persist"))
    watcher_service._seed_watch_mirror(str(source), str(target))
    assert (target / "visible.txt").read_text(encoding="utf-8") == "visible"
    monkeypatch.setattr(watcher_service.config, "PROJECTS_DIRS", [str(source), str(source)])
    assert watcher_service._watch_default_paths(None) == [str(source.resolve())]
    assert watcher_service._watch_paths(SimpleNamespace(paths=[str(source)], collection=None)) == [
        str(source.resolve())
    ]


def test_watcher_publishes_each_result_state_without_leaking_details(monkeypatch) -> None:
    handler = watcher_service._watch_Handler.__new__(watcher_service._watch_Handler)
    handler._queue_condition = __import__("threading").Condition()
    handler._queued = set()
    handler._timeout_seconds = 10
    with state.watcher["lock"]:
        state.watcher["handler"] = None
        state.watcher.update({"runs_completed": 0, "runs_failed": 0, "runs_timed_out": 0, "runs_cancelled": 0})
    for result, reload_ok, expected in (
        (watcher_service._WatchRunResult(None, stderr="cancelled", cancelled=True), False, "cancelled"),
        (watcher_service._WatchRunResult(None, stderr="timeout", timed_out=True), False, "timed_out"),
        (watcher_service._WatchRunResult(2, stderr="failed"), False, "failed"),
        (watcher_service._WatchRunResult(0), False, "failed"),
        (watcher_service._WatchRunResult(0, stdout="ok"), True, "succeeded"),
    ):
        handler._publish_result("/root", result, reload_ok=reload_ok)
        assert state.watcher["job_status"] == expected
    assert state.watcher["runs_completed"] == 1
    assert state.watcher["runs_failed"] == 2
    assert state.watcher["runs_timed_out"] == 1
    assert state.watcher["runs_cancelled"] == 1


def test_rag_nonstream_generation_runs_one_bounded_fix_pass(monkeypatch) -> None:
    spec = SimpleNamespace(
        use_rag=False,
        model="model",
        regime=__import__("app.generation.spec", fromlist=["Regime"]).Regime.CODE_GEN,
        validate=True,
        max_fix_passes=1,
        retrieval_mode="auto",
        llm_kwargs=lambda: {},
        describe=lambda: "code plan",
    )
    results = iter(
        [SimpleNamespace(ok=False, summary=lambda: "missing html"), SimpleNamespace(ok=True, summary=lambda: "ok")]
    )
    generated = iter(["bad", "fixed"])
    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: spec)
    monkeypatch.setattr(rag_service, "get_llm", lambda *_args, **_kwargs: "llm")
    monkeypatch.setattr(rag_service, "build_generation_prompt", lambda *_args, **_kwargs: "prompt")
    monkeypatch.setattr(rag_service, "_freeform_generate", lambda *_args, **_kwargs: next(generated))
    monkeypatch.setattr(rag_service, "validate_output", lambda *_args, **_kwargs: next(results))
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)
    response, nodes, model, project = rag_service.run_rag(
        [{"role": "user", "content": "write a code example"}], stream=False
    )
    assert str(response) == "fixed"
    assert nodes == [] and model == "model" and project is None


def test_public_schema_validators_reject_unsafe_shapes() -> None:
    from pydantic import ValidationError

    invalid_messages = [
        [{"role": "system", "content": "x"}],
        [{"role": "user", "content": 1}],
        [{"role": "other", "content": "x"}],
        ["not an object"],
    ]
    for messages in invalid_messages:
        with pytest.raises(ValidationError):
            __import__("app.schemas", fromlist=["ChatRequest"]).ChatRequest(messages=messages)
    with pytest.raises(ValidationError):
        __import__("app.schemas", fromlist=["AppStateOperation"]).AppStateOperation(op="set", key="tc-x")
    with pytest.raises(ValidationError):
        __import__("app.schemas", fromlist=["AppStateOperation"]).AppStateOperation(
            op="delete", key="tc-x", value="bad"
        )
    with pytest.raises(ValidationError):
        AppStateRequest(values={"tc-x": "x"}, operations=[])
    with pytest.raises(ValidationError):
        __import__("app.schemas.api", fromlist=["AgentRequest"]).AgentRequest(
            messages=[{"role": "assistant", "content": "x"}]
        )
    with pytest.raises(ValidationError):
        __import__("app.schemas.api", fromlist=["AgentRequest"]).AgentRequest(
            messages=[{"role": "user", "content": "x" * 100_001}]
        )
    with pytest.raises(ValidationError):
        __import__("app.schemas.api", fromlist=["AgentRequest"]).AgentRequest(
            messages=[{"role": "user", "content": "x"}] * 101,
            web_search=False,
        )
    with pytest.raises(ValidationError):
        __import__("app.schemas.api", fromlist=["ResearchRequest"]).ResearchRequest(
            query="x",
            collections=[str(index) for index in range(51)],
        )
    with pytest.raises(ValidationError):
        __import__("app.schemas.api", fromlist=["MemoryUpdateRequest"]).MemoryUpdateRequest()


def test_api_facade_supports_dynamic_attribute_lifecycle(monkeypatch) -> None:
    import app.api_runtime as facade

    original = facade.__getattr__("APP_STATE_PATH")
    facade.__setattr__("APP_STATE_PATH", "temporary")
    assert facade.__getattr__("APP_STATE_PATH") == "temporary"
    facade.__delattr__("APP_STATE_PATH")
    facade.__setattr__("APP_STATE_PATH", original)
    assert "APP_STATE_PATH" in facade.__dir__()


def test_scoped_retriever_is_cached_and_filters_collections(monkeypatch) -> None:
    class Node:
        def __init__(self, collection_id: str):
            self.metadata = {"collection_id": collection_id}

    class Index:
        docstore = SimpleNamespace(docs={"a": Node("docs"), "b": Node("other")})

        def as_retriever(self, **kwargs):
            return ("vector", kwargs)

    class BM25:
        @classmethod
        def from_defaults(cls, **kwargs):
            return ("bm25", kwargs)

    class Fusion:
        def __init__(self, retrievers, **kwargs):
            self.retrievers = retrievers
            self.kwargs = kwargs

    monkeypatch.setattr(shared_runtime.state, "vector_index", Index())
    monkeypatch.setattr(shared_runtime.state, "index_docstore", Index.docstore)
    monkeypatch.setattr(shared_runtime.state, "collection_retrievers", OrderedDict())
    monkeypatch.setattr(shared_runtime, "BM25Retriever", BM25)
    monkeypatch.setattr(shared_runtime, "QueryFusionRetriever", Fusion)
    monkeypatch.setattr(shared_runtime, "MetadataFilters", lambda **kwargs: kwargs)
    monkeypatch.setattr(shared_runtime, "MetadataFilter", lambda **kwargs: kwargs)
    monkeypatch.setattr(shared_runtime, "FilterCondition", SimpleNamespace(OR="or"))
    monkeypatch.setattr(shared_runtime, "get_llm", lambda _model: "llm")
    assert shared_runtime._retriever_for_collections(()) is shared_runtime.state.fusion_retriever
    assert shared_runtime._retriever_for_collections(("missing",)) is None
    first = shared_runtime._retriever_for_collections(("docs",))
    assert isinstance(first, Fusion)
    assert shared_runtime._retriever_for_collections(("docs",)) is first


def test_agent_workspace_policy_and_session_approval_lifecycle(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "project"
    child = root / "child"
    child.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setenv("TRINAXAI_AGENT_WORKSPACE_ROOTS", str(root))
    assert agent_service._configured_workspace_roots() == (root.resolve(),)
    assert agent_service._workspace_is_allowed(child.resolve())
    assert not agent_service._workspace_is_allowed(outside.resolve())
    assert agent_service._resolve_workspace(str(child)) == child.resolve()
    with pytest.raises(HTTPException) as exc:
        agent_service._resolve_workspace(str(outside))
    assert exc.value.status_code == 403
    assert agent_service._resolve_workspace("") == root.resolve()
    monkeypatch.setenv("TRINAXAI_AGENT_HTTP_YOLO", "true")
    req = SimpleNamespace(yolo=True)
    monkeypatch.setattr(agent_service, "authorize_scope", lambda *_args: None)
    monkeypatch.setattr(agent_service, "_is_local_client", lambda _ip: True)
    agent_service._authorize_http_yolo(req, _request())
    monkeypatch.setattr(agent_service, "_is_local_client", lambda _ip: False)
    with pytest.raises(HTTPException) as exc:
        agent_service._authorize_http_yolo(req, _request())
    assert exc.value.status_code == 403
    monkeypatch.setattr(agent_service.config, "MODEL_GENERAL", "general")
    monkeypatch.setattr(agent_service.config, "route_model_for_messages", lambda _messages: "routed")
    assert agent_service._resolve_model("auto", [{"role": "user", "content": "hi"}]) == "routed"
    assert agent_service._resolve_model("qwen2.5-coder:7b") == "general"
    session_id, session = agent_service._register_session(("device", "one"))
    assert agent_service._identity_key(_request()) == ("unknown", "unknown")
    agent_service._drop_session(session_id)
    assert session["closed"] and session["cancelled"].is_set()


def test_agent_external_tools_and_approval_timeout_are_actionable(monkeypatch) -> None:
    session = {"queue": __import__("queue").Queue(), "approvals": {}, "closed": False}
    monkeypatch.setattr(agent_service, "_APPROVAL_TIMEOUT_SECONDS", 0)
    tool = SimpleNamespace(name="run_command")
    assert agent_service._wait_for_approval(session, tool, {"command": "x"}) is False
    assert session["queue"].get()["type"] == "approval_request"
    assert session["queue"].get()["type"] == "approval_timeout"
    assert "truncated" in agent_service._safe_args({"content": "x" * 1300})["content"]
    monkeypatch.setattr(agent_service.state, "fusion_retriever", None)
    assert "No indexed" in agent_service._search_knowledge(None, "query")
    monkeypatch.setattr(agent_service.state, "fusion_retriever", object())
    assert "must not be empty" in agent_service._search_knowledge(None, "")
    monkeypatch.setattr(agent_service, "format_tool_failure", lambda *_args, **_kwargs: "failure")
    assert agent_service._web_search(None, "") == "failure"
    assert agent_service._deep_research(None, "") == "failure"
    assert agent_service._search_memory(None, "") == "failure"
    assert len(agent_service._agent_tools(web_search=False, knowledge_search=False, deep_research=False)) >= 2


def test_session_round_trip_skips_bad_lines_and_sanitizes_names(tmp_path: Path, capsys) -> None:
    with Session("../chat/main", tmp_path) as session:
        session.append("user", "hello", {"source": "test"})
        path = session.path
    path.write_text(path.read_text() + "{broken\n\n", encoding="utf-8")
    records = Session.load("../chat/main", tmp_path)
    assert records[0]["content"] == "hello"
    assert "malformed session line" in capsys.readouterr().err
    assert Session.delete("../chat/main", tmp_path)
    assert not Session.delete("../chat/main", tmp_path)


def test_lifecycle_and_index_commands_report_recoverable_failures(monkeypatch, tmp_path: Path) -> None:
    ui = MagicMock()
    monkeypatch.setattr(_lifecycle, "find_install_root", lambda: None)
    assert _lifecycle.run_script("update", [], ui) == 1
    root = tmp_path
    (root / "update.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(_lifecycle.sys, "platform", "linux")
    monkeypatch.setattr(_lifecycle, "find_install_root", lambda: root)
    monkeypatch.setattr(_lifecycle, "command_for", lambda *_args: ["update"])
    monkeypatch.setattr(_lifecycle, "run_process_group", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))
    assert _lifecycle.run_script("update", [], ui) == 0
    monkeypatch.setattr(index_command, "find_install_root", lambda: tmp_path)
    assert index_command.run(SimpleNamespace(path=None, folder=None), None, ui, None) == 1
    assert index_command.run(SimpleNamespace(path=str(tmp_path / "missing"), folder=None), None, ui, None) == 1
    (tmp_path / "index.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(index_command, "spawn_process_group", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(index_command, "wait_process_group", lambda *_args, **_kwargs: 4)
    assert (
        index_command.run(
            SimpleNamespace(path=str(tmp_path), folder=None, collection="docs", append=False), None, ui, None
        )
        == 4
    )


def test_ask_command_handles_stdin_limits_and_backend_failures(monkeypatch, tmp_path: Path) -> None:
    ui = MagicMock()
    config = SimpleNamespace(collections=["docs"], active_collection="docs", model="model")
    monkeypatch.setattr(ask.sys.stdin, "isatty", lambda: True)
    assert ask.run(SimpleNamespace(prompt=[], collections=None, session="x", engine=None), None, ui, config) == 2
    monkeypatch.setattr(ask.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(ask.sys.stdin, "read", lambda _limit: "question")
    monkeypatch.setattr(ask, "Session", Session)
    monkeypatch.setattr(ask, "_resolve_engine", lambda *_args: "rag")
    monkeypatch.setattr(ask, "_stream_answer", lambda *_args: "answer")
    assert ask.run(SimpleNamespace(prompt=[], collections=None, session="x", engine=None), None, ui, config) == 0
    monkeypatch.setattr(ask, "_stream_answer", MagicMock(side_effect=RuntimeError("offline")))
    assert (
        ask.run(SimpleNamespace(prompt=["question"], collections=None, session="x", engine=None), None, ui, config) == 1
    )
    monkeypatch.setattr(ask.sys.stdin, "read", lambda _limit: "x" * 1_048_577)
    assert ask.run(SimpleNamespace(prompt=[], collections=None, session="x", engine=None), None, ui, config) == 2


def test_cli_dispatcher_converts_import_and_return_errors(monkeypatch) -> None:
    ui = MagicMock()
    monkeypatch.setattr(cli_app.importlib, "import_module", MagicMock(side_effect=ImportError("missing")))
    assert cli_app._dispatch("missing", SimpleNamespace(), None, ui, None) == 1
    module = SimpleNamespace()
    monkeypatch.setattr(cli_app.importlib, "import_module", lambda _name: module)
    assert cli_app._dispatch("empty", SimpleNamespace(), None, ui, None) == 1
    module.run = lambda *_args: None
    assert cli_app._dispatch("empty", SimpleNamespace(), None, ui, None) == 0
    module.run = lambda *_args: (_ for _ in ()).throw(KeyboardInterrupt())
    assert cli_app._dispatch("empty", SimpleNamespace(), None, ui, None) == 130
    module.run = lambda *_args: (_ for _ in ()).throw(SystemExit(3))
    assert cli_app._dispatch("empty", SimpleNamespace(), None, ui, None) == 3


def test_cli_main_dispatches_local_commands_without_opening_http_client(monkeypatch, tmp_path: Path) -> None:
    client_factory = MagicMock()
    monkeypatch.setattr(cli_app, "get_console", lambda **_kwargs: MagicMock())
    monkeypatch.setattr(
        cli_app,
        "_dispatch",
        lambda name, args, passed, ui, config: 0 if name == "version" and passed is None else 1,
    )
    monkeypatch.setattr("trinaxai_cli.client.TrinaxAPIClient", client_factory)
    assert cli_app.main(["--api-url", "https://localhost:3333", "version"]) == 0
    client_factory.assert_not_called()
    ca = tmp_path / "ca.pem"
    ca.write_text("ca", encoding="utf-8")
    assert cli_app.main(["--ca-file", str(ca), "version"]) == 0
    client_factory.assert_not_called()


def test_lifecycle_platform_and_process_failures_are_safe(monkeypatch, tmp_path: Path) -> None:
    ui = MagicMock()
    monkeypatch.setattr(_lifecycle.sys, "platform", "linux")
    monkeypatch.setattr(_lifecycle.shutil, "which", lambda _name: "/bin/bash")
    assert _lifecycle.command_for("update", ["--yes"], tmp_path) == ["/bin/bash", str(tmp_path / "update.sh"), "--yes"]
    monkeypatch.setattr(_lifecycle.sys, "platform", "win32")
    monkeypatch.setattr(_lifecycle.shutil, "which", lambda _name: None)
    with pytest.raises(FileNotFoundError):
        _lifecycle.command_for("update", [], tmp_path)
    monkeypatch.setattr(_lifecycle.shutil, "which", lambda _name: "pwsh")
    assert _lifecycle.command_for("update", [], tmp_path)[0] == "pwsh"
    (tmp_path / "update.ps1").write_text("", encoding="utf-8")
    monkeypatch.setattr(_lifecycle, "find_install_root", lambda: tmp_path)
    monkeypatch.setattr(_lifecycle, "command_for", lambda *_args: ["update"])
    monkeypatch.setattr(
        _lifecycle, "run_process_group", lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    assert _lifecycle.run_script("update", [], ui) == 130
    monkeypatch.setattr(
        _lifecycle,
        "run_process_group",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("denied")),
    )
    assert _lifecycle.run_script("update", [], ui) == 1


def test_doctor_parsers_and_ollama_fail_closed(monkeypatch) -> None:
    assert cli_app is not None
    from trinaxai_cli.commands import doctor

    assert doctor._process_command(0) == ""
    monkeypatch.setattr(
        doctor, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")), raising=False
    )
    monkeypatch.setattr(doctor.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=""))
    assert doctor._process_command(10) == ""
    assert doctor._frontend_mode_from_command("vite preview") == "preview"
    assert doctor._frontend_mode_from_command("npm run dev -- --host 0.0.0.0") == "dev"
    assert doctor._frontend_mode_from_command("unknown") is None
    assert doctor._safe_backend_command("uvicorn app --host 0.0.0.0") is False
    assert doctor._safe_backend_command("uvicorn app --host 127.0.0.1") is True
    assert doctor._safe_backend_command("") is None
    assert doctor._ollama_api_ok("not a url") is False


def test_console_rich_and_branding_fallbacks(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_ui, "_RICH", True)

    def rich_console(*_args, **kwargs):
        if kwargs:
            raise TypeError()
        return SimpleNamespace(print=lambda *_args, **_kwargs: None)

    monkeypatch.setattr(cli_ui, "_rich_console_cls", rich_console)
    monkeypatch.setattr(
        cli_ui, "_rich_prompt_cls", SimpleNamespace(ask=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError()))
    )
    monkeypatch.setattr(
        cli_ui,
        "_rich_confirm_cls",
        SimpleNamespace(ask=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError())),
    )
    monkeypatch.setattr(__import__("builtins"), "input", lambda _prompt: "")
    console = cli_ui.Console()
    assert console.prompt("Name", default="fallback") == "fallback"
    assert console.confirm("Continue", default=True) is True
    api_error = type("TrinaxAPIError", (Exception,), {})
    console.failure("API", api_error("offline"))
    monkeypatch.setattr(cli_ui, "_rich_progress_cls", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError()))
    with console.spinner("work"):
        pass
    monkeypatch.setattr(cli_ui, "_rich_prompt_cls", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError()))
    assert console.chat_prompt() == ""
    console.assistant_label("Assistant")
    monkeypatch.setattr(cli_ui, "_rich_table_cls", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(
        cli_ui, "_rich_panel_cls", SimpleNamespace(fit=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError()))
    )
    monkeypatch.setattr(cli_ui, "_rich_markdown_cls", lambda *_args: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(cli_ui, "_rich_syntax_cls", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError()))
    console.table(["name"], [["docs"]])
    console.panel("body")
    console.markdown("body")
    console.code("body")
    original_title = branding.set_terminal_title
    monkeypatch.setattr(branding, "set_terminal_title", lambda *_args: (_ for _ in ()).throw(RuntimeError()))
    console.set_title("title")
    monkeypatch.setattr(branding, "set_terminal_title", original_title)
    monkeypatch.setattr(branding, "_terminal_width", lambda: 40)
    assert len(branding.banner_lines()) > 0
    monkeypatch.setattr(branding, "_is_tty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(branding.os, "name", "posix")
    branding.set_terminal_title("TrinaxAI")
    branding.reset_terminal_title()
    assert "\x1b]0;TrinaxAI" in capsys.readouterr().out
