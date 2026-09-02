#!/usr/bin/env python3
"""Safely replace the source portion of a managed TrinaxAI installation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import NamedTuple
from urllib.parse import urlsplit

REPOSITORY = "TrinaxCode/TrinaxAI"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASE_VERSION = "1.2.1"
ARCHIVE_NAME = f"TrinaxAI-{RELEASE_VERSION}.tar.gz"
RELEASE_ARCHIVE_URL = f"https://github.com/TrinaxCode/TrinaxAI/releases/download/v{RELEASE_VERSION}/{ARCHIVE_NAME}"
CHECKSUM_URL = f"https://github.com/TrinaxCode/TrinaxAI/releases/download/v{RELEASE_VERSION}/SHA256SUMS"
ARCHIVE_URL = None
DOWNLOAD_TIMEOUT = 120
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MARKER = ".trinaxai-update-backup"
BACKUP_PREFIX = ".trinaxai-rollback-"

PRESERVED = {
    ".env",
    ".trinaxai-managed",
    MARKER,
    ".venv",
    "backups",
    "chat-pwa/certs",
    "local_sources",
    "logs",
    "storage",
}

LIFECYCLE_FILES = {
    "backup.sh",
    "install.sh",
    "setup_trinaxai.sh",
    "shutdown_ai.sh",
    "startup_ai.sh",
    "uninstall.sh",
    "update.sh",
}


class ReleaseInfo(NamedTuple):
    version: str
    tag: str
    archive_name: str
    archive_url: str
    checksum_url: str


def _is_preserved(relative: Path, preserved: set[str] | frozenset[str] = PRESERVED) -> bool:
    value = relative.as_posix()
    return any(value == item or value.startswith(f"{item}/") for item in preserved)


def _source_entries(root: Path, preserved: set[str] | frozenset[str] = PRESERVED):
    """Yield source entries without following symlinked directories."""

    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in list(directories):
            path = current_path / name
            relative = path.relative_to(root)
            if _is_preserved(relative, preserved):
                directories.remove(name)
                continue
            yield path, relative
            if path.is_symlink():
                directories.remove(name)
        for name in files:
            path = current_path / name
            relative = path.relative_to(root)
            if not _is_preserved(relative, preserved):
                yield path, relative


def _remove_source(root: Path, preserved: set[str] | frozenset[str] = PRESERVED) -> None:
    entries = [path for path, _ in _source_entries(root, preserved)]
    for path in sorted(entries, key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
            except OSError:
                remaining = path.iterdir()
                if not all(_is_preserved(item.relative_to(root), preserved) for item in remaining):
                    raise
        else:
            path.unlink()


def _assert_destination_safe(root: Path, destination: Path) -> None:
    relative = destination.relative_to(root)
    current = root
    for component in relative.parts[:-1]:
        current /= component
        if current.is_symlink():
            raise RuntimeError("The installation contains an unsafe symbolic-link path.")
    if destination.is_symlink():
        raise RuntimeError("The installation contains an unsafe symbolic link.")


def _copy_source(
    source: Path,
    target: Path,
    preserved: set[str] | frozenset[str] = PRESERVED,
) -> None:
    for path, relative in _source_entries(source, preserved):
        if path.is_symlink():
            raise RuntimeError("The source tree contains an unsupported symbolic link.")
        destination = target / relative
        _assert_destination_safe(target, destination)
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        if not path.is_file():
            raise RuntimeError("The source tree contains an unsupported file type.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def _safe_member_path(name: str) -> PurePosixPath:
    if not name or "\x00" in name or "\\" in name:
        raise RuntimeError("The downloaded package contains an unsafe path.")
    if name.startswith("/") or (len(name) >= 2 and name[1] == ":"):
        raise RuntimeError("The downloaded package contains an unsafe path.")
    raw_parts = name.rstrip("/").split("/")
    if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
        raise RuntimeError("The downloaded package contains an unsafe path.")
    return PurePosixPath(*raw_parts)


def _validate_members(members, *, archive_kind: str) -> tuple[str, list]:
    roots: set[str] = set()
    seen: set[str] = set()
    total_size = 0
    required = set()
    validated = []

    for member in members:
        name = member.filename if archive_kind == "zip" else member.name
        path = _safe_member_path(name)
        normalized = path.as_posix()
        if normalized in seen:
            raise RuntimeError("The downloaded package contains duplicate entries.")
        seen.add(normalized)
        roots.add(path.parts[0])
        relative_to_root = Path(*path.parts[1:]) if len(path.parts) > 1 else Path()
        if relative_to_root != Path() and _is_preserved(relative_to_root):
            raise RuntimeError("The downloaded package contains runtime data.")

        if archive_kind == "zip":
            mode = (member.external_attr >> 16) & 0o170000
            is_directory = member.is_dir()
            is_regular = not is_directory and (mode == 0 or stat.S_ISREG(mode))
            if mode and not (is_directory or stat.S_ISREG(mode)):
                raise RuntimeError("The downloaded package contains an unsafe link or file type.")
            if member.flag_bits & 0x1:
                raise RuntimeError("The downloaded package is encrypted and cannot be verified.")
        else:
            is_directory = member.isdir()
            is_regular = member.isreg()
            if not (is_directory or is_regular):
                raise RuntimeError("The downloaded package contains an unsafe link or file type.")

        size = 0 if is_directory else int(member.file_size if archive_kind == "zip" else member.size)
        if size < 0 or size > MAX_MEMBER_BYTES or total_size + size > MAX_TOTAL_BYTES:
            raise RuntimeError("The downloaded package is too large.")
        total_size += size
        if len(path.parts) == 2 and path.parts[1] == "pyproject.toml":
            required.add("pyproject.toml")
        validated.append((member, path, is_directory, is_regular))

    if len(roots) != 1:
        raise RuntimeError("The downloaded package must contain one source folder.")
    root = next(iter(roots))
    if not root.startswith("TrinaxAI-") or "pyproject.toml" not in required:
        raise RuntimeError("The downloaded package is not a valid TrinaxAI source package.")
    return root, validated


def _write_file(stream, destination: Path, size: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        remaining = size
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError("The downloaded package ended before a file was complete.")
            output.write(chunk)
            remaining -= len(chunk)


def _extract_archive(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        try:
            with zipfile.ZipFile(archive) as bundle:
                root, members = _validate_members(bundle.infolist(), archive_kind="zip")
                for member, path, is_directory, _ in members:
                    target = destination.joinpath(*path.parts)
                    if is_directory:
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    with bundle.open(member) as stream:
                        _write_file(stream, target, member.file_size)
                    mode = (member.external_attr >> 16) & 0o777
                    if mode:
                        os.chmod(target, mode)
        except (OSError, zipfile.BadZipFile) as error:
            raise RuntimeError(f"The downloaded package could not be read: {error}") from error
    else:
        try:
            with tarfile.open(archive, mode="r:*") as bundle:
                root, members = _validate_members(bundle.getmembers(), archive_kind="tar")
                for member, path, is_directory, _ in members:
                    target = destination.joinpath(*path.parts)
                    if is_directory:
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    stream = bundle.extractfile(member)
                    if stream is None:
                        raise RuntimeError("The downloaded package contains an unreadable file.")
                    with stream:
                        _write_file(stream, target, member.size)
                    os.chmod(target, member.mode & 0o777)
        except (OSError, tarfile.TarError) as error:
            raise RuntimeError(f"The downloaded package could not be read: {error}") from error
    extracted = destination / root
    if not extracted.is_dir():
        raise RuntimeError("The downloaded package has no source directory.")
    return extracted


_STABLE_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def _read_remote(url: str, max_bytes: int, description: str = "remote release metadata") -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "TrinaxAI-updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:  # nosec B310
            payload = response.read(max_bytes + 1)
    except (OSError, TimeoutError, urllib.error.URLError, ValueError) as error:
        raise RuntimeError(f"The {description} could not be downloaded: {error}") from error
    if len(payload) > max_bytes:
        raise RuntimeError(f"The {description} is too large.")
    return payload


def _release_info(version: str) -> ReleaseInfo:
    if not _STABLE_VERSION.fullmatch(version):
        raise RuntimeError("The release version must be a stable semantic version.")
    tag = f"v{version}"
    archive_name = f"TrinaxAI-{version}.tar.gz"
    base = f"https://github.com/{REPOSITORY}/releases/download/{tag}"
    return ReleaseInfo(version, tag, archive_name, f"{base}/{archive_name}", f"{base}/SHA256SUMS")


def resolve_latest_release() -> ReleaseInfo:
    """Resolve the latest non-draft, non-prerelease GitHub release.

    The returned URLs are derived from the validated tag rather than copied
    from API-provided URLs, so a response cannot redirect the updater to an
    unrelated host or asset path.
    """

    payload = _read_remote(LATEST_RELEASE_URL, 4 * 1024 * 1024)
    try:
        release = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("The latest release metadata is not valid JSON.") from error
    if not isinstance(release, dict) or release.get("draft") is not False or release.get("prerelease") is not False:
        raise RuntimeError("GitHub did not return a stable release.")
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not re.fullmatch(r"v(\d+\.\d+\.\d+)", tag):
        raise RuntimeError("The latest release has no stable semantic-version tag.")
    info = _release_info(tag[1:])
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("The latest release has no asset list.")
    names = {asset.get("name") for asset in assets if isinstance(asset, dict)}
    if info.archive_name not in names or "SHA256SUMS" not in names:
        raise RuntimeError("The latest release is missing its source archive or checksum manifest.")
    return info


def _release_from_url(url: str) -> ReleaseInfo | None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment:
        return None
    match = re.fullmatch(
        rf"/{re.escape(REPOSITORY)}/releases/download/v(\d+\.\d+\.\d+)/TrinaxAI-(\d+\.\d+\.\d+)\.tar\.gz",
        parsed.path,
    )
    if not match or match.group(1) != match.group(2):
        return None
    return _release_info(match.group(1))


def _release_checksum(checksum_url: str | None = None, archive_name: str | None = None) -> str:
    checksum_url = checksum_url or CHECKSUM_URL
    archive_name = archive_name or ARCHIVE_NAME
    payload = _read_remote(checksum_url, 1024 * 1024, "release checksum manifest")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError("The release checksum manifest is not valid UTF-8.") from error
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1].lstrip("*") == archive_name:
            checksum = fields[0].lower()
            if re.fullmatch(r"[0-9a-f]{64}", checksum):
                return checksum
    raise RuntimeError(f"The release checksum manifest has no valid entry for {archive_name}.")


def _expected_checksum(url: str | None, checksum: str | None) -> str | None:
    if checksum is not None:
        value = checksum.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise RuntimeError("The archive checksum must be a 64-character SHA-256 digest.")
        return value
    if url is None:
        raise RuntimeError("The update source was not resolved to a stable release.")
    release = _release_from_url(url)
    if release is not None:
        return _release_checksum(release.checksum_url, release.archive_name)
    parsed = urlsplit(url)
    if parsed.scheme == "https":
        raise RuntimeError("Custom HTTPS update URLs require --sha256.")
    if parsed.scheme == "file":
        raise RuntimeError("Custom file update URLs require an explicit SHA-256 checksum (--sha256).")
    return None


def _download(url: str, archive: Path, expected_checksum: str | None = None) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "file"} or (parsed.scheme == "https" and not parsed.hostname):
        raise RuntimeError("The update URL must use HTTPS (or a local file URL). Nothing was changed.")
    try:
        # The URL scheme is restricted above; file URLs are only for local maintenance.
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response, archive.open("wb") as output:  # nosec B310
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_ARCHIVE_BYTES:
                raise RuntimeError("The downloaded package is too large.")
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise RuntimeError("The downloaded package is too large.")
                output.write(chunk)
    except (OSError, ValueError, TimeoutError, urllib.error.URLError) as error:
        raise RuntimeError(f"The TrinaxAI download failed: {error}") from error
    if not archive.is_file() or archive.stat().st_size == 0:
        raise RuntimeError("The TrinaxAI download was empty.")
    if expected_checksum is not None:
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != expected_checksum:
            raise RuntimeError("The downloaded package failed SHA-256 verification.")


def _root_path(root: Path) -> Path:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("The installation root must be a real directory.")
    return root.resolve()


def _marker_path(root: Path) -> Path:
    marker = root / MARKER
    if marker.is_symlink():
        raise RuntimeError("The update rollback marker is an unsafe symbolic link.")
    return marker


def _read_backup(root: Path) -> tuple[Path, Path] | None:
    marker = _marker_path(root)
    if not marker.exists():
        return None
    if not marker.is_file():
        raise RuntimeError("The update rollback marker is invalid.")
    value = marker.read_text(encoding="utf-8").strip()
    backup = Path(value).expanduser()
    backup = (root.parent / backup).resolve() if not backup.is_absolute() else backup.resolve()
    if backup.parent != root.parent or not backup.name.startswith(BACKUP_PREFIX) or not backup.is_dir():
        raise RuntimeError("The update rollback backup is outside the installation boundary.")
    return marker, backup


def _write_marker(root: Path, backup: Path) -> None:
    marker = _marker_path(root)
    temporary = root / f"{MARKER}.tmp-{os.getpid()}"
    temporary.write_text(f"{backup}\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, marker)


def _clear_marker(marker: Path, backup: Path) -> None:
    shutil.rmtree(backup)
    marker.unlink()


def _restore(root: Path, backup: Path) -> None:
    _remove_source(root)
    _copy_source(backup, root)


def _recover_pending(root: Path) -> None:
    pending = _read_backup(root)
    if pending is None:
        return
    marker, backup = pending
    _restore(root, backup)
    _clear_marker(marker, backup)


def update(root: Path, url: str | None = ARCHIVE_URL, sha256: str | None = None) -> None:
    try:
        root = _root_path(root)
        if not (root / ".trinaxai-managed").is_file():
            raise RuntimeError(
                "This is not a managed installation. Download a release or use the installer to update safely."
            )
        _recover_pending(root)
        with tempfile.TemporaryDirectory(prefix="trinaxai-update-") as temporary:
            temporary_path = Path(temporary)
            archive = temporary_path / "source-package"
            if url is None:
                url = resolve_latest_release().archive_url
            _download(url, archive, _expected_checksum(url, sha256))
            source = _extract_archive(archive, temporary_path / "source")

            backup = Path(tempfile.mkdtemp(prefix=BACKUP_PREFIX, dir=root.parent))
            try:
                _copy_source(root, backup)
                _write_marker(root, backup)
                _remove_source(root)
                _copy_source(source, root)
            except Exception as error:
                try:
                    _restore(root, backup)
                    marker = _marker_path(root)
                    if marker.exists():
                        _clear_marker(marker, backup)
                except Exception as rollback_error:
                    raise RuntimeError(
                        f"The source update failed and automatic rollback also failed: {rollback_error}"
                    ) from error
                raise
    except SystemExit:
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile, tarfile.TarError) as error:
        raise SystemExit(str(error)) from error


def finish(root: Path, rollback: bool = False) -> None:
    try:
        root = _root_path(root)
        pending = _read_backup(root)
        if pending is None:
            return
        marker, backup = pending
        if rollback:
            _restore(root, backup)
        _clear_marker(marker, backup)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from error


def remove(root: Path) -> None:
    try:
        root = _root_path(root)
        if not (root / ".trinaxai-managed").is_file():
            raise RuntimeError("This is not a managed installation; application files were kept.")
        _recover_pending(root)
        preserved = set(PRESERVED) | LIFECYCLE_FILES
        _remove_source(root, preserved)
        (root / ".trinaxai-managed").unlink(missing_ok=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("update", "finish", "rollback", "remove"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--url", default=ARCHIVE_URL)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.action == "update":
        update(args.root, args.url, args.sha256)
    elif args.action == "remove":
        remove(args.root)
    else:
        finish(args.root, rollback=args.action == "rollback")


if __name__ == "__main__":
    main()
