#!/usr/bin/env python3
"""TrinaxAI public readiness audit.

Checks for the release blockers that are easy to reintroduce:
missing setup files, local machine paths/IPs, and incomplete i18n keys.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_GLOBS = ("*.py", "*.sh", "*.md", "*.yaml", "*.yml", "*.ts", "*.tsx", "*.js")
SKIP_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "storage",
    "storage.bak.nomic",
    "__pycache__",
    "projects",
    "local_sources",
}
REQUIRED_FILES = [
    "README.md",
    "README.es.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "LICENSE",
    "SUPPORT.md",
    "TRADEMARK.md",
    "requirements.txt",
    ".env.example",
    "backup.sh",
    "update.sh",
    "uninstall.sh",
    "docs/README.md",
    "docs/API_REFERENCE.md",
    "docs/CONFIGURATION.md",
    "chat-pwa/package.json",
]
ALLOW_HARDCODE_IN = {
    ".env.example",
    "README.md",
    "README.es.md",
    "docs/API_REFERENCE.md",
    "docs/ARCHITECTURE.md",
    "docs/DEVELOPER_GUIDE.md",
    "scripts/public_readiness.py",
    # Deliberate fake credentials used to exercise hashing/scanner behavior.
    "tests/test_device_pairing.py",
    "tests/test_public_readiness.py",
}
HARDCODE_PATTERNS = [
    re.compile(r"/home/trinaxcode"),
    re.compile(r"192\.168\.1\.23"),
]
LOCAL_ARTIFACTS = [
    ".venv",
    "__pycache__",
    "chat-pwa/node_modules",
    "chat-pwa/dist",
    "storage",
    "storage.bak.nomic",
    "local_sources",
    "projects",
    "logs",
    "backups",
]

# Patterns that should NEVER appear in public repo files
SECRET_PATTERNS = [
    (
        re.compile(
            r"(?i)\b(api[_-]?key|apikey|secret[_-]?key|admin[_-]?token)\b"
            r"[ \t]*[:=][ \t]*(['\"])[A-Za-z0-9_./+=-]{8,}\2"
        ),
        "possible API key or token",
    ),
    (re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"), "OpenAI-style API key"),
    (re.compile(r"(?i)(password|passwd)\s*[:=]\s*['\"]\S+['\"]"), "hardcoded password"),
    (re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"), "private key"),
    (
        re.compile(
            r"(?i)\b(access[_-]?token|auth[_-]?token)\b"
            r"\s*[:=]\s*(['\"])[A-Za-z0-9_./+=-]{16,}\2"
        ),
        "access token",
    ),
]

FILES_NEVER_COMMIT = {
    ".env",
    ".env.*",
    "*.log",
    "*.pem",
    "*.key",
    "*.crt",
    "*.pfx",
    "certs/*.pem",
    "certs/*.key",
    "certs/*.crt",
    "storage/",
    "backups/",
    "local_sources/",
    "logs/",
}
FILES_NEVER_COMMIT_EXCEPTIONS = {
    ".env.example",
}


def iter_source_files() -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS and not d.startswith(".")]
        for filename in filenames:
            path = current / filename
            if path.suffix in {".py", ".sh", ".md", ".yaml", ".yml", ".ts", ".tsx", ".js"} or path.name in {
                ".env.example"
            }:
                out.append(path)
    return out


def check_required_files() -> list[str]:
    errors = []
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")
    return errors


def check_local_artifacts() -> list[str]:
    try:
        ignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    except OSError:
        ignore_text = ""
    errors = []
    for rel in LOCAL_ARTIFACTS:
        patterns = {rel, f"{rel}/", f"/{rel}", f"/{rel}/"}
        if not any(pattern in ignore_text for pattern in patterns):
            errors.append(f"local artifact is not covered by .gitignore: {rel}")
    return errors


def check_hardcodes(files: list[Path]) -> list[str]:
    errors = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOW_HARDCODE_IN:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in HARDCODE_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{rel}:{line}: local hardcode `{match.group(0)}`")
    return errors


def check_i18n() -> list[str]:
    src = (ROOT / "chat-pwa/src/i18n/translations.ts").read_text(encoding="utf-8")
    es = set(re.findall(r"^\s+([A-Za-z0-9_]+):", src.split("\n  en: {", 1)[0], re.MULTILINE))
    en = set(re.findall(r"^\s+([A-Za-z0-9_]+):", src.split("\n  en: {", 1)[1], re.MULTILINE))
    used: set[str] = set()
    for path in (ROOT / "chat-pwa/src").rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        used.update(re.findall(r"(?<![A-Za-z0-9_])t\('([A-Za-z0-9_]+)'\)", text))

    errors = []
    for key in sorted((es ^ en) | (used - es) | (used - en)):
        parts = []
        if key not in es:
            parts.append("es")
        if key not in en:
            parts.append("en")
        if key not in used:
            continue
        errors.append(f"missing i18n key `{key}` in {', '.join(parts)}")
    return errors


def check_secrets(files: list[Path]) -> list[str]:
    """Check for accidentally committed secrets or tokens."""
    errors = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOW_HARDCODE_IN:
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern, desc in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{rel}:{line}: {desc} detected")
    return errors


def check_never_commit_files() -> list[str]:
    """Ensure sensitive file patterns are covered by .gitignore."""
    errors = []
    try:
        ignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    except OSError:
        ignore_text = ""
    ignore_lines = [line.strip() for line in ignore_text.splitlines() if line.strip() and not line.startswith("#")]

    def _covered(pattern: str) -> bool:
        """Check if a pattern is covered by .gitignore rules."""
        # Direct match
        if pattern in ignore_lines:
            return True
        if pattern.rstrip("/") in ignore_lines:
            return True
        # Check if a glob covers it
        if pattern.startswith("*."):
            if pattern in ignore_lines:
                return True
            return False
        # For path patterns like certs/*.pem, check if *.pem or certs/ covers it
        if "/" in pattern:
            parts = pattern.split("/")
            # Check if parent directory is in ignore_lines
            parent = parts[0] + "/"
            if parent in ignore_lines:
                return True
            # Check if file extension glob covers it
            if len(parts) > 1 and parts[-1].startswith("*."):
                if parts[-1] in ignore_lines:
                    return True
        # Check for directory patterns
        if not pattern.startswith("*"):
            dir_pattern = pattern.rstrip("/") + "/"
            if dir_pattern in ignore_lines:
                return True
        return False

    for pattern in sorted(FILES_NEVER_COMMIT):
        if not _covered(pattern):
            errors.append(f".gitignore may not cover: {pattern}")
    return errors


def git_tracked_files() -> list[Path]:
    """Return files tracked by git; empty outside a git checkout."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return []
    return [ROOT / rel for rel in result.stdout.split("\0") if rel]


def _matches_never_commit(rel: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        prefix = pattern.rstrip("/") + "/"
        return rel == pattern.rstrip("/") or rel.startswith(prefix)
    return fnmatch(rel, pattern) or fnmatch(Path(rel).name, pattern)


def check_tracked_never_commit_files() -> list[str]:
    """Fail if git already tracks local/private/generated files."""
    errors = []
    for path in git_tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in FILES_NEVER_COMMIT_EXCEPTIONS:
            continue
        for pattern in sorted(FILES_NEVER_COMMIT):
            if _matches_never_commit(rel, pattern):
                errors.append(f"tracked file should not be committed: {rel} (matches {pattern})")
                break
    return errors


def main() -> int:
    files = iter_source_files()
    errors = []
    errors.extend(check_required_files())
    errors.extend(check_local_artifacts())
    errors.extend(check_hardcodes(files))
    errors.extend(check_i18n())
    errors.extend(check_secrets(files))
    errors.extend(check_never_commit_files())
    errors.extend(check_tracked_never_commit_files())

    if errors:
        print("Public readiness audit failed:\n")
        for err in errors:
            print(f"- {err}")
        return 1
    print("Public readiness audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
