"""Cross-platform discovery of the full TrinaxAI installation."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _looks_like_install(path: Path) -> bool:
    required = (
        path / "service_manager.py",
        path / "rag_api.py",
        path / "chat-pwa" / "server.mjs",
        path / "trinaxai_cli",
    )
    return all(item.is_file() for item in required[:-1]) and required[-1].is_dir()


def install_candidates() -> list[Path]:
    """Return installation candidates ordered from explicit to conventional."""
    candidates: list[Path] = []
    override = os.environ.get("TRINAXAI_HOME")
    if override:
        candidates.append(Path(override).expanduser())

    # Editable installs resolve here; normal wheel installs stay isolated from
    # unrelated source trees that happen to contain the invoking interpreter.
    package_path = Path(__file__).resolve()
    cwd = Path.cwd()
    candidates.extend(
        [
            package_path.parents[1],
            cwd,
            *cwd.parents,
        ]
    )

    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "TrinaxAI")
        candidates.append(Path.home() / "trinaxai")
    elif sys.platform == "darwin":
        candidates.extend([Path.home() / "Library" / "Application Support" / "TrinaxAI", Path.home() / "trinaxai"])
    else:
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        candidates.extend([data_home / "trinaxai", Path.home() / "trinaxai"])

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.expanduser().resolve()
        key = os.path.normcase(str(candidate))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def find_install_root() -> Path | None:
    """Locate the full app installation, or return ``None`` for CLI-only installs."""
    return next((path for path in install_candidates() if _looks_like_install(path)), None)
