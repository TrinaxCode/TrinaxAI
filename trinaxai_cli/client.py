"""HTTP client for the TrinaxAI CLI.

Wraps the RAG API (FastAPI) with typed methods for each command. The CLI
modules call this client and never touch HTTP directly.
"""
from __future__ import annotations

import os
import ssl
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse, urlunparse

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover - httpx is in requirements
    httpx = None  # type: ignore


class TrinaxAPIError(RuntimeError):
    """Raised for any failed RAG API call.

    ``status`` is the HTTP status code for non-2xx responses, or ``0`` for
    transport-level failures (timeout, connection refused, DNS error) where no
    response was ever received.
    """

    def __init__(self, status: int, message: str, payload: Any | None = None) -> None:
        prefix = f"HTTP {status}: " if status else ""
        super().__init__(f"{prefix}{message}" if message else (prefix or "request failed"))
        self.status = status
        self.payload = payload


class TrinaxAPIClient:
    """Thin synchronous wrapper over the RAG API."""

    def __init__(self, base_url: str, verify_tls: bool | str = True, timeout: float = 30.0) -> None:
        if httpx is None:
            raise RuntimeError("httpx is required for the TrinaxAI CLI (install via requirements.txt).")
        self.base_url = (base_url or "https://localhost:3333").rstrip("/")
        self.verify_tls: bool | str = self._resolve_local_ca(verify_tls)
        self.timeout = timeout
        request_headers: dict[str, str] = {}
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
        """Use an explicit/local CA for loopback HTTPS without disabling TLS."""
        if verify_tls is not True:
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
                return str(candidate)

        root = os.getenv("TRINAXAI_HOME", "").strip()
        install_root = Path(root).expanduser() if root else Path(__file__).resolve().parents[1]
        leaf = install_root / "chat-pwa" / "certs" / "localhost.pem"
        if leaf.is_file():
            try:
                certificate = ssl._ssl._test_decode_cert(str(leaf))  # type: ignore[attr-defined]
                if certificate.get("issuer") == certificate.get("subject"):
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
            ollama_client = httpx.Client(base_url=normalized, timeout=self.timeout)
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
            self.verify_tls = verify_tls
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
            # CA; custom certificates use --insecure as an explicit opt-out.
            with httpx.Client(base_url=candidate, verify=self.verify_tls, timeout=probe_timeout) as probe:
                r = probe.get("/health")
                if r.status_code < 500:
                    self._switch_base_url(candidate)
        except Exception:
            pass

    # ── low-level ──
    def _send(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Issue a request, translating transport failures into TrinaxAPIError."""
        try:
            effective_timeout = timeout or self.timeout
            r = self._client.request(method, url, json=json, timeout=effective_timeout)
        except httpx.TimeoutException as exc:
            raise TrinaxAPIError(
                0, f"the RAG API at {self.base_url} timed out after {(timeout or self.timeout):g}s"
            ) from exc
        except httpx.TransportError as exc:
            raise TrinaxAPIError(
                0,
                f"cannot reach the RAG API at {self.base_url} "
                f"({exc.__class__.__name__}); is TrinaxAI running?",
            ) from exc
        return self._handle(r)

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
    def _handle(r: Any) -> Any:
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
            raise TrinaxAPIError(r.status_code, message, payload)
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
        return self._post("/v1/pairing/start", {
            "scopes": scopes,
            "ttl_seconds": ttl_seconds,
            "device_ttl_days": device_ttl_days,
        })

    def list_paired_devices(self) -> list[dict[str, Any]]:
        return list(self._get("/v1/pairing/devices").get("devices") or [])

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
    def list_sources(self, collection: str) -> dict[str, Any]:
        return self._get("/v1/sources", [("collection", collection)])

    def list_chunks(self, collection: str, file: str, limit: int = 50, offset: int = 0, q: str | None = None) -> dict[str, Any]:
        from urllib.parse import quote
        # `quote(..., safe="/")` preserves the slashes inside the path while
        # encoding spaces and other unsafe characters.
        path = f"/v1/sources/{quote(collection, safe='')}/{quote(file, safe='/')}/chunks"
        params: list[tuple[str, str]] = [("limit", str(limit)), ("offset", str(offset))]
        if q:
            params.append(("q", q))
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
        return self._get("/v1/memory").get("memories") or []

    def add_memory(self, text: str, tags: list[str] | None = None) -> dict[str, Any]:
        return self._post("/v1/memory", {"text": text, "tags": tags or []})

    def delete_memory(self, mid: str) -> bool:
        return bool(self._delete(f"/v1/memory/{mid}").get("deleted"))

    def refresh_memory(self) -> dict[str, Any]:
        return self._post("/v1/memory/refresh", {})

    def memory_summary(self) -> dict[str, Any]:
        return self._get("/v1/memory/summary")

    def memory_context(self, query: str, max_entries: int = 8) -> list[dict[str, Any]]:
        result = self._post(
            "/v1/memory/context",
            {"query": query, "max_entries": max_entries},
        )
        memories = result.get("memories") if isinstance(result, dict) else None
        return memories if isinstance(memories, list) else []

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
        return self._post(
            "/v1/research",
            body,
            timeout=max(float(self.timeout), 120.0 + 60.0 * max(1, min(depth, 3))),
        )

    # ── Stats ──
    def stats(self) -> dict[str, Any]:
        return self._get("/v1/stats")

    # ── Health ──
    def health(self) -> dict[str, Any]:
        return self._get("/health")
