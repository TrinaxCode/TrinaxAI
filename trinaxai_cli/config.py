"""Local CLI configuration loader.

Follows the XDG Base Directory specification:

* ``$TRINAXAI_CONFIG``                 - explicit override (full file path)
* ``$XDG_CONFIG_HOME/trinaxai/config.toml``
* ``~/.config/trinaxai/config.toml``   - default fallback

The schema is intentionally small.  Missing keys fall back to sane defaults so
the CLI works on a fresh checkout.
"""
from __future__ import annotations

import logging
import os
import sys
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib  # type: ignore[import-not-found]
else:  # pragma: no cover - project requires py>=3.10 but be defensive
    tomllib = None  # type: ignore[assignment]

LOG = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:3333"


def _default_config_path() -> Path:
    """Return the XDG-resolved default config path (does not require it to exist)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join("~", ".config")
    return Path(base).expanduser() / "trinaxai" / "config.toml"


def _config_search_paths() -> list[Path]:
    """Return candidate config paths in priority order."""
    candidates: list[Path] = []
    env_override = os.environ.get("TRINAXAI_CONFIG")
    if env_override:
        candidates.append(Path(env_override).expanduser())
    candidates.append(_default_config_path())
    return candidates


@dataclass
class CLIConfig:
    """In-memory representation of the CLI configuration.

    Use :py:meth:`load` (classmethod) to read from disk and :py:meth:`save`
    to persist changes.  Access nested values via the typed properties
    (``api_base_url``, ``engine`` ...).
    """

    api_base_url: str = DEFAULT_BASE_URL
    api_verify_tls: bool = False

    engine: str = "rag"
    model: str = "qwen2.5-coder:3b"
    collections: list[str] = field(default_factory=lambda: ["default"])

    ui_color: str = "auto"  # auto | always | never

    session_enabled: bool = False
    session_dir: str = ""

    @property
    def api(self) -> dict[str, Any]:
        return {"base_url": self.api_base_url, "verify_tls": self.api_verify_tls}

    @property
    def defaults(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "model": self.model,
            "collections": list(self.collections),
        }

    @property
    def ui(self) -> dict[str, Any]:
        return {"color": self.ui_color}

    @property
    def session(self) -> dict[str, Any]:
        return {"enabled": self.session_enabled, "dir": self.session_dir}

    # ------------------------------------------------------------------ I/O
    @classmethod
    def load(cls, path: Path | None = None) -> "CLIConfig":
        """Load and parse the config at ``path`` (or search XDG locations).

        Missing files are not an error; malformed files log a warning and
        fall back to defaults.
        """
        cfg = cls()
        target = path.expanduser() if path is not None else cls.find_config()
        if target is None:
            return cfg
        try:
            raw = target.read_bytes()
        except OSError as exc:
            LOG.warning("Could not read %s: %s", target, exc)
            return cfg
        try:
            parsed = _parse_toml(raw)
        except Exception as exc:  # noqa: BLE001 - defensive: any parse error
            warnings.warn(f"Malformed config at {target}: {exc}; using defaults", stacklevel=2)
            LOG.warning("Malformed config at %s: %s; using defaults", target, exc)
            return cfg
        _apply_section(cfg, parsed)
        return cfg

    @classmethod
    def find_config(cls) -> Path | None:
        """Return the first existing config file, or ``None``."""
        for candidate in _config_search_paths():
            if candidate.is_file():
                return candidate
        return None

    def save(self, path: Path | None = None) -> Path:
        """Persist the config to ``path`` (or the default XDG location)."""
        target = path.expanduser() if path is not None else _default_config_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        body = _render_toml(self)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, target)
        return target

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------- helpers


def _parse_toml(raw: bytes) -> dict[str, Any]:
    if tomllib is not None:
        return tomllib.loads(raw.decode("utf-8"))
    # Minimal fallback for Python < 3.11 - project targets 3.12 so this rarely
    # executes.  It only handles the flat string / bool / list-of-strings forms
    # produced by :func:`_render_toml`.
    text = raw.decode("utf-8", errors="replace")
    result: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            current = result.setdefault(section, {})
            continue
        if current is None or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        current[key] = _parse_scalar(value)
    return result


def _parse_scalar(value: str) -> Any:
    if not value:
        return ""
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        items = [_parse_scalar(part.strip()) for part in _split_list(inner)]
        return items
    return value


def _split_list(inner: str) -> list[str]:
    items: list[str] = []
    buf: list[str] = []
    in_str = False
    for ch in inner:
        if ch == '"':
            in_str = not in_str
            buf.append(ch)
        elif ch == "," and not in_str:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        items.append("".join(buf))
    return items


def _apply_section(cfg: CLIConfig, parsed: dict[str, Any]) -> None:
    api = parsed.get("api") or {}
    if isinstance(api, dict):
        if "base_url" in api:
            cfg.api_base_url = str(api["base_url"])
        if "verify_tls" in api:
            cfg.api_verify_tls = bool(api["verify_tls"])

    defaults = parsed.get("defaults") or {}
    if isinstance(defaults, dict):
        if "engine" in defaults:
            cfg.engine = str(defaults["engine"])
        if "model" in defaults:
            cfg.model = str(defaults["model"])
        if "collections" in defaults:
            cols = defaults["collections"]
            if isinstance(cols, list):
                cfg.collections = [str(c) for c in cols]

    ui = parsed.get("ui") or {}
    if isinstance(ui, dict) and "color" in ui:
        cfg.ui_color = str(ui["color"])

    session = parsed.get("session") or {}
    if isinstance(session, dict):
        if "enabled" in session:
            cfg.session_enabled = bool(session["enabled"])
        if "dir" in session:
            cfg.session_dir = str(session["dir"])


def _render_toml(cfg: CLIConfig) -> str:
    lines = [
        "[api]",
        f'base_url = "{cfg.api_base_url}"',
        f"verify_tls = {str(cfg.api_verify_tls).lower()}",
        "",
        "[defaults]",
        f'engine = "{cfg.engine}"',
        f'model = "{cfg.model}"',
        "collections = [" + ", ".join(f'"{c}"' for c in cfg.collections) + "]",
        "",
        "[ui]",
        f'color = "{cfg.ui_color}"',
        "",
        "[session]",
        f"enabled = {str(cfg.session_enabled).lower()}",
        f'dir = "{cfg.session_dir}"',
        "",
    ]
    return "\n".join(lines)
