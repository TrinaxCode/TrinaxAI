from __future__ import annotations

import json
import socket
import ssl
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.schemas.api import WebSearchConnectionTest, WebSearchSettingsUpdate
from app.services import web_search_service as web
from app.services import web_search_settings_service as settings


class _SearchResponse:
    def __init__(self, *, payload=None, text="", status_code=200, content=None):
        self._payload = payload or {}
        self.text = text
        self.status_code = status_code
        self.content = content if content is not None else text.encode()

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://search.example")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("failed", request=request, response=response)


class _RawSocket:
    def __init__(self, *, send_error: Exception | None = None):
        self.timeouts = []
        self.sent = b""
        self.closed = False
        self.send_error = send_error

    def settimeout(self, value):
        self.timeouts.append(value)

    def sendall(self, value):
        if self.send_error:
            raise self.send_error
        self.sent += value

    def close(self):
        self.closed = True


class _StartedResponse:
    def __init__(self, connection):
        self.connection = connection
        self.started = False

    def begin(self):
        self.started = True


class _BodyResponse:
    def __init__(self, body=b"", *, headers=None, status=200):
        self.status = status
        self.headers = headers or {"Content-Type": "text/plain"}
        self._body = body
        self._offset = 0
        self.closed = False

    def read(self, size):
        value = self._body[self._offset : self._offset + size]
        self._offset += len(value)
        return value

    def close(self):
        self.closed = True


class _BodyConnection:
    def __init__(self):
        self.timeouts = []
        self.closed = False

    def settimeout(self, value):
        self.timeouts.append(value)

    def close(self):
        self.closed = True


def _public_dns(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def _request():
    return SimpleNamespace()


def test_web_normalization_and_address_edge_cases(monkeypatch):
    assert web._safe_result("bad", "mailto:user@example.com", "text") is None
    assert not web._is_public_address("not-an-ip")
    assert web._is_public_address("::ffff:93.184.216.34")
    assert not web._is_loopback_address("not-an-ip")
    assert web._is_loopback_address("::ffff:127.0.0.1")
    assert web._is_loopback_hostname("service.localhost")
    assert not web._is_loopback_hostname("not-an-ip")
    assert web._is_loopback_hostname("::ffff:127.0.0.1")
    assert web._host_header("2001:db8::1", 443, "https") == "[2001:db8::1]"
    assert web._host_header("example.com", 8080, "http") == "example.com:8080"

    monkeypatch.setattr(web.socket, "getaddrinfo", _public_dns)
    scheme, host, port, path, addresses = web._validated_target("HTTPS://Example.com/a b?q=hello world")
    assert (scheme, host, port, addresses) == ("https", "example.com", 443, ["93.184.216.34"])
    assert path == "/a%20b?q=hello%20world"


def test_web_target_validation_rejects_parse_idna_and_dns_errors(monkeypatch):
    with pytest.raises(web.PageFetchError, match="invalid URL"):
        web._validated_target("https://example.com:99999")

    parsed = SimpleNamespace(
        scheme="https",
        hostname="\ud800.example",
        username=None,
        password=None,
        port=None,
        path="/",
        query="",
    )
    monkeypatch.setattr(web, "urlsplit", lambda _url: parsed)
    with pytest.raises(web.PageFetchError, match="invalid hostname"):
        web._validated_target("https://ignored.example")

    monkeypatch.setattr(web, "urlsplit", __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit)
    monkeypatch.setattr(web.socket, "getaddrinfo", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("dns")))
    with pytest.raises(web.PageFetchError, match="DNS"):
        web._validated_target("https://example.com")


def test_web_provider_validation_covers_public_local_and_failure_paths(monkeypatch):
    with pytest.raises(web.PageFetchError, match="invalid provider URL"):
        web._validated_provider_url("https://example.com:99999")
    with pytest.raises(web.PageFetchError, match="only public"):
        web._validated_provider_url("file:///tmp/search")
    with pytest.raises(web.PageFetchError, match="credentials"):
        web._validated_provider_url("https://user:pass@example.com/search?q=x")

    parsed = SimpleNamespace(
        scheme="https",
        hostname="\ud800.example",
        username=None,
        password=None,
        port=None,
        path="",
        query="",
        fragment="",
    )
    monkeypatch.setattr(web, "urlsplit", lambda _url: parsed)
    with pytest.raises(web.PageFetchError, match="invalid provider hostname"):
        web._validated_provider_url("https://ignored.example")
    monkeypatch.setattr(web, "urlsplit", __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit)

    with pytest.raises(web.PageFetchError, match="non-web provider"):
        web._validated_provider_url("https://example.com:8443")
    monkeypatch.setattr(web.socket, "getaddrinfo", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("dns")))
    with pytest.raises(web.PageFetchError, match="provider DNS"):
        web._validated_provider_url("https://example.com")
    monkeypatch.setattr(web.socket, "getaddrinfo", lambda *_args, **_kwargs: [])
    with pytest.raises(web.PageFetchError, match="no addresses"):
        web._validated_provider_url("https://example.com")

    monkeypatch.setattr(
        web.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 8080))],
    )
    assert web._validated_provider_url("http://localhost:8080/") == "http://127.0.0.1:8080"
    monkeypatch.setattr(
        web.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 8080)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 8080)),
        ],
    )
    with pytest.raises(web.PageFetchError, match="provider targets"):
        web._validated_provider_url("http://localhost:8080")
    monkeypatch.setattr(web.socket, "getaddrinfo", _public_dns)
    assert web._validated_provider_url("https://example.com") == "https://example.com"
    monkeypatch.setattr(
        web.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", 443)),
        ],
    )
    with pytest.raises(web.PageFetchError, match="provider targets"):
        web._validated_provider_url("https://example.com")


def test_web_pinned_connection_http_https_retry_and_timeout(monkeypatch):
    raw = _RawSocket()
    started = _StartedResponse
    monkeypatch.setattr(web.socket, "create_connection", lambda *_args, **_kwargs: raw)
    monkeypatch.setattr(web.http.client, "HTTPResponse", started)
    response, connection = web._open_pinned_response("http", "example.com", 80, "/x", ["93.184.216.34"], 10**9)
    assert response.started and connection is raw
    assert b"GET /x HTTP/1.1" in raw.sent
    assert b"Host: example.com" in raw.sent

    tls_raw = _RawSocket()
    tls_connection = _RawSocket()

    class _Context:
        minimum_version = None

        def wrap_socket(self, value, *, server_hostname):
            assert value is tls_raw and server_hostname == "example.com"
            return tls_connection

    context = _Context()
    monkeypatch.setattr(web.socket, "create_connection", lambda *_args, **_kwargs: tls_raw)
    monkeypatch.setattr(web.ssl, "create_default_context", lambda: context)
    response, connection = web._open_pinned_response("https", "example.com", 443, "/", ["93.184.216.34"], 10**9)
    assert response.started and connection is tls_connection
    assert context.minimum_version is ssl.TLSVersion.TLSv1_2

    failed_raw = _RawSocket(send_error=OSError("write"))
    good_raw = _RawSocket()
    sequence = iter([failed_raw, good_raw])
    monkeypatch.setattr(web.socket, "create_connection", lambda *_args, **_kwargs: next(sequence))
    monkeypatch.setattr(web.http.client, "HTTPResponse", started)
    response, connection = web._open_pinned_response("http", "example.com", 80, "/", ["a", "b"], 10**9)
    assert response.started and connection is good_raw and failed_raw.closed

    monkeypatch.setattr(
        web.socket, "create_connection", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("down"))
    )
    with pytest.raises(web.PageFetchError, match="connection failed"):
        web._open_pinned_response("http", "example.com", 80, "/", ["a"], 10**9)

    with pytest.raises(web.PageFetchError, match="timed out"):
        web._open_pinned_response("http", "example.com", 80, "/", ["a"], 0)

    timed_raw = _RawSocket()
    monkeypatch.setattr(web.socket, "create_connection", lambda *_args, **_kwargs: timed_raw)
    times = iter([0.0, 0.0, 11.0])
    monkeypatch.setattr(web.time, "monotonic", lambda: next(times))
    with pytest.raises(web.PageFetchError, match="timed out"):
        web._open_pinned_response("http", "example.com", 80, "/", ["a"], 10.0)
    assert timed_raw.closed


def test_web_limited_body_and_parser_edges():
    connection = _BodyConnection()
    assert (
        web._read_limited_body(_BodyResponse(b"abc", headers={"Content-Length": "unknown"}), connection, 10, 10**9)
        == b"abc"
    )
    with pytest.raises(web.PageFetchError, match="download limit"):
        web._read_limited_body(_BodyResponse(b"", headers={"Content-Length": "11"}), _BodyConnection(), 10, 10**9)
    with pytest.raises(web.PageFetchError, match="timed out"):
        web._read_limited_body(_BodyResponse(b"x"), _BodyConnection(), 10, 0)

    parser = web._ReadableHTMLParser()
    parser.feed(
        '<title>Page title</title><meta name="author" content="Author">'
        '<time datetime="2026-08-26T00:00:00Z"/><script><p>ignored data</p></script>'
        "<main><p>This is a sufficiently long preferred paragraph with readable content.</p></main>"
    )
    assert parser.title == "Page title"
    assert parser.author == "Author"
    assert parser.published_at.startswith("2026-08-26")
    assert "sufficiently long" in parser.text
    assert "ignored" not in parser.text
    parser.handle_starttag("form", [])
    parser.handle_starttag("p", [])
    parser.handle_endtag("p")
    parser.handle_endtag("form")

    assert web._same_host_canonical("https://example.com", "") is None
    assert web._same_host_canonical("https://example.com", "https://example.com:bad") is None
    assert web._same_host_canonical("https://example.com", "https://other.example/page") is None


def _patch_fetch(monkeypatch, response, *, url="https://example.com/page"):
    monkeypatch.setattr(
        web,
        "_validated_target",
        lambda _url: ("https", "example.com", 443, "/page", ["93.184.216.34"]),
    )
    monkeypatch.setattr(web, "_open_pinned_response", lambda *args, **kwargs: (response, _BodyConnection()))
    return url


@pytest.mark.parametrize(
    ("status", "headers", "match"),
    [
        (302, {}, "too many redirects"),
        (404, {}, "HTTP 404"),
        (200, {"Content-Type": "application/json"}, "readable HTML"),
        (200, {"Content-Type": "text/plain", "Content-Encoding": "gzip"}, "compressed"),
    ],
)
def test_web_page_fetch_rejects_redirect_status_and_media(monkeypatch, status, headers, match):
    if status == 302:
        headers = {"Location": "/next"}
        monkeypatch.setattr(web, "_PAGE_FETCH_MAX_REDIRECTS", 0)
    response = _BodyResponse(b"", status=status, headers=headers)
    with pytest.raises(web.PageFetchError, match=match):
        web.fetch_web_page(_patch_fetch(monkeypatch, response))


def test_web_page_fetch_redirect_loop_downgrade_timeout_and_transport(monkeypatch):
    response = _BodyResponse(b"", status=302, headers={"Location": "https://example.com/page"})
    with pytest.raises(web.PageFetchError, match="redirect loop"):
        web.fetch_web_page(_patch_fetch(monkeypatch, response))

    response = _BodyResponse(b"", status=302, headers={"Location": "http://example.com/page"})
    with pytest.raises(web.PageFetchError, match="downgrade"):
        web.fetch_web_page(_patch_fetch(monkeypatch, response, url="https://example.com/start"))

    monkeypatch.setattr(web.config, "WEB_SEARCH_TIMEOUT", 0)
    with pytest.raises(web.PageFetchError, match="timed out"):
        web.fetch_web_page("https://example.com/timeout")

    monkeypatch.setattr(web.config, "WEB_SEARCH_TIMEOUT", 5)
    monkeypatch.setattr(web, "_validated_target", lambda _url: ("https", "example.com", 443, "/", ["a"]))
    monkeypatch.setattr(web, "_open_pinned_response", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("socket")))
    with pytest.raises(web.PageFetchError, match="fetch failed"):
        web.fetch_web_page("https://example.com/failure")

    monkeypatch.setattr(web, "_PAGE_FETCH_MAX_REDIRECTS", -1)
    with pytest.raises(web.PageFetchError, match="too many redirects"):
        web.fetch_web_page("https://example.com/empty-loop")


def test_web_page_fetch_unknown_charset_and_short_content(monkeypatch):
    body = b"readable text " * 10
    response = _BodyResponse(body, headers={"Content-Type": "text/plain; charset=unknown-charset"})
    result = web.fetch_web_page(_patch_fetch(monkeypatch, response))
    assert result["content_scope"] == "full_page"

    response = _BodyResponse(b"short", headers={"Content-Type": "text/plain"})
    with pytest.raises(web.PageFetchError, match="enough readable"):
        web.fetch_web_page(_patch_fetch(monkeypatch, response))


def test_web_results_keep_unexpected_fetch_failures(monkeypatch):
    monkeypatch.setattr(web, "fetch_web_page", lambda _url: (_ for _ in ()).throw(ValueError("bad reader")))
    result = web.read_web_results([{"url": "https://example.com", "title": "T", "snippet": "S"}])
    assert result[0]["fetch_error"] == "page fetch failed"


def test_web_provider_searchers_and_fallbacks(monkeypatch):
    monkeypatch.setattr(web.config, "WEB_SEARCH_BRAVE_API_KEY", "brave-key")
    monkeypatch.setattr(
        web.httpx,
        "get",
        lambda *args, **kwargs: _SearchResponse(
            payload={
                "web": {
                    "results": [
                        {
                            "title": "Brave result",
                            "url": "https://example.com/brave",
                            "description": "Description",
                            "extra_snippets": ["Extra one", "Extra two", "ignored"],
                        },
                        {"title": "bad", "url": "mailto:x", "description": "bad"},
                    ]
                }
            }
        ),
    )
    assert web._search_brave("query", 5)[0]["snippet"] == "Description Extra one Extra two"
    monkeypatch.setattr(web.config, "WEB_SEARCH_BRAVE_API_KEY", "")
    with pytest.raises(web.WebSearchError, match="Brave"):
        web._search_brave("query", 5)

    monkeypatch.setattr(web.config, "WEB_SEARCH_SEARXNG_URL", "https://search.example")
    monkeypatch.setattr(web, "_validated_provider_url", lambda _url: "https://search.example")
    monkeypatch.setattr(
        web.httpx,
        "get",
        lambda *args, **kwargs: _SearchResponse(
            payload={
                "results": [{"title": "Searx", "url": "https://example.com/s", "content": "Found"}, {"url": "bad"}]
            }
        ),
    )
    assert web._search_searxng("query", 5)[0]["title"] == "Searx"
    monkeypatch.setattr(web, "_validated_provider_url", lambda _url: (_ for _ in ()).throw(web.PageFetchError("bad")))
    with pytest.raises(web.WebSearchError, match="invalid"):
        web._search_searxng("query", 5)
    monkeypatch.setattr(web, "_validated_provider_url", lambda _url: "https://search.example")
    monkeypatch.setattr(web.httpx, "get", lambda *args, **kwargs: _SearchResponse(status_code=302))
    with pytest.raises(web.WebSearchError, match="redirect"):
        web._search_searxng("query", 5)
    monkeypatch.setattr(web.config, "WEB_SEARCH_SEARXNG_URL", "")
    with pytest.raises(web.WebSearchError, match="SearXNG requires"):
        web._search_searxng("query", 5)

    instant_payload = {
        "Heading": "Instant",
        "AbstractURL": "https://example.com/instant",
        "AbstractText": "Instant abstract",
        "RelatedTopics": [
            {"Topics": [{"Text": "Topic one - details", "FirstURL": "https://example.com/one"}]},
            {"Text": "Topic two - details", "FirstURL": "https://example.com/two"},
        ],
    }
    monkeypatch.setattr(web.httpx, "get", lambda *args, **kwargs: _SearchResponse(payload=instant_payload))
    assert len(web._search_duckduckgo_instant("query", 2)) == 2


def test_web_bing_and_provider_dispatch_edges(monkeypatch):
    rss = (
        b"<rss><channel>"
        b"<item><title>One</title><link>https://example.com/one</link><description>One</description></item>"
        b"<item><title>Two</title><link>https://example.com/two</link><description>Two</description></item>"
        b"</channel></rss>"
    )
    monkeypatch.setattr(web.httpx, "get", lambda *args, **kwargs: _SearchResponse(content=rss))
    assert len(web._search_bing_rss("query", 1)) == 1

    with pytest.raises(web.WebSearchError, match="empty"):
        web.search_web("   ")
    monkeypatch.setattr(web.config, "WEB_SEARCH_PROVIDER", "disabled")
    with pytest.raises(web.WebSearchError, match="disabled"):
        web.search_web("query")

    monkeypatch.setattr(web.config, "WEB_SEARCH_PROVIDER", "auto")
    monkeypatch.setattr(web.config, "WEB_SEARCH_SEARXNG_URL", "configured")
    monkeypatch.setattr(web.config, "WEB_SEARCH_BRAVE_API_KEY", "")
    monkeypatch.setattr(web, "_search_searxng", lambda query, limit: [{"url": "https://example.com/s", "title": "S"}])
    results, provider = web.search_web("query", provider="auto")
    assert results and provider == "searxng"

    monkeypatch.setattr(web.config, "WEB_SEARCH_PROVIDER", "unknown")
    with pytest.raises(web.WebSearchError, match="Unknown"):
        web.search_web("query")


def test_web_duckduckgo_instant_fallback_success_empty_and_error(monkeypatch):
    monkeypatch.setattr(web.config, "WEB_SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setattr(web.config, "WEB_SEARCH_CACHE_SECONDS", 0)
    monkeypatch.setattr(web, "_search_duckduckgo", lambda *_args: (_ for _ in ()).throw(web.WebSearchError("blocked")))
    monkeypatch.setattr(
        web, "_search_duckduckgo_instant", lambda *_args: [{"url": "https://example.com", "title": "fallback"}]
    )
    results, provider = web.search_web("query")
    assert results and provider == "duckduckgo-instant"

    monkeypatch.setattr(web, "_search_duckduckgo_instant", lambda *_args: [])
    with pytest.raises(web.WebSearchError, match="no results"):
        web.search_web("query")
    monkeypatch.setattr(web, "_search_duckduckgo_instant", lambda *_args: (_ for _ in ()).throw(ValueError("bad json")))
    with pytest.raises(web.WebSearchError, match="failed"):
        web.search_web("query")

    monkeypatch.setattr(web.config, "WEB_SEARCH_PROVIDER", "brave")
    monkeypatch.setattr(web.config, "WEB_SEARCH_BRAVE_API_KEY", "key")
    monkeypatch.setattr(web, "_search_brave", lambda *_args: [])
    with pytest.raises(web.WebSearchError, match="no results"):
        web.search_web("query")


@pytest.mark.asyncio
async def test_web_settings_remaining_error_and_update_paths(monkeypatch, tmp_path: Path):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_PATH", path)
    for name in settings._ENV.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(settings, "authorize_system", lambda _request: None)

    original_unlink = Path.unlink

    def fail_tmp_unlink(candidate, *args, **kwargs):
        if candidate == path.with_suffix(".tmp"):
            raise OSError("cleanup")
        return original_unlink(candidate, *args, **kwargs)

    original_replace = settings.os.replace
    monkeypatch.setattr(settings.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("write")))
    monkeypatch.setattr(Path, "unlink", fail_tmp_unlink)
    with pytest.raises(HTTPException, match="settings_write_failed"):
        settings._write({"preferred_provider": "auto"})

    monkeypatch.setattr(settings.os, "replace", original_replace)
    monkeypatch.setattr(Path, "unlink", original_unlink)
    monkeypatch.setattr(settings.web_search_service, "_validated_provider_url", lambda _url: "ok")
    assert settings._validate_searxng_url(" https://example.com/ ") == "https://example.com"
    assert settings._validate_searxng_url("   ") == ""

    response = await settings.update_web_search_settings(WebSearchSettingsUpdate(enabled=False), _request())
    assert response["enabled"] is False

    monkeypatch.setenv("TRINAXAI_BRAVE_SEARCH_API_KEY", "managed")
    with pytest.raises(HTTPException) as exc:
        await settings.update_web_search_settings(WebSearchSettingsUpdate(brave_api_key="new"), _request())
    assert exc.value.status_code == 409
    monkeypatch.setenv("TRINAXAI_SEARXNG_URL", "managed")
    with pytest.raises(HTTPException) as exc:
        await settings.update_web_search_settings(
            WebSearchSettingsUpdate(searxng_url="https://example.com"), _request()
        )
    assert exc.value.status_code == 409

    monkeypatch.delenv("TRINAXAI_BRAVE_SEARCH_API_KEY")
    with pytest.raises(HTTPException) as exc:
        await settings.delete_web_search_credential("unknown", _request())
    assert exc.value.status_code == 404
    monkeypatch.setenv("TRINAXAI_BRAVE_SEARCH_API_KEY", "managed")
    with pytest.raises(HTTPException) as exc:
        await settings.delete_web_search_credential("brave", _request())
    assert exc.value.status_code == 409

    monkeypatch.delenv("TRINAXAI_BRAVE_SEARCH_API_KEY")
    monkeypatch.delenv("TRINAXAI_SEARXNG_URL")
    path.unlink(missing_ok=True)
    await settings.reset_web_search_settings(_request())
    path.write_text("{}")
    original_reset_unlink = Path.unlink

    def fail_reset(candidate, *args, **kwargs):
        if candidate == path:
            raise OSError("reset")
        return original_reset_unlink(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_reset)
    with pytest.raises(HTTPException, match="settings_reset_failed"):
        await settings.reset_web_search_settings(_request())


@pytest.mark.asyncio
async def test_web_settings_connection_provider_configuration_and_generic_error(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "authorize_system", lambda _request: None)
    for name in settings._ENV.values():
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "settings.json").write_text(json.dumps({"preferred_provider": "searxng"}))
    with pytest.raises(HTTPException) as exc:
        await settings.test_web_search_connection(WebSearchConnectionTest(query="q", provider="searxng"), _request())
    assert exc.value.status_code == 424

    (tmp_path / "settings.json").write_text(json.dumps({"preferred_provider": "brave", "brave_api_key": "key"}))
    monkeypatch.setattr(
        settings.web_search_service,
        "search_web",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(web.WebSearchError("down")),
    )
    with pytest.raises(HTTPException) as exc:
        await settings.test_web_search_connection(WebSearchConnectionTest(query="q", provider="brave"), _request())
    assert exc.value.status_code == 502
