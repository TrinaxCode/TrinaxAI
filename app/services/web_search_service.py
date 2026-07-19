"""Opt-in web search providers used to ground TrinaxAI answers.

The default provider uses DuckDuckGo's HTML results so a local installation can
work without an account. Brave Search and a self-hosted SearXNG instance are
supported for more predictable production use.
"""

from __future__ import annotations

import html
import http.client
import ipaddress
import logging
import re
import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse, urlsplit

import httpx
from defusedxml import ElementTree as ET

import config

LOG = logging.getLogger("trinaxai.web_search")

_SEARCH_CACHE: dict[tuple[Any, ...], tuple[float, list[dict[str, str]], str]] = {}
_SEARCH_CACHE_LOCK = threading.Lock()

# Page reads deliberately do not use httpx's normal resolver: resolving once
# and connecting by hostname leaves a DNS-rebinding window between validation
# and the actual connection.  We resolve every candidate, reject the whole host
# if *any* answer is non-public, and connect directly to one of the validated
# addresses while preserving TLS SNI/certificate validation for the hostname.
_PAGE_FETCH_MAX_BYTES = 1_000_000
_PAGE_FETCH_MAX_TEXT_CHARS = 40_000
_PAGE_FETCH_MAX_REDIRECTS = 3
_PAGE_FETCH_TIMEOUT_SECONDS = 5.0
_PAGE_FETCH_MAX_RESULTS = 8
_PAGE_FETCH_DEFAULT_RESULTS = 3
_PAGE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8",
    "Accept-Encoding": "identity",
    "Connection": "close",
    "User-Agent": "Mozilla/5.0 (compatible; TrinaxAI/1.0; safe research reader)",
}

_WEB_INTENT_PATTERNS = (
    r"\b(?:busca|buscar|búscalo|buscarlo|investiga|consulta|verifica)\b.{0,35}\b(?:internet|web|en\s+línea|online)\b",
    r"\b(?:internet|web|en\s+línea|online)\b.{0,35}\b(?:busca|buscar|investiga|consulta|verifica)\b",
    r"\b(?:search|look\s+up|research|check|verify)\b.{0,35}\b(?:the\s+)?(?:internet|web|online)\b",
    r"\b(?:internet|web|online)\b.{0,35}\b(?:search|look\s+up|research|check|verify)\b",
    r"^\s*/web\b",
)


class WebSearchError(RuntimeError):
    """A readable provider/configuration error safe to surface to the user."""


def wants_web_search(query: str) -> bool:
    """Return True only when the user explicitly asks to search online."""
    normalized = " ".join(str(query or "").split()).lower()
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in _WEB_INTENT_PATTERNS)


def _clean_text(value: Any, limit: int = 1200) -> str:
    text = html.unescape(re.sub(r"\s+", " ", str(value or ""))).strip()
    return text[:limit]


def _safe_result(title: Any, url: Any, snippet: Any) -> dict[str, str] | None:
    cleaned_url = html.unescape(str(url or "")).strip()
    parsed = urlparse(cleaned_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return {
        "title": _clean_text(title, 300) or parsed.netloc,
        "url": cleaned_url,
        "snippet": _clean_text(snippet),
    }


def _source_authority(url: str) -> str:
    """Classify only unambiguous government publishers as primary.

    A hostname containing a query token or a title saying "official" is not
    evidence of provenance.  Most pages therefore remain secondary; callers
    can still inspect/cite them without TrinaxAI overclaiming authority.
    """
    host = (urlparse(url).hostname or "").rstrip(".").casefold()
    labels = host.split(".")
    government_suffix = bool(labels) and labels[-1] in {"gov", "mil"}
    country_government_suffix = len(labels) >= 2 and len(labels[-1]) == 2 and labels[-2] in {"gov", "gob", "mil"}
    return "primary" if government_suffix or country_government_suffix else "secondary"


def _rank_results(results: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    """Put conservatively identified primary publishers first."""
    del query  # Kept in the signature for compatibility with older callers.

    def authority_score(result: dict[str, str]) -> int:
        return 1 if _source_authority(result["url"]) == "primary" else 0

    ranked = []
    for result in results:
        annotated = dict(result)
        annotated["authority"] = _source_authority(result["url"])
        ranked.append(annotated)

    def authority(item: tuple[int, dict[str, str]]) -> tuple[int, int]:
        index, result = item
        return (-authority_score(result), index)

    return [result for _, result in sorted(enumerate(ranked), key=authority)]


class PageFetchError(RuntimeError):
    """A safe, terse explanation for why a result stayed snippet-only."""


def _is_public_address(address: str) -> bool:
    """Return whether an IP is globally routable and safe for web retrieval."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(ip.is_global) and not any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


def _validated_target(url: str) -> tuple[str, str, int, str, list[str]]:
    """Normalize a URL and return hostname/port/request-target/public IPs."""
    try:
        parsed = urlsplit(str(url or "").strip())
        port = parsed.port
    except ValueError as exc:
        raise PageFetchError("invalid URL") from exc
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise PageFetchError("only public http/https URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise PageFetchError("URLs with credentials are not allowed")
    try:
        hostname = parsed.hostname.rstrip(".").encode("idna").decode("ascii").casefold()
    except (UnicodeError, ValueError) as exc:
        raise PageFetchError("invalid hostname") from exc
    if not hostname or hostname == "localhost" or hostname.endswith(".localhost"):
        raise PageFetchError("local/private targets are blocked")
    expected_port = 443 if scheme == "https" else 80
    port = port or expected_port
    if port != expected_port:
        raise PageFetchError("non-web ports are blocked")
    try:
        rows = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise PageFetchError("DNS resolution failed") from exc
    addresses = list(dict.fromkeys(str(row[4][0]).split("%", 1)[0] for row in rows))
    # Reject mixed public/private responses rather than silently choosing the
    # public answer. This closes common DNS-rebinding/multi-answer SSRF tricks.
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise PageFetchError("local/private targets are blocked")
    raw_path = parsed.path or "/"
    path = quote(raw_path, safe="/%:@!$&'()*+,;=-._~")
    if parsed.query:
        path += "?" + quote(parsed.query, safe="=&;%:+,/?@!$'()*-._~")
    return scheme, hostname, port, path, addresses


def _host_header(hostname: str, port: int, scheme: str) -> str:
    host = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if scheme == "https" else 80
    return host if port == default_port else f"{host}:{port}"


def _open_pinned_response(
    scheme: str,
    hostname: str,
    port: int,
    path: str,
    addresses: list[str],
    deadline: float,
) -> tuple[http.client.HTTPResponse, socket.socket]:
    """Connect to a prevalidated address and return a started HTTP response."""
    last_error: OSError | ssl.SSLError | None = None
    for address in addresses:
        raw_socket: socket.socket | None = None
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PageFetchError("page fetch timed out")
            raw_socket = socket.create_connection((address, port), timeout=remaining)
            raw_socket.settimeout(max(0.1, deadline - time.monotonic()))
            connection: socket.socket
            if scheme == "https":
                context = ssl.create_default_context()
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                connection = context.wrap_socket(raw_socket, server_hostname=hostname)
            else:
                connection = raw_socket
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PageFetchError("page fetch timed out")
            connection.settimeout(max(0.1, remaining))
            request_headers = {**_PAGE_HEADERS, "Host": _host_header(hostname, port, scheme)}
            request = [f"GET {path} HTTP/1.1", *(f"{key}: {value}" for key, value in request_headers.items())]
            connection.sendall(("\r\n".join(request) + "\r\n\r\n").encode("ascii"))
            response = http.client.HTTPResponse(connection)
            response.begin()
            return response, connection
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            last_error = exc
            if raw_socket is not None:
                raw_socket.close()
        except PageFetchError:
            if raw_socket is not None:
                raw_socket.close()
            raise
    raise PageFetchError("connection failed") from last_error


def _read_limited_body(
    response: http.client.HTTPResponse,
    connection: socket.socket,
    max_bytes: int,
    deadline: float,
) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise PageFetchError("page exceeds the download limit")
        except ValueError:
            pass
    body = bytearray()
    while len(body) <= max_bytes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PageFetchError("page fetch timed out")
        connection.settimeout(max(0.1, remaining))
        chunk = response.read(min(64 * 1024, max_bytes + 1 - len(body)))
        if not chunk:
            break
        body.extend(chunk)
    if len(body) > max_bytes:
        raise PageFetchError("page exceeds the download limit")
    return bytes(body)


class _ReadableHTMLParser(HTMLParser):
    """Small, dependency-free metadata and readable-text extractor."""

    _BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "blockquote", "pre", "td", "th"}
    _IGNORED_TAGS = {"script", "style", "noscript", "svg", "canvas", "template", "form", "nav", "footer", "aside"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.author = ""
        self.published_at = ""
        self.canonical = ""
        self._ignored_depth = 0
        self._title_depth = 0
        self._preferred_depth = 0
        self._block_depth = 0
        self._current: list[str] = []
        self._preferred_blocks: list[str] = []
        self._fallback_blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        values = {key.casefold(): (value or "") for key, value in attrs}
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._title_depth += 1
        if tag in {"main", "article"}:
            self._preferred_depth += 1
        if tag in self._BLOCK_TAGS:
            if self._block_depth == 0:
                self._current = []
            self._block_depth += 1
        if tag == "meta":
            key = (values.get("name") or values.get("property") or values.get("itemprop") or "").casefold()
            content = _clean_text(values.get("content"), 500)
            if content and key in {"author", "article:author", "byl"} and not self.author:
                self.author = content
            if (
                content
                and key in {"article:published_time", "date", "datepublished", "datecreated", "publishdate", "pubdate"}
                and not self.published_at
            ):
                self.published_at = content
        elif tag == "link" and "canonical" in values.get("rel", "").casefold().split():
            self.canonical = values.get("href", "")[:2048]
        elif tag == "time" and not self.published_at:
            self.published_at = _clean_text(values.get("datetime"), 200)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() not in self._IGNORED_TAGS:
            self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        cleaned = _clean_text(data, 5000)
        if not cleaned:
            return
        if self._title_depth and not self.title:
            self.title = cleaned[:300]
        if self._block_depth:
            self._current.append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self._IGNORED_TAGS:
            self._ignored_depth = max(0, self._ignored_depth - 1)
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._title_depth = max(0, self._title_depth - 1)
        if tag in self._BLOCK_TAGS and self._block_depth:
            self._block_depth -= 1
            if self._block_depth == 0:
                block = _clean_text(" ".join(self._current), 8000)
                if len(block) >= 20:
                    target = self._preferred_blocks if self._preferred_depth else self._fallback_blocks
                    target.append(block)
                self._current = []
        if tag in {"main", "article"}:
            self._preferred_depth = max(0, self._preferred_depth - 1)

    @property
    def text(self) -> str:
        blocks = self._preferred_blocks or self._fallback_blocks
        return "\n\n".join(blocks)[:_PAGE_FETCH_MAX_TEXT_CHARS]


def _same_host_canonical(base_url: str, candidate: str) -> str | None:
    """Accept canonical metadata only when it stays on the fetched hostname."""
    if not candidate:
        return None
    value = urljoin(base_url, html.unescape(candidate).strip())
    try:
        base = urlsplit(base_url)
        parsed = urlsplit(value)
        candidate_port = parsed.port or (443 if parsed.scheme.casefold() == "https" else 80)
    except ValueError:
        return None
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.hostname.rstrip(".").casefold() != (base.hostname or "").rstrip(".").casefold()
        or candidate_port != (443 if parsed.scheme.casefold() == "https" else 80)
        or (base.scheme.casefold() == "https" and parsed.scheme.casefold() != "https")
    ):
        return None
    return value[:2048]


def fetch_web_page(url: str) -> dict[str, str]:
    """Read one public HTML page through a pinned, bounded connection."""
    current_url = str(url or "").strip()
    visited: set[str] = set()
    started = time.monotonic()
    for redirect_count in range(_PAGE_FETCH_MAX_REDIRECTS + 1):
        if current_url in visited:
            raise PageFetchError("redirect loop")
        visited.add(current_url)
        elapsed = time.monotonic() - started
        remaining = min(_PAGE_FETCH_TIMEOUT_SECONDS, config.WEB_SEARCH_TIMEOUT) - elapsed
        if remaining <= 0:
            raise PageFetchError("page fetch timed out")
        scheme, hostname, port, path, addresses = _validated_target(current_url)
        response: http.client.HTTPResponse | None = None
        connection: socket.socket | None = None
        try:
            deadline = started + min(_PAGE_FETCH_TIMEOUT_SECONDS, config.WEB_SEARCH_TIMEOUT)
            response, connection = _open_pinned_response(scheme, hostname, port, path, addresses, deadline)
            if response.status in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location or redirect_count >= _PAGE_FETCH_MAX_REDIRECTS:
                    raise PageFetchError("too many redirects")
                next_url = urljoin(current_url, location)
                if scheme == "https" and urlsplit(next_url).scheme.casefold() != "https":
                    raise PageFetchError("HTTPS downgrade redirect blocked")
                current_url = next_url
                continue
            if response.status < 200 or response.status >= 300:
                raise PageFetchError(f"page returned HTTP {response.status}")
            content_type = (response.headers.get("Content-Type") or "").casefold()
            media_type = content_type.split(";", 1)[0].strip()
            if media_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                raise PageFetchError("page is not readable HTML/text")
            encoding = (response.headers.get("Content-Encoding") or "identity").casefold().strip()
            if encoding not in {"", "identity"}:
                raise PageFetchError("compressed response was not requested")
            body = _read_limited_body(response, connection, _PAGE_FETCH_MAX_BYTES, deadline)
            charset_match = re.search(r"charset\s*=\s*[\"']?([a-z0-9._-]+)", content_type)
            charset = charset_match.group(1) if charset_match else "utf-8"
            try:
                decoded = body.decode(charset, errors="replace")
            except LookupError:
                decoded = body.decode("utf-8", errors="replace")
            parser = _ReadableHTMLParser()
            parser.feed(decoded)
            text = parser.text if media_type != "text/plain" else _clean_text(decoded, _PAGE_FETCH_MAX_TEXT_CHARS)
            if len(text) < 80:
                raise PageFetchError("page did not contain enough readable text")
            return {
                "url": current_url,
                "canonical_url": _same_host_canonical(current_url, parser.canonical) or current_url,
                "title": _clean_text(parser.title, 300),
                "author": _clean_text(parser.author, 300),
                "published_at": _clean_text(parser.published_at, 200),
                "content": text,
                "content_scope": "full_page",
            }
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise PageFetchError("page fetch failed") from exc
        finally:
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()
    raise PageFetchError("too many redirects")


def read_web_results(
    results: list[dict[str, str]],
    *,
    limit: int = _PAGE_FETCH_DEFAULT_RESULTS,
) -> list[dict[str, str]]:
    """Enrich up to 3-8 search hits; safely retain snippets on failure."""
    page_limit = max(3, min(int(limit), _PAGE_FETCH_MAX_RESULTS))
    enriched: list[dict[str, str]] = []
    fetch_targets: list[tuple[int, str]] = []
    for index, result in enumerate(results):
        item = dict(result)
        search_url = item.get("url", "")
        item["search_url"] = search_url
        item.setdefault("authority", _source_authority(item.get("url", "")))
        item["content_scope"] = "snippet_only"
        item["content"] = item.get("snippet", "") or item.get("title", "")
        item["fetch_error"] = "not fetched (result limit)"
        if index < page_limit:
            fetch_targets.append((index, item.get("url", "")))
            item["fetch_error"] = "page fetch pending"
        enriched.append(item)

    # Page reads are bounded and I/O-only. Give every allowed target a worker
    # so 5-8 slow pages need one timeout wave instead of two.
    with ThreadPoolExecutor(max_workers=min(_PAGE_FETCH_MAX_RESULTS, len(fetch_targets) or 1)) as executor:
        pending = {executor.submit(fetch_web_page, url): index for index, url in fetch_targets}
        for future in as_completed(pending):
            index = pending[future]
            try:
                page = future.result()
            except PageFetchError as exc:
                enriched[index]["fetch_error"] = str(exc)
            except Exception as exc:  # noqa: BLE001 - one bad page must not abort the research pass
                LOG.warning("Unexpected page-reader failure (%s)", type(exc).__name__)
                enriched[index]["fetch_error"] = "page fetch failed"
            else:
                enriched[index].update(page)
                enriched[index]["authority"] = _source_authority(page.get("url", ""))
                enriched[index]["title"] = page.get("title") or enriched[index].get("title", "")
                enriched[index]["fetch_error"] = ""
    return enriched


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._capture: str | None = None
        self._href = ""
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if "result__a" in classes:
            self._capture, self._href, self._parts = "title", values.get("href") or "", []
        elif "result__snippet" in classes:
            self._capture, self._href, self._parts = "snippet", values.get("href") or "", []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._capture:
            return
        text = _clean_text("".join(self._parts))
        url = self._decode_url(self._href)
        if self._capture == "title":
            result = _safe_result(text, url, "")
            if result:
                self.results.append(result)
        elif self.results:
            self.results[-1]["snippet"] = text
        self._capture, self._href, self._parts = None, "", []

    @staticmethod
    def _decode_url(value: str) -> str:
        if value.startswith("//"):
            value = f"https:{value}"
        parsed = urlparse(html.unescape(value))
        redirect = parse_qs(parsed.query).get("uddg")
        return unquote(redirect[0]) if redirect else value


def _search_brave(query: str, limit: int) -> list[dict[str, str]]:
    if not config.WEB_SEARCH_BRAVE_API_KEY:
        raise WebSearchError("Brave Search requires TRINAXAI_BRAVE_SEARCH_API_KEY.")
    response = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query[:400], "count": limit, "safesearch": "moderate", "extra_snippets": "true"},
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": config.WEB_SEARCH_BRAVE_API_KEY,
        },
        timeout=config.WEB_SEARCH_TIMEOUT,
        follow_redirects=True,
    )
    response.raise_for_status()
    rows = (response.json().get("web") or {}).get("results") or []
    results = []
    for row in rows:
        extra = row.get("extra_snippets") or []
        snippet = " ".join([str(row.get("description") or ""), *(str(item) for item in extra[:2])])
        result = _safe_result(row.get("title"), row.get("url"), snippet)
        if result:
            results.append(result)
    return results[:limit]


def _search_searxng(query: str, limit: int) -> list[dict[str, str]]:
    if not config.WEB_SEARCH_SEARXNG_URL:
        raise WebSearchError("SearXNG requires TRINAXAI_SEARXNG_URL.")
    response = httpx.get(
        f"{config.WEB_SEARCH_SEARXNG_URL.rstrip('/')}/search",
        params={"q": query, "format": "json", "safesearch": 1},
        headers={"Accept": "application/json"},
        timeout=config.WEB_SEARCH_TIMEOUT,
        follow_redirects=True,
    )
    response.raise_for_status()
    results = []
    for row in response.json().get("results") or []:
        result = _safe_result(row.get("title"), row.get("url"), row.get("content"))
        if result:
            results.append(result)
    return results[:limit]


def _search_duckduckgo(query: str, limit: int) -> list[dict[str, str]]:
    response = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Mozilla/5.0 (compatible; TrinaxAI/1.0; local web search)",
        },
        timeout=config.WEB_SEARCH_TIMEOUT,
        follow_redirects=True,
    )
    response.raise_for_status()
    status_code = int(getattr(response, "status_code", 200))
    lower_body = response.text.lower()
    if status_code != 200 or "anomaly.js" in lower_body or "bots use duckduckgo" in lower_body:
        raise WebSearchError(
            "DuckDuckGo temporarily blocked automated searches. Configure Brave Search or SearXNG for reliable web access."
        )
    parser = _DuckDuckGoParser()
    parser.feed(response.text)
    return parser.results[:limit]


def _search_duckduckgo_instant(query: str, limit: int) -> list[dict[str, str]]:
    """Use DuckDuckGo's JSON knowledge endpoint as a no-key fallback."""
    response = httpx.get(
        "https://api.duckduckgo.com/",
        params={"q": query[:400], "format": "json", "no_html": 1, "skip_disambig": 0},
        headers={"Accept": "application/json"},
        timeout=min(config.WEB_SEARCH_TIMEOUT, 6.0),
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    results: list[dict[str, str]] = []
    abstract = _safe_result(payload.get("Heading"), payload.get("AbstractURL"), payload.get("AbstractText"))
    if abstract and abstract.get("snippet"):
        results.append(abstract)
    flattened: list[dict[str, Any]] = []
    for topic in payload.get("RelatedTopics") or []:
        if isinstance(topic, dict):
            flattened.extend(topic.get("Topics") or [topic])
    for topic in flattened:
        text = topic.get("Text") or ""
        result = _safe_result(text.split(" - ", 1)[0], topic.get("FirstURL"), text)
        if result:
            results.append(result)
        if len(results) >= limit:
            break
    return results[:limit]


def _search_bing_rss(query: str, limit: int) -> list[dict[str, str]]:
    """No-key fallback using Bing's documented RSS-shaped search output."""
    response = httpx.get(
        "https://www.bing.com/search",
        params={"q": query[:400], "format": "rss"},
        headers={"Accept": "application/rss+xml, application/xml;q=0.9"},
        timeout=min(config.WEB_SEARCH_TIMEOUT, 7.0),
        follow_redirects=True,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    results: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        result = _safe_result(
            item.findtext("title"),
            item.findtext("link"),
            re.sub(r"<[^>]+>", " ", item.findtext("description") or ""),
        )
        if result:
            results.append(result)
        if len(results) >= limit:
            break
    return results


def configured_provider() -> str:
    provider = config.WEB_SEARCH_PROVIDER
    if provider != "auto":
        return provider
    if config.WEB_SEARCH_BRAVE_API_KEY:
        return "brave"
    if config.WEB_SEARCH_SEARXNG_URL:
        return "searxng"
    return "duckduckgo"


def search_web(
    query: str, limit: int | None = None, *, provider: str | None = None
) -> tuple[list[dict[str, str]], str]:
    """Search the web and return normalized, deduplicated results + provider."""
    clean_query = " ".join(str(query or "").split())
    if not clean_query:
        raise WebSearchError("The web search query is empty.")
    configured = provider or config.WEB_SEARCH_PROVIDER
    if configured == "disabled":
        raise WebSearchError("Web search is disabled by TRINAXAI_WEB_SEARCH_PROVIDER.")
    max_results = max(1, min(int(limit or config.WEB_SEARCH_MAX_RESULTS), 10))
    cache_key = (
        clean_query.casefold(),
        max_results,
        configured,
        bool(config.WEB_SEARCH_BRAVE_API_KEY),
        config.WEB_SEARCH_SEARXNG_URL,
    )
    if config.WEB_SEARCH_CACHE_SECONDS > 0:
        with _SEARCH_CACHE_LOCK:
            cached = _SEARCH_CACHE.get(cache_key)
            if cached and time.monotonic() - cached[0] <= config.WEB_SEARCH_CACHE_SECONDS:
                return [dict(item) for item in cached[1]], cached[2]
    searchers = {
        "brave": _search_brave,
        "searxng": _search_searxng,
        "duckduckgo": _search_duckduckgo,
        "bing-rss": _search_bing_rss,
    }
    if configured == "auto":
        providers = []
        if config.WEB_SEARCH_BRAVE_API_KEY:
            providers.append("brave")
        if config.WEB_SEARCH_SEARXNG_URL:
            providers.append("searxng")
        providers.append("duckduckgo")
        providers.append("bing-rss")
    else:
        providers = [configured]

    failures: list[str] = []
    for provider in providers:
        searcher = searchers.get(provider)
        if searcher is None:
            raise WebSearchError(f"Unknown web search provider: {provider}.")
        try:
            raw_results = searcher(clean_query, max_results)
        except (WebSearchError, httpx.HTTPError, ValueError, TypeError) as exc:
            LOG.warning("Web search via %s failed: %s", provider, exc)
            failures.append(f"{provider}: {exc}")
            if provider != "duckduckgo":
                continue
            try:
                raw_results = _search_duckduckgo_instant(clean_query, max_results)
            except (httpx.HTTPError, ValueError, TypeError) as fallback_exc:
                failures.append(f"duckduckgo-instant: {fallback_exc}")
                continue
            provider = "duckduckgo-instant"
            if not raw_results:
                failures.append("duckduckgo-instant: no results")
                continue

        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for result in raw_results:
            key = result["url"].rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            results.append(result)
        if results:
            results = _rank_results(results, clean_query)
            if config.WEB_SEARCH_CACHE_SECONDS > 0:
                with _SEARCH_CACHE_LOCK:
                    _SEARCH_CACHE[cache_key] = (
                        time.monotonic(),
                        [dict(item) for item in results],
                        provider,
                    )
            return results, provider
        failures.append(f"{provider}: no results")

    detail = "; ".join(failures)
    raise WebSearchError(f"All configured web search providers failed ({detail}).")


__all__ = [
    "PageFetchError",
    "WebSearchError",
    "configured_provider",
    "fetch_web_page",
    "read_web_results",
    "search_web",
    "wants_web_search",
]
