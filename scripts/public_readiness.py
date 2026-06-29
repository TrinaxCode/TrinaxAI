#!/usr/bin/env python3
"""TrinaxAI public readiness audit.

Checks for the release blockers that are easy to reintroduce:
missing setup files, local machine paths/IPs, and incomplete i18n keys.
"""
from __future__ import annotations

import re
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_GLOBS = ("*.py", "*.sh", "*.md", "*.yaml", "*.yml", "*.ts", "*.tsx", "*.js")
SKIP_PARTS = {
    ".git", ".venv", "venv", "node_modules", "dist", "storage", "storage.bak.nomic",
    "__pycache__", "projects", "local_sources",
}
REQUIRED_FILES = [
    "README.md",
    "README.es.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "LICENSE",
    "ROADMAP.md",
    "SUPPORT.md",
    "TRADEMARK.md",
    "requirements.txt",
    ".env.example",
    "backup.sh",
    "update.sh",
    "uninstall.sh",
    "docs/PUBLIC_RELEASE.md",
    "docs/PUBLIC_RELEASE.es.md",
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


def iter_source_files() -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS and not d.startswith(".")]
        for filename in filenames:
            path = current / filename
            if path.suffix in {".py", ".sh", ".md", ".yaml", ".yml", ".ts", ".tsx", ".js"} or path.name in {".env.example"}:
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


def main() -> int:
    files = iter_source_files()
    errors = []
    errors.extend(check_required_files())
    errors.extend(check_local_artifacts())
    errors.extend(check_hardcodes(files))
    errors.extend(check_i18n())

    if errors:
        print("Public readiness audit failed:\n")
        for err in errors:
            print(f"- {err}")
        return 1
    print("Public readiness audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
