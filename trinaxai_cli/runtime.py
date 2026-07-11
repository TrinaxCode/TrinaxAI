"""Cross-platform discovery of the full TrinaxAI installation."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _looks_like_install(path: Path) -> bool:
    return (path / "service_manager.py").is_file() and (path / "trinaxai_cli").is_dir()


def install_candidates() -> list[Path]:
    """Return installation candidates ordered from explicit to conventional."""
    candidates: list[Path] = []
    override = os.environ.get("TRINAXAI_HOME")
    if override:
        candidates.append(Path(override).expanduser())

    # Editable installs resolve here. A venv Python also gives us its project
    # root, including Windows' ``.venv\Scripts`` layout.
    package_path = Path(__file__).resolve()
    executable_path = Path(sys.executable).resolve()
    cwd = Path.cwd()
    candidates.extend(
        [
            package_path.parents[1],
            *list(executable_path.parents)[:3],
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
        candidates.extend(
            [Path.home() / "Library" / "Application Support" / "TrinaxAI", Path.home() / "trinaxai"]
        )
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


def require_install_root() -> Path:
    root = find_install_root()
    if root is None:
        checked = ", ".join(str(path) for path in install_candidates())
        raise FileNotFoundError(
            "No full TrinaxAI installation was found. Set TRINAXAI_HOME to its directory. "
            f"Checked: {checked}"
        )
    return root
