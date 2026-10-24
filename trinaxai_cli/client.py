"""HTTP client for the TrinaxAI CLI.

Wraps the RAG API (FastAPI) with typed methods for each command. The CLI
modules call this client and never touch HTTP directly.
"""

from __future__ import annotations

import logging
import os
import ssl
import sys
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse, urlunparse

from trinaxai.errors import ErrorCategory, classify_error
from trinaxai_cli.i18n import normalize_lang

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover - httpx is in requirements
    httpx = None  # type: ignore

LOG = logging.getLogger("trinaxai_cli.client")


class TrinaxAPIError(RuntimeError):
    """Raised for any failed RAG API call.

    ``status`` is the HTTP status code for non-2xx responses, or ``0`` for
    transport-level failures (timeout, connection refused, DNS error) where no
    response was ever received.
    """

    def __init__(
        self,
        status: int,
        message: str,
        payload: Any | None = None,
        *,
        language: str = "en",
        certificate_problem: bool = False,
    ) -> None:
        self.technical_message = message
        self.language = normalize_lang(language)
        info = classify_error(RuntimeError(message), status_code=status, hint=message)
        spanish = self.language == "es"
        public_message = info.definition.message_es if spanish else info.definition.message
        public_recovery = info.definition.recovery_es if spanish else info.definition.recovery
        # True when the message already tells the user what to do next.
        self.recovery_included = False
        if certificate_problem:
            self.recovery_included = True
            public_message, public_recovery = (
                (
                    "Este equipo no confía en el certificado del servicio local de TrinaxAI.",
                    "Ejecuta: trinaxai doctor",
                )
                if spanish
                else ("This computer does not trust the local TrinaxAI certificate.", "Run: trinaxai doctor")
            )
        elif status == 0 and message == "request timed out":
            # The wait limit ended while the local model was still working; the network is fine.
            public_message, public_recovery = (
                (
                    "TrinaxAI no terminó dentro del tiempo de espera; este equipo puede necesitar más tiempo para esto.",
                    "Prueba una petición más pequeña (en research: --depth 1) o sube TRINAXAI_CLI_TIMEOUT (segundos).",
                )
                if spanish
                else (
                    "TrinaxAI did not finish within the wait limit; this computer may need more time for this.",
                    "Try a smaller request (for research: --depth 1) or raise TRINAXAI_CLI_TIMEOUT (seconds).",
                )
            )
        elif info.category is ErrorCategory.INTERNET_UNAVAILABLE:
            # This client only ever talks to the local TrinaxAI API, so a refused or
            # failed connection means the service is not running, not that the
            # internet is down.
            self.recovery_included = True
            public_message, public_recovery = (
                ("No se puede conectar con el servicio local de TrinaxAI.", "Inícialo con: trinaxai start")
                if spanish
                else ("Cannot reach the local TrinaxAI service.", "Start it with: trinaxai start")
            )
        super().__init__(f"{public_message} {public_recovery}")
        self.status = status
        self.payload = payload
        self.category = info.category.value
        self.error_code = info.code
        self.retryable = info.retryable


_CREDENTIAL_HEADERS = frozenset({"X-Admin-Token", "X-TrinaxAI-Device-Token"})


def _cli_timeout() -> float | None:
    """Seconds from ``TRINAXAI_CLI_TIMEOUT`` for long requests, or None to use the built-in limits."""
    try:
        value = float(os.getenv("TRINAXAI_CLI_TIMEOUT", "").strip())
    except ValueError:
        return None
    return value if 5.0 <= value <= 86400.0 else None


def _speaks_no_tls(exc: BaseException) -> bool:
    """True when the handshake failed because the other end is a plain-HTTP server."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        text = str(current).lower()
        if isinstance(current, ssl.SSLError) and ("wrong version number" in text or "http request" in text):
            return True
        current = current.__cause__ or current.__context__
    return False


def _is_certificate_problem(exc: BaseException) -> bool:
    """True when a transport failure was the TLS handshake rejecting the server's certificate."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError) or "certificate verify failed" in str(current).lower():
            return True
        current = current.__cause__ or current.__context__
    return False


class TrinaxAPIClient:
    """Thin synchronous wrapper over the RAG API."""

    def __init__(
        self, base_url: str, verify_tls: str | None = None, timeout: float = 30.0, language: str | None = None
    ) -> None:
        if httpx is None:
            raise RuntimeError("httpx is required for the TrinaxAI CLI (install via requirements.txt).")
        self.base_url = (base_url or "https://localhost:3333").rstrip("/")
        self.verify_tls: bool | str = self._resolve_local_ca(verify_tls)
        self.timeout = timeout
        self.language = normalize_lang(language)
        request_headers: dict[str, str] = {}
        if language is not None:
            request_headers["Accept-Language"] = self.language
        admin_token = os.getenv("TRINAXAI_ADMIN_TOKEN", "").strip()
        device_token = os.getenv("TRINAXAI_DEVICE_TOKEN", "").strip()
        if admin_token:
            request_headers["X-Admin-Token"] = admin_token
        elif device_token:
            request_headers["X-TrinaxAI-Device-Token"] = device_token
        self._request_headers = request_headers
        self._client = httpx.Client(
            base_url=self.base_url,
            verify=self.verify_tls,
            timeout=timeout,
            headers=request_headers,
        )
        self._ollama_clients: dict[str, Any] = {}
        self._prefer_local_https_if_needed()

    def _resolve_local_ca(self, verify_tls: bool | str) -> bool | str:
        """Return ``True`` or a validated CA path; never disable TLS checks."""
        if verify_tls is False:
            raise ValueError("TLS certificate verification cannot be disabled")
        context = ssl.create_default_context()
        if isinstance(verify_tls, str):
            context.load_verify_locations(cafile=verify_tls)
            return verify_tls
        parsed = urlparse(self.base_url)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return True

        configured = os.getenv("TRINAXAI_CA_FILE", "").strip()
        candidates: list[Path] = [Path(configured).expanduser()] if configured else []
        if sys.platform == "darwin":
            candidates.append(Path("~/Library/Application Support/mkcert/rootCA.pem").expanduser())
        elif sys.platform == "win32":
            local_app_data = os.getenv("LOCALAPPDATA", "")
            if local_app_data:
                candidates.append(Path(local_app_data) / "mkcert" / "rootCA.pem")
        else:
            candidates.append(Path("~/.local/share/mkcert/rootCA.pem").expanduser())

        for candidate in candidates:
            if candidate.is_file():
                context.load_verify_locations(cafile=str(candidate))
                return str(candidate)

        root = os.getenv("TRINAXAI_HOME", "").strip()
        install_root = Path(root).expanduser() if root else Path(__file__).resolve().parents[1]
        leaf = install_root / "chat-pwa" / "certs" / "localhost.pem"
        if leaf.is_file():
            try:
                certificate = ssl._ssl._test_decode_cert(str(leaf))  # type: ignore[attr-defined]
                if certificate.get("issuer") == certificate.get("subject"):
                    context.load_verify_locations(cafile=str(leaf))
                    return str(leaf)
            except (OSError, ValueError, ssl.SSLError):
                pass
        return True

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
        for ollama_client in self._ollama_clients.values():
            try:
                ollama_client.close()
            except Exception:
                pass
        self._ollama_clients.clear()

    def stream_ollama(self, base_url: str, body: dict[str, Any], *, timeout: float = 120.0) -> Any:
        """Open a streaming Ollama request, reusing the connection between turns."""
        ollama_client = self._ollama_client(base_url)
        return ollama_client.stream("POST", "/api/chat", json=body, timeout=timeout)

    def _ollama_client(self, base_url: str) -> Any:
        normalized = base_url.rstrip("/")
        ollama_client = self._ollama_clients.get(normalized)
        if ollama_client is None:
            ollama_client = httpx.Client(base_url=normalized, verify=self.verify_tls, timeout=self.timeout)
            self._ollama_clients[normalized] = ollama_client
        return ollama_client

    def list_ollama_models(self, base_url: str) -> list[dict[str, Any]]:
        """Return the models installed in the configured local Ollama instance."""
        response = self._ollama_client(base_url).get("/api/tags", timeout=5.0)
        response.raise_for_status()
        return list(response.json().get("models") or [])

    def __enter__(self) -> "TrinaxAPIClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _local_https_candidate(self) -> str | None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
            return None
        return urlunparse(parsed._replace(scheme="https"))

    def _switch_base_url(self, base_url: str, *, verify_tls: bool | str | None = None) -> None:
        self.close()
        self.base_url = base_url.rstrip("/")
        if verify_tls is not None:
            self.verify_tls = self._resolve_local_ca(verify_tls)
        self._client = httpx.Client(
            base_url=self.base_url,
            verify=self.verify_tls,
            timeout=self.timeout,
            headers=self._request_headers,
        )

    def _prefer_local_https_if_needed(self) -> None:
        candidate = self._local_https_candidate()
        if not candidate:
            return
        probe_timeout = min(float(self.timeout), 1.5)
        try:
            r = self._client.get("/health", timeout=probe_timeout)
            if r.status_code < 500:
                return
        except Exception:
            pass
        try:
            # Never silently downgrade certificate verification merely because
            # the candidate is localhost. The installer trusts TrinaxAI's local
            # CA; custom certificates must provide a trusted CA file.
            with httpx.Client(base_url=candidate, verify=self.verify_tls, timeout=probe_timeout) as probe:
                r = probe.get("/health")
                if r.status_code < 500:
                    self._switch_base_url(candidate)
        except Exception:
            pass

    def _use_plain_http_if_served(self) -> bool:
        """Follow a local API that runs without HTTPS (no certificate was created for it).

        Only a loopback address, and only when the port answers plain HTTP: the handshake
        proved nothing was sent, and verification is never relaxed for an HTTPS server.
        """
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return False
        candidate = urlunparse(parsed._replace(scheme="http"))
        try:
            with httpx.Client(base_url=candidate, timeout=min(float(self.timeout), 1.5)) as probe:
                answer = probe.get("/health")
                # Another program on that port must not be adopted: require TrinaxAI's own answer.
                if answer.status_code != 200 or not isinstance(answer.json(), dict) or "ok" not in answer.json():
                    return False
        except Exception:  # noqa: BLE001 - a failed probe just means there is no plain-HTTP API
            return False
        # The port could not be verified with TLS, so no secret travels to it in clear text. A local
        # program squatting on the port would otherwise receive the admin or device token.
        self._request_headers = {
            key: value for key, value in self._request_headers.items() if key not in _CREDENTIAL_HEADERS
        }
        self._switch_base_url(candidate)
        return True

    def ensure_reachable(self) -> None:
        """Settle http vs https before a streamed request, which bypasses ``_send``. Once per client."""
        if getattr(self, "_reachability_checked", False):
            return
        self._reachability_checked = True
        try:
            self._client.get("/health", timeout=min(float(self.timeout), 1.5))
        except httpx.TransportError as exc:
            if _speaks_no_tls(exc):
                self._use_plain_http_if_served()
        except Exception:  # noqa: BLE001 - the real request reports whatever is wrong
            pass

    # ── internal details ──
    def _send(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Issue a request, translating transport failures into TrinaxAPIError."""
        effective_timeout = timeout or self.timeout
        retryable_method = method.upper() in {"GET", "HEAD", "OPTIONS"}
        for attempt in range(2 if retryable_method else 1):
            try:
                r = self._client.request(method, url, json=json, timeout=effective_timeout)
                return self._handle(r, language=getattr(self, "language", "en"))
            except httpx.TimeoutException:
                error = TrinaxAPIError(0, "request timed out", language=getattr(self, "language", "en"))
            except httpx.TransportError as exc:
                if _speaks_no_tls(exc) and self._use_plain_http_if_served():
                    return self._send(method, url, json=json, timeout=timeout)
                error = TrinaxAPIError(
                    0,
                    "local service unavailable",
                    language=getattr(self, "language", "en"),
                    certificate_problem=_is_certificate_problem(exc),
                )
            except TrinaxAPIError as caught:
                error = caught
                if not (retryable_method and error.retryable and attempt == 0):
                    raise
            if retryable_method and error.retryable and attempt == 0:
                time.sleep(0.25)
                continue
            raise error

    def _get(self, path: str, params: Iterable[tuple[str, str]] | None = None) -> Any:
        url = path + ("?" + urlencode(list(params)) if params else "")
        return self._send("GET", url)

    def _post(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        return self._send("POST", path, json=body or {}, timeout=timeout)

    def _delete(self, path: str) -> Any:
        return self._send("DELETE", path)

    def _patch(self, path: str, body: dict[str, Any]) -> Any:
        return self._send("PATCH", path, json=body)

    @staticmethod
    def _handle(r: Any, *, language: str = "en") -> Any:
        if r.status_code >= 400:
            try:
                payload = r.json()
            except Exception:
                payload = r.text
            # FastAPI reports errors as {"detail": ...}; prefer that over the
            # raw response body for a readable message.
            message = ""
            if isinstance(payload, dict):
                detail = payload.get("detail") or payload.get("error") or payload.get("message")
                message = str(detail) if detail else ""
            if not message:
                message = (r.text or "").strip()[:400]
            raise TrinaxAPIError(r.status_code, message, payload, language=language)
        if not r.content:
            return {}
        try:
            return r.json()
        except Exception:
            return r.text

    # ── Device pairing ──
    def start_pairing(
        self,
        scopes: list[str],
        *,
        ttl_seconds: int = 300,
        device_ttl_days: int | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "/v1/pairing/start",
            {
                "scopes": scopes,
                "ttl_seconds": ttl_seconds,
                "device_ttl_days": device_ttl_days,
            },
        )

    def list_paired_devices(self) -> list[dict[str, Any]]:
        return list(self._get("/v1/pairing/devices").get("devices") or [])

    def set_paired_device_scopes(self, device_id: str, scopes: list[str]) -> dict[str, Any]:
        return self._patch(f"/v1/pairing/devices/{device_id}", {"scopes": scopes}).get("device") or {}

    def revoke_paired_device(self, device_id: str) -> dict[str, Any]:
        return self._delete(f"/v1/pairing/devices/{device_id}").get("device") or {}

    # ── Collections ──
    def list_collections(self) -> list[dict[str, Any]]:
        data = self._get("/collections")
        return data.get("collections") or []

    def reload_index(self) -> dict[str, Any]:
        return self._post("/system/reload")

    def create_collection(self, name: str) -> dict[str, Any]:
        return self._post("/collections", {"name": name}).get("collection") or {}

    def rename_collection(self, cid: str, name: str) -> dict[str, Any]:
        return self._patch(f"/collections/{cid}", {"name": name}).get("collection") or {}

    def delete_collection(self, cid: str) -> int:
        from urllib.parse import quote

        return int((self._delete(f"/collections/{quote(cid, safe='')}") or {}).get("deleted_nodes") or 0)

    # ── Sources / Browse ──
    def list_sources(self, collection: str, source_id: str | None = None) -> dict[str, Any]:
        params = [("collection", collection)]
        if source_id:
            params.append(("source_id", source_id))
        return self._get("/v1/sources", params)

    def list_chunks(
        self,
        collection: str,
        file: str,
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        from urllib.parse import quote

        # `quote(..., safe="/")` preserves the slashes inside the path while
        # encoding spaces and other unsafe characters.
        path = f"/v1/sources/{quote(collection, safe='')}/{quote(file, safe='/')}/chunks"
        params: list[tuple[str, str]] = [("limit", str(limit)), ("offset", str(offset))]
        if q:
            params.append(("q", q))
        if source_id:
            params.append(("source_id", source_id))
        return self._get(path, params)

    # ── Watcher ──
    def watch_start(self, paths: list[str] | None = None, collection: str | None = None) -> dict[str, Any]:
        return self._post("/v1/watch/start", {"paths": paths, "collection": collection})

    def watch_stop(self) -> dict[str, Any]:
        return self._post("/v1/watch/stop", {})

    def watch_status(self) -> dict[str, Any]:
        return self._get("/v1/watch/status")

    # ── Memory ──
    def list_memories(self) -> list[dict[str, Any]]:
        data = self._get("/v1/memory")
        if isinstance(data, list):
            memories = data
        elif isinstance(data, dict):
            memories = data.get("memories")
            if memories is None and isinstance(data.get("data"), dict):
                memories = data["data"].get("memories")
            if memories is None:
                memories = data.get("items")
        else:
            memories = None
        if not isinstance(memories, list) or any(not isinstance(item, dict) for item in memories):
            raise TrinaxAPIError(
                0, "unexpected memory-list response from the backend", data, language=getattr(self, "language", "en")
            )
        return memories

    def add_memory(self, text: str, tags: list[str] | None = None) -> dict[str, Any]:
        return self._post("/v1/memory", {"text": text, "tags": tags or []})

    def delete_memory(self, mid: str) -> bool:
        return bool(self._delete(f"/v1/memory/{mid}").get("deleted"))

    def refresh_memory(self) -> dict[str, Any]:
        return self._post("/v1/memory/refresh", {}, timeout=max(float(self.timeout), 300.0))

    def memory_summary(self) -> dict[str, Any]:
        return self._get("/v1/memory/summary")

    def memory_context(self, query: str, max_entries: int = 8) -> list[dict[str, Any]]:
        result = self._post(
            "/v1/memory/context",
            {"query": query, "max_entries": max_entries},
        )
        memories = result.get("memories") if isinstance(result, dict) else None
        if not isinstance(memories, list) or any(not isinstance(item, dict) for item in memories):
            raise TrinaxAPIError(
                502,
                "unexpected memory-context response from the backend",
                result,
                language=getattr(self, "language", "en"),
            )
        return memories

    # ── Research ──
    def research(
        self,
        query: str,
        collections: list[str] | None = None,
        depth: int = 2,
        *,
        web_search: bool | None = None,
        search_query: str | None = None,
        context: str | None = None,
        include_local: bool = False,
        model: str | None = None,
        thinking: bool | None = None,
    ) -> dict[str, Any]:
        """Run a research pass. ``web_search`` grounds the answer on the live web.

        The backend (``/v1/research``) accepts optional ``search_query`` /
        ``context`` to build a standalone web query without trusting stale
        answers, and ``include_local`` to also pull from indexed collections.
        Only non-default values are sent so old server builds keep working.
        """
        body: dict[str, Any] = {
            "query": query,
            "collections": collections or [],
            "depth": depth,
        }
        if web_search is not None:
            body["web_search"] = web_search
        if search_query:
            body["search_query"] = search_query
        if context:
            body["context"] = context
        if include_local:
            body["include_local"] = True
        if model:
            body["model"] = model
        if thinking is not None:
            body["think"] = bool(thinking)
        return self._post(
            "/v1/research",
            body,
            timeout=_cli_timeout() or max(float(self.timeout), 120.0 + 60.0 * max(1, min(depth, 3))),
        )

    # ── Stats ──
    def stats(self) -> dict[str, Any]:
        return self._get("/v1/stats")

    # ── Health ──
    def health(self) -> dict[str, Any]:
        return self._get("/health")
