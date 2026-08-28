from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest

import config
from app.services import web_search_service as web
from app.services import web_search_settings_service as settings


class _Response:
    def __init__(self, payload=None, *, text="", content=b"") -> None:
        self._payload = payload or {}
        self.text = text
        self.content = content
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_result_validation_authority_and_ranking() -> None:
    assert web._safe_result("bad", "file:///etc/passwd", "secret") is None
    assert web._safe_result("", "https://example.com/path", "  useful  ") == {
        "title": "example.com",
        "url": "https://example.com/path",
        "snippet": "useful",
    }
    ranked = web._rank_results(
        [
            {"title": "Blog", "url": "https://example.com", "snippet": "one"},
            {"title": "Agency", "url": "https://agency.gov", "snippet": "two"},
        ],
        "query",
    )
    assert [row["authority"] for row in ranked] == ["primary", "secondary"]
    assert web._source_authority("https://service.gob.mx") == "primary"


def test_public_address_and_target_normalization(monkeypatch) -> None:
    assert not web._is_public_address("not-an-ip")
    assert not web._is_public_address("::ffff:127.0.0.1")
    assert web._is_public_address("93.184.216.34")
    monkeypatch.setattr(
        web.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )

    target = web._validated_target("https://Example.COM/a path?q=hello world")

    assert target[:4] == ("https", "example.com", 443, "/a%20path?q=hello%20world")
    assert target[4] == ["93.184.216.34"]
    assert web._host_header("2001:4860:4860::8888", 443, "https") == "[2001:4860:4860::8888]"

    monkeypatch.setattr(
        web.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("dns")),
    )
    with pytest.raises(web.PageFetchError, match="DNS resolution failed"):
        web._validated_target("https://example.com")


def test_limited_body_checks_headers_timeout_and_size(monkeypatch) -> None:
    connection = SimpleNamespace(settimeout=lambda _value: None)
    oversized = SimpleNamespace(
        headers={"Content-Length": "100"},
        read=lambda _size: b"",
    )
    with pytest.raises(web.PageFetchError, match="download limit"):
        web._read_limited_body(oversized, connection, 10, web.time.monotonic() + 1)

    invalid_header = SimpleNamespace(
        headers={"Content-Length": "invalid"},
        read=lambda _size: b"ok",
    )
    calls = 0

    def read_once(_size):
        nonlocal calls
        calls += 1
        return b"ok" if calls == 1 else b""

    invalid_header.read = read_once
    assert web._read_limited_body(invalid_header, connection, 10, web.time.monotonic() + 1) == b"ok"

    monkeypatch.setattr(web.time, "monotonic", lambda: 10)
    with pytest.raises(web.PageFetchError, match="timed out"):
        web._read_limited_body(
            SimpleNamespace(headers={}, read=lambda _size: b""),
            connection,
            10,
            9,
        )


def test_canonical_url_stays_on_secure_origin() -> None:
    assert web._same_host_canonical("https://example.com/article", "/canonical") == "https://example.com/canonical"
    assert web._same_host_canonical("https://example.com/article", "http://example.com/insecure") is None
    assert web._same_host_canonical("https://example.com/article", "https://other.example/article") is None
    assert web._same_host_canonical("https://example.com", "") is None


def test_page_reader_rejects_status_media_encoding_and_short_text(monkeypatch) -> None:
    monkeypatch.setattr(
        web,
        "_validated_target",
        lambda _url: ("https", "example.com", 443, "/", ["93.184.216.34"]),
    )

    class Page:
        def __init__(self, status, headers):
            self.status = status
            self.headers = headers

        def close(self):
            return None

    connection = SimpleNamespace(close=lambda: None)

    for page, message in [
        (Page(500, {"Content-Type": "text/html"}), "HTTP 500"),
        (Page(200, {"Content-Type": "application/json"}), "not readable"),
        (
            Page(
                200,
                {"Content-Type": "text/html", "Content-Encoding": "gzip"},
            ),
            "compressed",
        ),
    ]:
        monkeypatch.setattr(web, "_open_pinned_response", lambda *_args, page=page, **_kwargs: (page, connection))
        with pytest.raises(web.PageFetchError, match=message):
            web.fetch_web_page("https://example.com")

    short = Page(200, {"Content-Type": "text/plain; charset=unknown-charset"})
    monkeypatch.setattr(
        web,
        "_open_pinned_response",
        lambda *_args, **_kwargs: (short, connection),
    )
    monkeypatch.setattr(web, "_read_limited_body", lambda *_args: b"too short")
    with pytest.raises(web.PageFetchError, match="enough readable text"):
        web.fetch_web_page("https://example.com")


def test_unexpected_page_failure_keeps_a_safe_snippet(monkeypatch) -> None:
    monkeypatch.setattr(
        web,
        "fetch_web_page",
        lambda _url: (_ for _ in ()).throw(RuntimeError("private diagnostic")),
    )

    results = web.read_web_results(
        [
            {
                "title": "Result",
                "url": "https://example.com",
                "snippet": "Safe snippet",
            }
        ]
    )

    assert results[0]["content"] == "Safe snippet"
    assert results[0]["fetch_error"] == "page fetch failed"
    assert "private diagnostic" not in str(results[0])


def test_brave_and_searxng_normalize_provider_results(monkeypatch) -> None:
    monkeypatch.setattr(config, "WEB_SEARCH_BRAVE_API_KEY", "")
    with pytest.raises(web.WebSearchError, match="requires"):
        web._search_brave("query", 2)
    monkeypatch.setattr(config, "WEB_SEARCH_SEARXNG_URL", "")
    with pytest.raises(web.WebSearchError, match="requires"):
        web._search_searxng("query", 2)

    monkeypatch.setattr(config, "WEB_SEARCH_BRAVE_API_KEY", "key")
    monkeypatch.setattr(config, "WEB_SEARCH_SEARXNG_URL", "https://search.example")
    monkeypatch.setattr(
        web.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    responses = iter(
        [
            _Response(
                {
                    "web": {
                        "results": [
                            {
                                "title": "Brave",
                                "url": "https://example.com/brave",
                                "description": "Description",
                                "extra_snippets": ["Extra"],
                            }
                        ]
                    }
                }
            ),
            _Response(
                {
                    "results": [
                        {
                            "title": "SearX",
                            "url": "https://example.com/searx",
                            "content": "Content",
                        }
                    ]
                }
            ),
        ]
    )
    monkeypatch.setattr(web.httpx, "get", lambda *_args, **_kwargs: next(responses))

    assert web._search_brave("query", 2)[0]["snippet"] == "Description Extra"
    assert web._search_searxng("query", 2)[0]["title"] == "SearX"


def test_searxng_provider_rejects_private_targets_and_redirects(monkeypatch) -> None:
    monkeypatch.setattr(config, "WEB_SEARCH_SEARXNG_URL", "http://127.0.0.1")
    with pytest.raises(web.WebSearchError, match="not public"):
        web._search_searxng("query", 1)

    monkeypatch.setattr(config, "WEB_SEARCH_SEARXNG_URL", "https://search.example")
    monkeypatch.setattr(
        web.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    captured = {}

    class Redirect:
        status_code = 302

        def raise_for_status(self):
            return None

    def fake_get(*_args, **kwargs):
        captured.update(kwargs)
        return Redirect()

    monkeypatch.setattr(web.httpx, "get", fake_get)
    with pytest.raises(web.WebSearchError, match="redirect"):
        web._search_searxng("query", 1)
    assert captured["follow_redirects"] is False


def test_searxng_accepts_only_documented_loopback_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        web.socket,
        "getaddrinfo",
        lambda _host, port, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))],
    )
    assert web._validated_provider_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"
    assert settings._validate_searxng_url("http://127.0.0.1:8080/") == "http://127.0.0.1:8080"
    monkeypatch.setattr(config, "WEB_SEARCH_SEARXNG_URL", "http://127.0.0.1:8080")
    requested = {}

    def fake_get(url, **kwargs):
        requested.update(url=url, **kwargs)
        return _Response({"results": []})

    monkeypatch.setattr(web.httpx, "get", fake_get)
    assert web._search_searxng("query", 1) == []
    assert requested["url"] == "http://127.0.0.1:8080/search"

    for url in ("http://127.0.0.1", "http://127.0.0.1:8081", "http://10.0.0.7:8080"):
        with pytest.raises(web.PageFetchError):
            web._validated_provider_url(url)


def test_searxng_loopback_dns_rebinding_stays_blocked(monkeypatch) -> None:
    monkeypatch.setattr(config, "WEB_SEARCH_SEARXNG_URL", "http://localhost:8080")
    monkeypatch.setattr(
        web.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 8080)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 8080)),
        ],
    )

    with pytest.raises(web.WebSearchError, match="not public"):
        web._search_searxng("query", 1)


def test_duckduckgo_instant_flattens_topics(monkeypatch) -> None:
    monkeypatch.setattr(
        web.httpx,
        "get",
        lambda *_args, **_kwargs: _Response(
            {
                "Heading": "Topic",
                "AbstractURL": "https://example.com/topic",
                "AbstractText": "Abstract",
                "RelatedTopics": [
                    {
                        "Topics": [
                            {
                                "Text": "Related - detail",
                                "FirstURL": "https://example.com/related",
                            }
                        ]
                    }
                ],
            }
        ),
    )

    results = web._search_duckduckgo_instant("query", 2)

    assert [row["title"] for row in results] == ["Topic", "Related"]


@pytest.mark.parametrize(
    ("query", "provider", "message"),
    [
        ("", None, "empty"),
        ("query", "disabled", "disabled"),
        ("query", "unknown", "Unknown"),
    ],
)
def test_search_rejects_invalid_requests(monkeypatch, query, provider, message) -> None:
    monkeypatch.setattr(config, "WEB_SEARCH_PROVIDER", provider or "auto")
    with pytest.raises(web.WebSearchError, match=message):
        web.search_web(query, provider=provider)


def test_search_uses_instant_fallback_and_reports_total_failure(monkeypatch) -> None:
    monkeypatch.setattr(config, "WEB_SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setattr(
        web,
        "_search_duckduckgo",
        lambda *_args: (_ for _ in ()).throw(web.WebSearchError("blocked")),
    )
    monkeypatch.setattr(
        web,
        "_search_duckduckgo_instant",
        lambda *_args: [
            {
                "title": "Fallback",
                "url": "https://example.com",
                "snippet": "answer",
            }
        ],
    )

    results, provider = web.search_web("unique fallback query")
    assert provider == "duckduckgo-instant"
    assert results[0]["title"] == "Fallback"

    monkeypatch.setattr(
        web,
        "_search_duckduckgo_instant",
        lambda *_args: (_ for _ in ()).throw(ValueError("bad response")),
    )
    with pytest.raises(web.WebSearchError, match="All configured"):
        web.search_web("another unique failed query")
