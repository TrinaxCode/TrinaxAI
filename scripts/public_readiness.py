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
    "chat-pwa/package.json",
    "chat-pwa/public/manifest.en.webmanifest",
    "chat-pwa/public/manifest.es.webmanifest",
    "chat-pwa/public/offline.html",
    "trinaxai_cli/i18n.py",
]
INSTALL_SURFACE_FILES = (
    "install.sh",
    "install.ps1",
    "README.md",
    "README.es.md",
    "TESTING.md",
    "TESTING.es.md",
    "docs/README.md",
    "docs/README.es.md",
    "docs/INSTALL_LINUX.md",
    "docs/INSTALL_LINUX.es.md",
    "docs/INSTALL_MACOS.md",
    "docs/INSTALL_MACOS.es.md",
    "docs/INSTALL_WINDOWS.md",
    "docs/INSTALL_WINDOWS.es.md",
)
UNPINNED_INSTALL_MARKERS = (
    "raw.githubusercontent.com/TrinaxCode/TrinaxAI/main",
    "github.com/TrinaxCode/TrinaxAI/archive/refs/heads/main",
)
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
RELEASE_ACTION_REF = re.compile(r"^\s*(?:-\s*)?uses:\s*([^@\s]+)@([^\s#]+)")
EXACT_BUILD_VERSION = re.compile(r"\"\d+\.\d+\.\d+\"")


def _read_ci_workflow() -> str:
    try:
        return (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    except OSError:
        return ""


def _workflow_code(workflow: str) -> str:
    """Ignore comments so readiness markers cannot be satisfied by prose."""
    return "\n".join(line.split("#", 1)[0] for line in workflow.splitlines())


def check_ci_workflow_contract(workflow: str) -> list[str]:
    """Keep the required publication gates visible and fail-closed."""
    errors: list[str] = []
    code = _workflow_code(workflow)
    required_commands = (
        ("Ruff lint", r"(?m)^\s*run:\s+ruff\s+check\s+\.\s*$"),
        ("Ruff format check", r"(?m)^\s*run:\s+ruff\s+format\s+--check\s+\.\s*$"),
        ("Mypy gradual boundary", r"(?m)^\s*run:\s+mypy\s*$"),
        ("branch coverage", r"(?m)^\s*--cov-branch\s*$"),
        ("coverage threshold", r"(?m)^\s*--cov-report=.*--cov-fail-under=98\s*$"),
        ("deterministic RAG", r"(?m)^\s*run:\s+python\s+scripts/evaluate_rag\.py\s+--deterministic\b"),
        ("frontend coverage", r"(?m)^\s*run:\s+npm\s+run\s+test:coverage\s*$"),
        ("TypeScript check", r"(?m)^\s*run:\s+npx\s+tsc\s+--noEmit\s*$"),
        ("ESLint", r"(?m)^\s*run:\s+npm\s+run\s+lint\s*$"),
        ("Build PWA", r"(?m)^\s*run:\s+npm\s+run\s+build\s*$"),
        ("frontend bundle budgets", r"(?m)^\s*run:\s+npm\s+run\s+check:bundle\s*$"),
    )
    for marker, pattern in required_commands:
        if not re.search(pattern, code):
            errors.append(f"CI workflow is missing required gate: {marker}")
    if re.search(r"(?m)^\s*continue-on-error\s*:", code):
        errors.append("CI publication gates must not use continue-on-error")
    if not re.search(r"(?m)^\s*run:\s+.*scripts/evaluate_rag\.py\s+--deterministic(?:\s|$)", code):
        errors.append("CI must run the deterministic RAG fixture as its own gate")
    if not re.search(r"(?m)^\s*run:\s+.*scripts/evaluate_rag\.py\s+--ollama-smoke(?:\s|$)", code):
        errors.append("CI must expose a separate live Ollama smoke")
    if "workflow_dispatch:" not in code or "run_ollama_smoke" not in code:
        errors.append("live Ollama smoke must be an explicit workflow dispatch option")
    if not re.search(
        r"(?m)^\s*if:\s*github\.event_name\s*==\s*'workflow_dispatch'\s*&&\s*inputs\.run_ollama_smoke\s*==\s*true",
        code,
    ):
        errors.append("live Ollama smoke must be opt-in and manually triggered")
    return errors


def check_release_workflow_security(workflow: str, ci_workflow: str | None = None) -> list[str]:
    """Keep tagged release publication signed, fail-closed, and reproducible.

    This is intentionally dependency-free rather than a full YAML parser.  The
    critical controls are therefore matched as uncommented, executable lines;
    workflow review remains responsible for YAML structure outside these gates.
    """
    errors: list[str] = []
    action_refs = []
    code = _workflow_code(workflow)
    ci_workflow = _read_ci_workflow() if ci_workflow is None else ci_workflow
    workflows = (("release", workflow), ("CI", ci_workflow))
    for label, source in workflows:
        for line in source.splitlines():
            if "uses:" not in line or "./" in line:
                continue
            match = RELEASE_ACTION_REF.match(line)
            if not match:
                errors.append(f"{label} action is not pinned immutably: {line.strip()}")
                continue
            action, ref = match.groups()
            action_refs.append(action)
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                errors.append(f"{label} action {action} is not pinned to a commit SHA")
    if not action_refs:
        errors.append("release workflow has no externally pinned actions")

    combined = "\n".join(source for _label, source in workflows)
    if re.search(r"(?:runs-on:|\bos:)\s*[^\n]*-latest\b", combined):
        errors.append("release or transitive CI workflow uses a mutable latest runner")
    python_versions = re.findall(r"python-version:\s*([^\s#]+)", combined)
    if not python_versions or any(not EXACT_BUILD_VERSION.fullmatch(value) for value in python_versions):
        errors.append("release and transitive CI workflows must use exact Python toolchain versions")
    node_versions = re.findall(r"node-version:\s*([^\s#]+)", combined)
    if not node_versions or any(not EXACT_BUILD_VERSION.fullmatch(value) for value in node_versions):
        errors.append("release and transitive CI workflows must use exact Node toolchain versions")
    for tool in ("pip", "setuptools", "wheel"):
        if not re.search(rf"['\"]{tool}==\d+(?:\.\d+){{1,2}}['\"]", workflow):
            errors.append(f"release workflow must pin {tool}")

    command_markers = (
        (
            "release signing credential guard",
            r'if\s+\[\[\s+-z\s+"\$RELEASE_SIGNING_KEY_BASE64"\s+\|\|\s+-z\s+"\$RELEASE_SIGNING_KEY_PASSPHRASE"\s+\|\|\s+-z\s+"\$RELEASE_SIGNING_KEY_FINGERPRINT"\s+\]\];\s+then',
        ),
        ("gpg --batch --verify", r"gpg\s+--batch\s+--verify\b"),
        ("gpg --detach-sign", r"gpg\s+--detach-sign\b"),
        ("cosign sign --yes", r"cosign\s+sign\s+--yes\b"),
        ("cosign verify", r"cosign\s+verify\b"),
        (
            "gpg --batch --import TrinaxAI-release-signing-key.asc",
            r"gpg\s+--batch\s+--import\s+TrinaxAI-release-signing-key\.asc\b",
        ),
        ("sha256sum --check SHA256SUMS", r"sha256sum\s+--check\s+SHA256SUMS\b"),
        (
            "release-key fingerprint comparison",
            r'test\s+"\$\{actual_fingerprint\^\^\}"\s*=\s*"\$\{expected_fingerprint\^\^\}"',
        ),
        ("SOURCE_DATE_EPOCH export", r"export\s+SOURCE_DATE_EPOCH="),
        ("draft release creation", r"gh\s+release\s+create\b"),
        ("draft release flag", r"--draft(?:\s|$)"),
        ("published release edit", r"gh\s+release\s+edit\b[^\n]*--draft=false"),
    )
    for marker, pattern in command_markers:
        if not re.search(rf"(?m)^\s*{pattern}", code):
            errors.append(f"release workflow is missing signing control: {marker}")
    if not re.search(r'(?m)^\s*if\s+\[\[\s+"\$is_draft"\s+!=\s+"true"\s+\]\];\s+then', code):
        errors.append("release workflow must refuse overwriting an already-published release")
    if not re.search(r"(?m)^\s*cosign-release:\s*v2\.5\.3\s*$", code):
        errors.append("release workflow must pin the cosign release")
    if "env.WINDOWS_SIGNING_CERTIFICATE_BASE64 != ''" in workflow:
        errors.append("Windows signing must not be optional")
    if "env.MACOS_SIGNING_CERTIFICATE_BASE64 != ''" in workflow:
        errors.append("macOS signing must not be optional")
    if re.search(r"if:\s*runner\.os == '(?:Windows|macOS)'\s*&&", workflow):
        errors.append("platform signing must not be conditional on secret presence")
    signing = code.find("name: Sign and verify release assets")
    staging = code.find("name: Stage draft release with assets")
    container_signing = code.find("name: Sign and verify container images")
    publishing = code.find("name: Publish verified release")
    verification = code.find("name: Verify published release assets")
    if min(signing, staging, container_signing, publishing, verification) < 0 or not (
        signing < staging < container_signing < publishing < verification
    ):
        errors.append("release must stay draft until assets and container are signed, then verify publication")
    if len(re.findall(r"(?m)^\s*gpg\s+--batch\s+--verify\b", code)) < 2:
        errors.append("release workflow must verify signatures with gpg --batch --verify before and after publication")
    if not re.search(r'(?m)^\s*for\s+signature\s+in\s+"\$\{signatures\[@\]\}"', code):
        errors.append("release workflow must verify every published detached signature")
    if not re.search(r'(?m)^\s*\[\[\s+-n\s+"\$asset"\s+&&\s+-f\s+"\$asset"\s+&&\s+-f\s+"\$asset\.asc"\s+\]\]', code):
        errors.append("release workflow must require a signature for every checksummed asset")
    return errors


def required_gate_commands() -> tuple[tuple[str, tuple[str, ...], Path], ...]:
    """Return the release gates that must run before readiness can pass."""
    npm = "npm.cmd" if os.name == "nt" else "npm"
    return (
        ("Python lint", (sys.executable, "-m", "ruff", "check", "."), ROOT),
        ("Python format", (sys.executable, "-m", "ruff", "format", "--check", "."), ROOT),
        ("Python typecheck", (sys.executable, "-m", "mypy"), ROOT),
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
        (
            "Deterministic RAG",
            (sys.executable, "scripts/evaluate_rag.py", "--deterministic", "--output", "-"),
            ROOT,
        ),
        ("Frontend lint", (npm, "run", "lint"), ROOT / "chat-pwa"),
        ("TypeScript typecheck", (npm, "run", "typecheck"), ROOT / "chat-pwa"),
        ("Frontend coverage", (npm, "run", "test:coverage"), ROOT / "chat-pwa"),
        ("PWA build", (npm, "run", "build"), ROOT / "chat-pwa"),
        ("Frontend bundle budget", (npm, "run", "check:bundle"), ROOT / "chat-pwa"),
    )


def check_required_gates() -> list[str]:
    """Run release gates without logging command output."""
    errors: list[str] = []
    for label, command, cwd in required_gate_commands():
        print(f"[gate] {label}: running")
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


def check_install_surfaces() -> list[str]:
    """Reject executable TrinaxAI bootstrap/archive references tied to ``main``."""
    errors: list[str] = []
    for rel in INSTALL_SURFACE_FILES:
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for marker in UNPINNED_INSTALL_MARKERS:
            if marker in text:
                errors.append(f"{rel} contains an unpinned TrinaxAI install reference: {marker}")
    return errors


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
    errors.extend(check_install_surfaces())

    for readme_name in ("README.md", "README.es.md"):
        readme = ROOT / readme_name
        try:
            text = readme.read_text(encoding="utf-8")
        except OSError:
            errors.append(f"missing release README: {readme_name}")
            continue
        if f"version-{version}" not in text.lower():
            errors.append(f"{readme_name} does not advertise version {version}")
        if "TrinaxAI-Manager" in text or "trinaxai_manager" in text:
            errors.append(f"{readme_name} still advertises the removed desktop Manager")
        if "releases/download/v${version}" not in text or "TrinaxAI-${version}-installer.sh" not in text:
            errors.append(f"{readme_name} is missing the Unix release-pinned installer")
        if "releases/download/v$version" not in text or "TrinaxAI-$version-installer.ps1" not in text:
            errors.append(f"{readme_name} is missing the Windows release-pinned installer")

    workflow_path = ROOT / ".github/workflows/release.yml"
    ci_workflow = _read_ci_workflow()
    if not ci_workflow:
        errors.append("missing CI workflow")
    else:
        errors.extend(check_ci_workflow_contract(ci_workflow))
    try:
        workflow = workflow_path.read_text(encoding="utf-8")
    except OSError:
        errors.append("missing release workflow")
    else:
        if any(marker in workflow for marker in ("trinaxai_manager", "build_manager", "TrinaxAI-Manager")):
            errors.append("release workflow still contains the removed desktop Manager")
        if "Verify published release assets" not in workflow:
            errors.append("release workflow does not verify published release assets")
        errors.extend(check_release_workflow_security(workflow, ci_workflow))

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
    secret_errors = check_secrets(files)
    if secret_errors:
        errors.append(f"secret scan found {len(secret_errors)} potential issue(s)")
    errors.extend(check_never_commit_files())
    errors.extend(check_tracked_never_commit_files())
    errors.extend(check_release_contract())
    errors.extend(check_required_gates())

    if errors:
        print("Public readiness audit failed:\n")
        for err in errors:
            print(f"- {err}")
        return 1
    print("Public readiness checks passed; deterministic RAG evidence is present, but no live Ollama evidence was run.")
    print("Run `python scripts/evaluate_rag.py --ollama-smoke` for direct model evidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
