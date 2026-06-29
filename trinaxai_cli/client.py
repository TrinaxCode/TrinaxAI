"""HTTP client for the TrinaxAI CLI.

Wraps the RAG API (FastAPI) with typed methods for each command. The CLI
modules call this client and never touch HTTP directly.
"""
from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urlencode

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover - httpx is in requirements
    httpx = None  # type: ignore


class TrinaxAPIError(RuntimeError):
    def __init__(self, status: int, message: str, payload: Any | None = None) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.payload = payload


class TrinaxAPIClient:
    """Thin synchronous wrapper over the RAG API."""

    def __init__(self, base_url: str, verify_tls: bool = True, timeout: float = 30.0) -> None:
        if httpx is None:
            raise RuntimeError("httpx is required for the TrinaxAI CLI (install via requirements.txt).")
        self.base_url = (base_url or "http://localhost:3333").rstrip("/")
        self.verify_tls = bool(verify_tls)
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, verify=self.verify_tls, timeout=timeout)

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def __enter__(self) -> "TrinaxAPIClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ── low-level ──
    def _get(self, path: str, params: Iterable[tuple[str, str]] | None = None) -> Any:
        url = path + ("?" + urlencode(list(params)) if params else "")
        r = self._client.get(url)
        return self._handle(r)

    def _post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        r = self._client.post(path, json=body or {})
        return self._handle(r)

    def _delete(self, path: str) -> Any:
        r = self._client.delete(path)
        return self._handle(r)

    def _patch(self, path: str, body: dict[str, Any]) -> Any:
        r = self._client.patch(path, json=body)
        return self._handle(r)

    @staticmethod
    def _handle(r: Any) -> Any:
        if r.status_code >= 400:
            try:
                payload = r.json()
            except Exception:
                payload = r.text
            raise TrinaxAPIError(r.status_code, r.text[:400] if r.text else "", payload)
        if not r.content:
            return {}
        try:
            return r.json()
        except Exception:
            return r.text

    # ── Collections ──
    def list_collections(self) -> list[dict[str, Any]]:
        data = self._get("/collections")
        return data.get("collections") or []

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

    # ── Research ──
    def research(self, query: str, collections: list[str] | None = None, depth: int = 2) -> dict[str, Any]:
        return self._post("/v1/research", {"query": query, "collections": collections or [], "depth": depth})

    # ── Stats ──
    def stats(self) -> dict[str, Any]:
        return self._get("/v1/stats")

    # ── Health ──
    def health(self) -> dict[str, Any]:
        return self._get("/health")
