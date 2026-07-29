from __future__ import annotations

import ssl
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from trinaxai_cli import client as client_module
from trinaxai_cli.client import TrinaxAPIClient, TrinaxAPIError


def _client() -> TrinaxAPIClient:
    client = object.__new__(TrinaxAPIClient)
    client.base_url = "https://localhost:3333"
    client.verify_tls = ssl.create_default_context()
    client.timeout = 10.0
    client._request_headers = {}
    client._ollama_clients = {}
    return client


def test_send_retries_safe_transport_failures_but_never_replays_post(monkeypatch) -> None:
    client = _client()
    response = SimpleNamespace(status_code=200, content=b"{}", json=lambda: {"ok": True}, text="{}")
    client._client = MagicMock()
    client._client.request.side_effect = [httpx.ConnectError("offline"), response]
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)

    assert client._send("GET", "/health") == {"ok": True}
    assert client._client.request.call_count == 2

    client._client.request.reset_mock()
    client._client.request.side_effect = httpx.ReadTimeout("timeout")
    with pytest.raises(TrinaxAPIError) as raised:
        client._send("POST", "/v1/memory", json={"text": "x"})
    assert client._client.request.call_count == 1
    assert raised.value.retryable is True
    assert "ReadTimeout" not in str(raised.value)


def test_handle_masks_error_payloads_and_supports_empty_text_and_json() -> None:
    with pytest.raises(TrinaxAPIError) as raised:
        TrinaxAPIClient._handle(
            SimpleNamespace(
                status_code=503,
                content=b'{"detail":"private upstream path"}',
                json=lambda: {"detail": "private upstream path"},
                text='{"detail":"private upstream path"}',
            )
        )
    assert raised.value.status == 503
    assert "private upstream path" not in str(raised.value)

    assert TrinaxAPIClient._handle(SimpleNamespace(status_code=204, content=b"", text="")) == {}
    assert (
        TrinaxAPIClient._handle(
            SimpleNamespace(
                status_code=200,
                content=b"plain",
                json=MagicMock(side_effect=ValueError("not json")),
                text="plain",
            )
        )
        == "plain"
    )


def test_client_methods_preserve_api_paths_bodies_and_encoding() -> None:
    client = _client()
    client._get = MagicMock(
        side_effect=[
            {"devices": [{"id": "device"}]},
            {"collections": [{"id": "docs"}]},
            {"sources": []},
            {"chunks": []},
            {"running": True},
            {"memories": [{"id": "memory"}]},
            {"summary": "short"},
            {"messages_total": 2},
            {"ok": True},
        ]
    )
    client._post = MagicMock(
        side_effect=[
            {"code": "PAIR"},
            {"ok": True},
            {"collection": {"id": "new"}},
            {"ok": True},
            {"ok": True},
            {"memory": {"id": "memory"}},
            {"summary": "updated"},
            {"memories": [{"id": "memory"}]},
            {"answer": "research"},
        ]
    )
    client._patch = MagicMock(return_value={"collection": {"id": "docs", "name": "Renamed"}})
    client._delete = MagicMock(
        side_effect=[
            {"device": {"id": "device"}},
            {"deleted_nodes": 2},
            {"deleted": True},
        ]
    )

    assert client.start_pairing(["chat"])["code"] == "PAIR"
    assert client.list_paired_devices() == [{"id": "device"}]
    assert client.revoke_paired_device("device/id") == {"id": "device"}
    assert client.list_collections() == [{"id": "docs"}]
    assert client.reload_index()["ok"] is True
    assert client.create_collection("New") == {"id": "new"}
    assert client.rename_collection("docs", "Renamed")["name"] == "Renamed"
    assert client.delete_collection("docs/id") == 2
    assert client.list_sources("docs") == {"sources": []}
    assert client.list_chunks("docs/id", "folder/file name.md", q="needle") == {"chunks": []}
    assert client.watch_start(["/project"], "docs")["ok"] is True
    assert client.watch_stop()["ok"] is True
    assert client.watch_status() == {"running": True}
    assert client.list_memories() == [{"id": "memory"}]
    assert client.add_memory("Remember", ["preference"]) == {"memory": {"id": "memory"}}
    assert client.delete_memory("memory") is True
    assert client.refresh_memory() == {"summary": "updated"}
    assert client.memory_summary() == {"summary": "short"}
    assert client.memory_context("current task") == [{"id": "memory"}]
    assert client.research("compare", ["docs"], 3, web_search=True, include_local=True)["answer"] == "research"
    assert client.stats() == {"messages_total": 2}
    assert client.health() == {"ok": True}

    client._delete.assert_any_call("/collections/docs%2Fid")
    client._get.assert_any_call(
        "/v1/sources/docs%2Fid/folder/file%20name.md/chunks",
        [("limit", "50"), ("offset", "0"), ("q", "needle")],
    )
    research_call = client._post.call_args_list[-1]
    assert research_call.args[0] == "/v1/research"
    assert research_call.args[1]["web_search"] is True
    assert research_call.args[1]["include_local"] is True
    assert research_call.kwargs["timeout"] == 300.0


def test_ollama_client_is_reused_and_closed() -> None:
    client = _client()
    created = []

    class HttpClient:
        closed = False

        def __init__(self, **kwargs):
            created.append(kwargs)

        def get(self, *_args, **_kwargs):
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"models": [{"name": "model"}]},
            )

        def stream(self, *args, **kwargs):
            return args, kwargs

        def close(self):
            self.closed = True

    original = client_module.httpx.Client
    client_module.httpx.Client = HttpClient
    client._client = HttpClient()
    try:
        first = client._ollama_client("http://localhost:11434/")
        assert client._ollama_client("http://localhost:11434") is first
        assert client.list_ollama_models("http://localhost:11434") == [{"name": "model"}]
        method, options = client.stream_ollama("http://localhost:11434", {"model": "model"})
        assert method == ("POST", "/api/chat")
        assert options["json"] == {"model": "model"}
        client.close()
        assert client._ollama_clients == {}
        assert first.closed is True
    finally:
        client_module.httpx.Client = original


def test_client_initialization_auth_tls_and_context_manager(monkeypatch, tmp_path: Path) -> None:
    created = []

    class HttpClient:
        def __init__(self, **kwargs):
            created.append(kwargs)

        def get(self, *_args, **_kwargs):
            return SimpleNamespace(status_code=200)

        def close(self):
            return None

    monkeypatch.setattr(client_module.httpx, "Client", HttpClient)
    monkeypatch.setenv("TRINAXAI_ADMIN_TOKEN", " admin ")
    client = TrinaxAPIClient("https://localhost:3333/")
    assert client.base_url == "https://localhost:3333"
    assert created[0]["headers"] == {"X-Admin-Token": "admin"}
    assert client.__enter__() is client
    client.__exit__(None, None, None)

    ca = tmp_path / "ca.pem"
    ca.write_text("invalid", encoding="utf-8")
    with pytest.raises(ssl.SSLError):
        client._resolve_local_ca(str(ca))
    with pytest.raises(ValueError, match="cannot be disabled"):
        client._resolve_local_ca(False)


def test_client_prefers_healthy_local_https_and_never_remote(monkeypatch) -> None:
    client = _client()
    client.base_url = "http://localhost:3333"
    client._client = MagicMock()
    client._client.get.side_effect = httpx.ConnectError("offline")
    switched = []

    class Probe:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, _path):
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(client_module.httpx, "Client", Probe)
    monkeypatch.setattr(client, "_switch_base_url", lambda value: switched.append(value))
    client._prefer_local_https_if_needed()
    assert switched == ["https://localhost:3333"]

    client.base_url = "http://example.com"
    assert client._local_https_candidate() is None
    client.base_url = "https://localhost:3333"
    assert client._local_https_candidate() is None


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ([{"id": "one"}], [{"id": "one"}]),
        ({"memories": [{"id": "two"}]}, [{"id": "two"}]),
        ({"data": {"memories": [{"id": "three"}]}}, [{"id": "three"}]),
        ({"items": [{"id": "four"}]}, [{"id": "four"}]),
    ],
)
def test_memory_list_compatibility_shapes(payload, expected) -> None:
    client = _client()
    client._get = MagicMock(return_value=payload)
    assert client.list_memories() == expected


def test_memory_list_rejects_malformed_payload_and_context_defaults() -> None:
    client = _client()
    client._get = MagicMock(return_value={"items": ["private"]})
    with pytest.raises(TrinaxAPIError) as raised:
        client.list_memories()
    assert raised.value.payload == {"items": ["private"]}
    client._post = MagicMock(side_effect=[{"memories": "bad"}, "bad"])
    assert client.memory_context("query") == []
    assert client.memory_context("query") == []


def test_research_only_sends_requested_optional_values() -> None:
    client = _client()
    client.timeout = 5
    client._post = MagicMock(return_value={"answer": "ok"})
    result = client.research(
        "question",
        depth=9,
        web_search=False,
        search_query="search",
        context="context",
        model="model",
    )
    assert result["answer"] == "ok"
    body = client._post.call_args.args[1]
    assert body == {
        "query": "question",
        "collections": [],
        "depth": 9,
        "web_search": False,
        "search_query": "search",
        "context": "context",
        "model": "model",
    }
    assert client._post.call_args.kwargs["timeout"] == 300.0
