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
    assert client.list_sources("docs", source_id="source-1") == {"sources": []}
    assert client.list_chunks("docs/id", "folder/file name.md", q="needle", source_id="source-1") == {"chunks": []}
    assert client.watch_start(["/project"], "docs")["ok"] is True
    assert client.watch_stop()["ok"] is True
    assert client.watch_status() == {"running": True}
    assert client.list_memories() == [{"id": "memory"}]
    assert client.add_memory("Remember", ["preference"]) == {"memory": {"id": "memory"}}
    assert client.delete_memory("memory") is True
    assert client.refresh_memory() == {"summary": "updated"}
    client._post.assert_any_call("/v1/memory/refresh", {}, timeout=300.0)
    assert client.memory_summary() == {"summary": "short"}
    assert client.memory_context("current task") == [{"id": "memory"}]
    assert client.research("compare", ["docs"], 3, web_search=True, include_local=True)["answer"] == "research"
    assert client.stats() == {"messages_total": 2}
    assert client.health() == {"ok": True}

    client._delete.assert_any_call("/collections/docs%2Fid")
    client._get.assert_any_call(
        "/v1/sources/docs%2Fid/folder/file%20name.md/chunks",
        [("limit", "50"), ("offset", "0"), ("q", "needle"), ("source_id", "source-1")],
    )
    client._get.assert_any_call("/v1/sources", [("collection", "docs"), ("source_id", "source-1")])
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


def test_memory_list_and_context_reject_malformed_payloads() -> None:
    client = _client()
    client._get = MagicMock(return_value={"items": ["private"]})
    with pytest.raises(TrinaxAPIError) as raised:
        client.list_memories()
    assert raised.value.payload == {"items": ["private"]}
    client._post = MagicMock(side_effect=[{"memories": "bad"}, "bad"])
    with pytest.raises(TrinaxAPIError):
        client.memory_context("query")
    with pytest.raises(TrinaxAPIError):
        client.memory_context("query")


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


def test_unreachable_local_service_is_not_blamed_on_the_internet() -> None:
    from trinaxai_cli.client import TrinaxAPIError

    english = TrinaxAPIError(0, "local service unavailable", language="en")
    assert "internet" not in str(english).lower()
    assert str(english) == "Cannot reach the local TrinaxAI service. Start it with: trinaxai start"
    assert (english.status, english.category, english.error_code) == (
        0,
        "internet_unavailable",
        "ERR_INTERNET_UNAVAILABLE",
    )

    spanish = TrinaxAPIError(0, "local service unavailable", language="es")
    assert str(spanish) == "No se puede conectar con el servicio local de TrinaxAI. Inícialo con: trinaxai start"

    # A timeout and real HTTP failures keep their own messages.
    waited = str(TrinaxAPIError(0, "request timed out"))
    assert "did not finish within the wait limit" in waited and "network" not in waited.lower()
    assert "TRINAXAI_CLI_TIMEOUT" in waited and "--depth 1" in waited
    assert str(TrinaxAPIError(0, "request timed out", language="es")).startswith("TrinaxAI no terminó")
    assert "Start it with" not in str(TrinaxAPIError(404, "not found"))


def test_an_untrusted_certificate_is_not_reported_as_a_stopped_service(monkeypatch) -> None:
    client = _client()
    client._client = MagicMock()
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)
    rejected = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
    rejected.__cause__ = ssl.SSLCertVerificationError(1, "certificate verify failed")
    client._client.request.side_effect = rejected

    with pytest.raises(TrinaxAPIError) as raised:
        client._send("GET", "/health")

    message = str(raised.value)
    assert message == "This computer does not trust the local TrinaxAI certificate. Run: trinaxai doctor"
    assert "start" not in message.lower() and raised.value.recovery_included is True
    spanish = TrinaxAPIError(0, "x", language="es", certificate_problem=True)
    assert str(spanish).startswith("Este equipo no conf")
    # A plain refused connection is still a stopped service.
    client._client.request.side_effect = httpx.ConnectError("refused")
    with pytest.raises(TrinaxAPIError) as stopped:
        client._send("GET", "/health")
    assert "trinaxai start" in str(stopped.value)


def _serve_plain_http(status: int = 200, payload: bytes = b'{"ok":true}'):
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server API
            body = payload
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_a_local_api_without_https_is_reached_over_plain_http() -> None:
    server = _serve_plain_http()
    try:
        client = TrinaxAPIClient(f"https://127.0.0.1:{server.server_port}", verify_tls=None)
        assert client._get("/health") == {"ok": True}
        assert client.base_url == f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def test_the_plain_http_fallback_is_only_for_a_local_server_that_answers() -> None:
    server = _serve_plain_http(status=503)
    try:
        client = TrinaxAPIClient(f"https://127.0.0.1:{server.server_port}", verify_tls=None)
        with pytest.raises(TrinaxAPIError):
            client._get("/health")
        assert client.base_url.startswith("https://")  # an unhealthy server is not adopted
    finally:
        server.shutdown()
        server.server_close()
    remote = _client()
    remote.base_url = "https://example.com:3333"
    assert remote._use_plain_http_if_served() is False
    already_plain = _client()
    already_plain.base_url = "http://localhost:3333"
    assert already_plain._use_plain_http_if_served() is False


def test_ensure_reachable_settles_the_scheme_before_a_streamed_request() -> None:
    server = _serve_plain_http()
    try:
        client = TrinaxAPIClient(f"https://127.0.0.1:{server.server_port}", verify_tls=None)
        client.ensure_reachable()
        assert client.base_url.startswith("http://")
    finally:
        server.shutdown()
        server.server_close()
    # Anything else (here: nothing listening) is left for the real request to report.
    refused = TrinaxAPIClient("https://127.0.0.1:9", verify_tls=None)
    refused.ensure_reachable()
    assert refused.base_url.startswith("https://")


def test_another_program_on_the_port_is_not_mistaken_for_trinaxai() -> None:
    for status, payload in ((404, b"{}"), (200, b'{"hello":"world"}'), (200, b"[]")):
        server = _serve_plain_http(status, payload)
        try:
            client = TrinaxAPIClient(f"https://127.0.0.1:{server.server_port}", verify_tls=None)
            assert client._use_plain_http_if_served() is False
            assert client.base_url.startswith("https://")
        finally:
            server.shutdown()
            server.server_close()


def test_ensure_reachable_probes_only_once_per_client() -> None:
    client = _client()
    client._client = MagicMock()
    client.ensure_reachable()
    client.ensure_reachable()
    assert client._client.get.call_count == 1


def test_cli_timeout_overrides_the_research_wait(monkeypatch) -> None:
    client = _client()
    client._post = MagicMock(return_value={})
    client.research("q", depth=1)
    assert client._post.call_args.kwargs["timeout"] == 180.0
    monkeypatch.setenv("TRINAXAI_CLI_TIMEOUT", "900")
    client.research("q", depth=1)
    assert client._post.call_args.kwargs["timeout"] == 900.0
    for bad in ("soon", "1", "999999", ""):
        monkeypatch.setenv("TRINAXAI_CLI_TIMEOUT", bad)
        client.research("q", depth=1)
        assert client._post.call_args.kwargs["timeout"] == 180.0, bad


def test_the_plain_http_fallback_never_sends_credentials(monkeypatch) -> None:
    monkeypatch.setenv("TRINAXAI_ADMIN_TOKEN", "secret-admin")
    monkeypatch.setenv("TRINAXAI_DEVICE_TOKEN", "secret-device")
    server = _serve_plain_http()
    try:
        client = TrinaxAPIClient(f"https://127.0.0.1:{server.server_port}", verify_tls=None, language="en")
        assert client._request_headers["X-Admin-Token"] == "secret-admin"
        assert client._get("/health") == {"ok": True}
        assert client.base_url.startswith("http://")
        assert "X-Admin-Token" not in client._request_headers
        assert "X-TrinaxAI-Device-Token" not in client._request_headers
        assert "X-Admin-Token" not in client._client.headers
        assert client._client.headers.get("Accept-Language") == "en"  # harmless headers are kept
    finally:
        server.shutdown()
        server.server_close()
