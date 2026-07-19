"""Conversation persistence for the TrinaxAI CLI.

Sessions are append-only JSONL files stored under
``$XDG_DATA_HOME/trinaxai/sessions/`` (default
``~/.local/share/trinaxai/sessions/``).  Each line is a single message:

.. code-block:: json

    {"ts": 1719560000.123, "role": "user", "content": "hi", "meta": {}}

The format is intentionally simple so it can be tailed, grepped, and
re-imported by other tools.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def _default_session_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.join("~", ".local", "share")
    return Path(base).expanduser() / "trinaxai" / "sessions"


def _resolve_dir(dir: Path | str | None) -> Path:
    if dir is None:
        return _default_session_dir()
    p = Path(dir).expanduser()
    return p


def _file_for(name: str, dir: Path) -> Path:
    safe = name.replace("/", "_").replace("..", "_").strip() or "default"
    return dir / f"{safe}.jsonl"


class Session:
    """Append-only conversation logger.

    Use the instance as a context manager (or call :py:meth:`close` explicitly)
    to flush the underlying file handle.
    """

    def __init__(self, name: str, dir: Path | str | None = None) -> None:
        self.name = name
        self.dir = _resolve_dir(dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = _file_for(name, self.dir)
        self._fh = open(self.path, "a", encoding="utf-8")

    def append(self, role: str, content: str, meta: dict[str, Any] | None = None) -> None:
        record = {
            "ts": time.time(),
            "role": role,
            "content": content,
            "meta": meta or {},
        }
        line = json.dumps(record, ensure_ascii=False)
        self._fh.write(line + "\n")
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover - best-effort
        try:
            self.close()
        except Exception:
            pass

    # ----------------------------------------------------------- class-level
    @staticmethod
    def load(name: str, dir: Path | str | None = None) -> list[dict[str, Any]]:
        """Read all messages from the named session.

        Returns an empty list if the session file does not exist.
        Malformed lines are skipped with a warning printed to stderr.
        """
        import sys

        path = _file_for(name, _resolve_dir(dir))
        if not path.is_file():
            return []
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    records.append(json.loads(raw))
                except json.JSONDecodeError as exc:
                    print(
                        f"warning: skipping malformed session line in {path}: {exc}",
                        file=sys.stderr,
                    )
        return records

    @staticmethod
    def list_names(dir: Path | str | None = None) -> list[str]:
        """Return sorted session names (without the ``.jsonl`` extension)."""
        d = _resolve_dir(dir)
        if not d.is_dir():
            return []
        return sorted(p.stem for p in d.glob("*.jsonl"))

    @staticmethod
    def delete(name: str, dir: Path | str | None = None) -> bool:
        """Delete the named session file.  Returns ``True`` if removed."""
        path = _file_for(name, _resolve_dir(dir))
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True
