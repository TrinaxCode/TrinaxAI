#!/usr/bin/env python3
"""TrinaxAI public readiness audit.

Checks for the release blockers that are easy to reintroduce:
missing setup files, local machine paths/IPs, and incomplete i18n keys.
"""

from __future__ import annotations

import os
import re
import shlex
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
    "test-results",
    "storage",
    "storage.bak.nomic",
    "__pycache__",
    "projects",
    "local_sources",
    "qa-test-workspace",
    "qa-evidence-after-fixes",
}
REQUIRED_FILES = [
    "README.md",
    "README.es.md",
    "docs/CONTRIBUTING.md",
    "docs/CODE_OF_CONDUCT.md",
    "docs/CHANGELOG.md",
    "LICENSE",
    "docs/SUPPORT.md",
    "docs/TRADEMARK.md",
    "requirements.txt",
    ".env.example",
    "backup.sh",
    "update.sh",
    "uninstall.sh",
    "docs/README.md",
    "docs/API_REFERENCE.md",
    "docs/CONFIGURATION.md",
    "trinaxai_manager.py",
    "scripts/build_manager.py",
    "chat-pwa/package.json",
    "chat-pwa/public/manifest.en.webmanifest",
    "chat-pwa/public/manifest.es.webmanifest",
    "chat-pwa/public/offline.html",
    "trinaxai_cli/i18n.py",
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
    "tests/test_release_tools_flows.py",
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
    "tarea[0-9]*.md",
}
FILES_NEVER_COMMIT_EXCEPTIONS = {
    ".env.example",
}
RELEASE_MANAGER_ASSETS = (
    "TrinaxAI-Manager-Windows.exe",
    "TrinaxAI-Manager-macOS.dmg",
    "TrinaxAI-Manager-Linux.deb",
)
RELEASE_ACTION_REF = re.compile(r"^\s*(?:-\s*)?uses:\s*([^@\s]+)@([^\s#]+)")
EXACT_BUILD_VERSION = re.compile(r"\"\d+\.\d+\.\d+\"")


def check_release_workflow_security(workflow: str) -> list[str]:
    """Keep stable release publication signed and reproducible."""
    errors: list[str] = []
    action_refs = []
    for line in workflow.splitlines():
        if "uses:" not in line or "./" in line:
            continue
        match = RELEASE_ACTION_REF.match(line)
        if not match:
            errors.append(f"release action is not pinned immutably: {line.strip()}")
            continue
        action, ref = match.groups()
        action_refs.append(action)
        if not re.fullmatch(r"[0-9a-f]{40}", ref):
            errors.append(f"release action {action} is not pinned to a commit SHA")
    if not action_refs:
        errors.append("release workflow has no externally pinned actions")

    if re.search(r"(?:runs-on:|\bos:)\s*[^\n]*-latest\b", workflow):
        errors.append("release workflow uses a mutable latest runner")
    python_versions = re.findall(r"python-version:\s*([^\s#]+)", workflow)
    if not python_versions or any(not EXACT_BUILD_VERSION.fullmatch(value) for value in python_versions):
        errors.append("release workflow must use an exact Python toolchain version")
    node_versions = re.findall(r"node-version:\s*([^\s#]+)", workflow)
    if not node_versions or any(not EXACT_BUILD_VERSION.fullmatch(value) for value in node_versions):
        errors.append("release workflow must use an exact Node toolchain version")
    if not re.search(r"['\"]pyinstaller==\d+\.\d+\.\d+['\"]", workflow):
        errors.append("release workflow must pin PyInstaller")
    for tool in ("pip", "setuptools", "wheel", "altgraph", "pyinstaller-hooks-contrib"):
        if not re.search(rf"['\"]{tool}==\d+(?:\.\d+){{1,2}}['\"]", workflow):
            errors.append(f"release workflow must pin {tool}")

    required_markers = (
        "name: Require Windows signing credentials",
        "name: Require macOS signing credentials",
        "name: Require release signing credentials",
        "gpg --batch --verify",
        "--detach-sign",
        "name: Sign and verify container images",
        "cosign sign --yes",
        "cosign verify",
        "cosign-release: v2.5.3",
    )
    for marker in required_markers:
        if marker not in workflow:
            errors.append(f"release workflow is missing signing control: {marker}")
    if "env.WINDOWS_SIGNING_CERTIFICATE_BASE64 != ''" in workflow:
        errors.append("Windows signing must not be optional")
    if "env.MACOS_SIGNING_CERTIFICATE_BASE64 != ''" in workflow:
        errors.append("macOS signing must not be optional")
    if re.search(r"if:\s*runner\.os == '(?:Windows|macOS)'\s*&&", workflow):
        errors.append("platform signing must not be conditional on secret presence")
    signing = workflow.find("name: Sign and verify release assets")
    publishing = workflow.find("name: Publish simple release with assets")
    if signing < 0 or publishing < 0 or signing > publishing:
        errors.append("release assets must be signed before publication")
    if "SHA256SUMS.asc" not in workflow:
        errors.append("release signature manifest is not verified after publication")
    if "py3-none-any.whl.asc" not in workflow:
        errors.append("Python wheel signature is not verified after publication")
    return errors


def required_gate_commands() -> tuple[tuple[str, tuple[str, ...], Path], ...]:
    """Return the release gates that must run before readiness can pass."""
    npm = "npm.cmd" if os.name == "nt" else "npm"
    return (
        (
            "Python coverage",
            (
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--cov=app",
                "--cov=trinaxai_cli",
                "--cov=trinaxai_core",
                "--cov=service_manager",
                "--cov=index",
                "--cov-branch",
                "--cov-report=xml:coverage.xml",
                "--cov-fail-under=98",
            ),
            ROOT,
        ),
        ("TypeScript typecheck", (npm, "run", "typecheck"), ROOT / "chat-pwa"),
        ("Frontend coverage", (npm, "run", "test:coverage"), ROOT / "chat-pwa"),
        ("PWA build", (npm, "run", "build"), ROOT / "chat-pwa"),
    )


def check_required_gates() -> list[str]:
    """Run release gates and retain stdout/stderr so failures are actionable."""
    errors: list[str] = []
    for label, command, cwd in required_gate_commands():
        rendered = shlex.join(command)
        print(f"[gate] {label}: {rendered} (cwd={cwd})")
        try:
            result = subprocess.run(
                list(command),
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            message = f"{label} could not start: {exc}"
            print(f"[gate] {message}")
            errors.append(message)
            continue

        stdout = (getattr(result, "stdout", "") or "").rstrip()
        stderr = (getattr(result, "stderr", "") or "").rstrip()
        if stdout:
            print(f"[gate] {label} stdout:\n{stdout}")
        if stderr:
            print(f"[gate] {label} stderr:\n{stderr}")
        if result.returncode:
            message = f"{label} failed with exit code {result.returncode}"
            print(f"[gate] {message}")
            errors.append(message)
        else:
            print(f"[gate] {label}: passed")
    return errors


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
        if rel in ALLOW_HARDCODE_IN or fnmatch(rel, "tarea[0-9]*.md"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in HARDCODE_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{rel}:{line}: local hardcode `{match.group(0)}`")
    return errors


def check_i18n() -> list[str]:
    src = (ROOT / "chat-pwa/src/i18n/translations.ts").read_text(encoding="utf-8")
    es_section = src.split("\n  es: {", 1)[1].split("\n  en: {", 1)[0]
    en_section = src.split("\n  en: {", 1)[1]
    es = set(re.findall(r"^\s+([A-Za-z0-9_]+):", es_section, re.MULTILINE))
    en = set(re.findall(r"^\s+([A-Za-z0-9_]+):", en_section, re.MULTILINE))
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
        if parts:
            errors.append(f"missing i18n key `{key}` in {', '.join(parts)}")
    return errors


def check_documentation_pairs() -> list[str]:
    errors: list[str] = []
    docs = ROOT / "docs"
    for english in sorted(docs.glob("*.md")):
        if english.name.endswith(".es.md"):
            continue
        spanish_suffix = english.with_name(f"{english.stem}.es.md")
        spanish_dir = docs / "es" / english.name
        if not spanish_suffix.exists() and not spanish_dir.exists():
            errors.append(f"missing Spanish documentation pair for {english.relative_to(ROOT)}")
    for spanish in sorted(docs.glob("*.es.md")):
        english = docs / f"{spanish.stem}.md"
        if not english.exists():
            errors.append(f"missing English documentation pair for {spanish.relative_to(ROOT)}")
    for spanish in sorted((docs / "es").glob("*.md")) if (docs / "es").is_dir() else []:
        english_candidates = (docs / spanish.name, ROOT / spanish.name)
        if not any(candidate.exists() for candidate in english_candidates):
            errors.append(f"missing English documentation pair for {spanish.relative_to(ROOT)}")
    return errors


def check_pwa_locales() -> list[str]:
    errors: list[str] = []
    for name in ("manifest.en.webmanifest", "manifest.es.webmanifest"):
        path = ROOT / "chat-pwa/public" / name
        if not path.exists():
            continue
        try:
            import json

            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"invalid PWA manifest {name}: {exc}")
            continue
        expected = "es" if ".es." in name else "en"
        if manifest.get("lang") != expected:
            errors.append(f"PWA manifest {name} must declare lang={expected}")
    offline_path = ROOT / "chat-pwa/public/offline.html"
    if offline_path.exists():
        try:
            offline = offline_path.read_text(encoding="utf-8")
            for source in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', offline, re.IGNORECASE):
                if source.startswith("/"):
                    script_path = ROOT / "chat-pwa/public" / source.lstrip("/")
                    if script_path.is_file():
                        offline += "\n" + script_path.read_text(encoding="utf-8")
            for marker in ("localStorage", "Sin conexión", "Offline", "Reintentar", "Retry"):
                if marker not in offline:
                    errors.append(f"offline experience missing locale marker `{marker}`")
        except OSError as exc:
            errors.append(f"could not read offline.html: {exc}")
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
            return pattern in ignore_lines
        # For path patterns like certs/*.pem, check if *.pem or certs/ covers it
        if "/" in pattern:
            parts = pattern.split("/")
            # Check if parent directory is in ignore_lines
            parent = parts[0] + "/"
            if parent in ignore_lines:
                return True
            # Check if file extension glob covers it
            if len(parts) > 1 and parts[-1].startswith("*.") and parts[-1] in ignore_lines:
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


def _single_match(path: Path, pattern: str) -> str | None:
    """Return one captured value without making the readiness check crash."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else None


def check_release_contract() -> list[str]:
    """Check that the source, docs, and release workflow describe one release."""
    errors: list[str] = []
    version_sources = {
        "pyproject.toml": _single_match(ROOT / "pyproject.toml", r'^version\s*=\s*"([^"]+)"$'),
        "chat-pwa/package.json": _single_match(ROOT / "chat-pwa/package.json", r'^\s*"version":\s*"([^"]+)"'),
        "chat-pwa/package-lock.json": _single_match(ROOT / "chat-pwa/package-lock.json", r'^\s*"version":\s*"([^"]+)"'),
        "trinaxai_cli/app.py": _single_match(ROOT / "trinaxai_cli/app.py", r'^VERSION\s*=\s*"([^"]+)"$'),
        "scripts/source_update.py": _single_match(
            ROOT / "scripts/source_update.py", r'^RELEASE_VERSION\s*=\s*"([^"]+)"$'
        ),
        "trinaxai_manager.py": _single_match(ROOT / "trinaxai_manager.py", r'^RELEASE_VERSION\s*=\s*"([^"]+)"$'),
        "install.sh": _single_match(ROOT / "install.sh", r"TRINAXAI_RELEASE_VERSION:-([^}]+)\}"),
        "install.ps1": _single_match(
            ROOT / "install.ps1",
            r'\$ReleaseVersion\s*=.*?else\s*\{\s*"([^"]+)"\s*\}',
        ),
    }
    missing = [name for name, version in version_sources.items() if version is None]
    if missing:
        errors.append(f"release version is not discoverable in: {', '.join(missing)}")
        return errors
    versions = set(version_sources.values())
    if len(versions) != 1:
        details = ", ".join(f"{name}={version}" for name, version in version_sources.items())
        errors.append(f"release versions are inconsistent: {details}")
        return errors
    version = next(iter(versions))

    for readme_name in ("README.md", "README.es.md"):
        readme = ROOT / readme_name
        try:
            text = readme.read_text(encoding="utf-8")
        except OSError:
            errors.append(f"missing release README: {readme_name}")
            continue
        if f"version-{version}" not in text.lower():
            errors.append(f"{readme_name} does not advertise version {version}")
        for asset in RELEASE_MANAGER_ASSETS:
            expected_link = f"releases/download/v{version}/{asset}"
            if expected_link not in text:
                errors.append(f"{readme_name} does not link the versioned Manager asset {asset}")
        if "/releases/latest/download/TrinaxAI-Manager-" in text:
            errors.append(f"{readme_name} uses an unpinned latest Manager asset URL")

    workflow_path = ROOT / ".github/workflows/release.yml"
    try:
        workflow = workflow_path.read_text(encoding="utf-8")
    except OSError:
        errors.append("missing release workflow")
    else:
        if "download-artifact" not in workflow:
            errors.append("release workflow does not collect all Manager artifacts before publishing")
        for asset in RELEASE_MANAGER_ASSETS:
            if asset not in workflow:
                errors.append(f"release workflow does not produce {asset}")
        if "Verify published release assets" not in workflow:
            errors.append("release workflow does not verify published release assets")
        errors.extend(check_release_workflow_security(workflow))

    for doc_name in ("docs/INSTALL_LINUX.md", "docs/INSTALL_LINUX.es.md"):
        text = (ROOT / doc_name).read_text(encoding="utf-8", errors="ignore") if (ROOT / doc_name).is_file() else ""
        if re.search(r"`(?:max|ultra)`", text, re.IGNORECASE):
            errors.append(f"{doc_name} still documents retired hardware profiles")
    windows_installer = ROOT / "install.ps1"
    if windows_installer.is_file():
        text = windows_installer.read_text(encoding="utf-8", errors="ignore")
        if 'ValidateSet("8gb", "16gb", "32gb", "64gb"' not in text:
            errors.append("install.ps1 does not expose the canonical hardware profiles")
        if "qwen3-embedding:8b" in text or "TRINAXAI_PROFILE=$Profile" not in text:
            errors.append("install.ps1 hardware profile/model configuration is stale")
    settings = ROOT / "chat-pwa/src/components/Settings.tsx"
    if settings.is_file() and "qwen3-embedding:8b" in settings.read_text(encoding="utf-8", errors="ignore"):
        errors.append("PWA model settings still advertise the retired qwen3-embedding:8b model")
    matrix_files = (
        "config.py",
        "install.sh",
        "install.ps1",
        "setup_trinaxai.sh",
        "scripts/generate_continue_config.py",
        "continue-config.yaml",
        "chat-pwa/src/lib/api.ts",
    )
    for rel in matrix_files:
        path = ROOT / rel
        if path.is_file() and "qwen3-embedding:8b" in path.read_text(encoding="utf-8", errors="ignore"):
            errors.append(f"{rel} still advertises the retired qwen3-embedding:8b model")
    return errors


def main() -> int:
    files = iter_source_files()
    errors = []
    errors.extend(check_required_files())
    errors.extend(check_local_artifacts())
    errors.extend(check_hardcodes(files))
    errors.extend(check_i18n())
    errors.extend(check_documentation_pairs())
    errors.extend(check_pwa_locales())
    errors.extend(check_secrets(files))
    errors.extend(check_never_commit_files())
    errors.extend(check_tracked_never_commit_files())
    errors.extend(check_release_contract())
    errors.extend(check_required_gates())

    if errors:
        print("Public readiness audit failed:\n")
        for err in errors:
            print(f"- {err}")
        return 1
    print("Public readiness audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
