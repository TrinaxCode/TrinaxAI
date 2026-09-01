import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import source_update
from scripts.source_update import _extract_archive, _remove_source, finish, update


def test_archive_update_preserves_user_data_and_supports_rollback(tmp_path: Path):
    root = tmp_path / "install"
    source = tmp_path / "TrinaxAI-main"
    root.mkdir()
    source.mkdir()
    (root / ".trinaxai-managed").write_text("managed", encoding="utf-8")
    (root / "old.py").write_text("old", encoding="utf-8")
    (root / ".env").write_text("SECRET=kept", encoding="utf-8")
    (root / "storage").mkdir()
    (root / "storage" / "index").write_text("kept", encoding="utf-8")
    (source / "pyproject.toml").write_text("[project]", encoding="utf-8")
    (source / "new.py").write_text("new", encoding="utf-8")
    (source / "scripts").mkdir()
    (source / "scripts" / "source_update.py").write_text("new updater", encoding="utf-8")
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in source.rglob("*"):
            bundle.write(path, path.relative_to(tmp_path))

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    update(root, archive.as_uri(), digest)
    assert not (root / "old.py").exists()
    assert (root / "new.py").read_text(encoding="utf-8") == "new"
    assert (root / ".env").read_text(encoding="utf-8") == "SECRET=kept"
    assert (root / "storage" / "index").read_text(encoding="utf-8") == "kept"

    finish(root, rollback=True)
    assert (root / "old.py").read_text(encoding="utf-8") == "old"
    assert not (root / "new.py").exists()
    assert not list(tmp_path.glob("trinaxai-previous-*"))


def test_remove_source_keeps_personal_data(tmp_path: Path):
    (tmp_path / "app.py").write_text("code", encoding="utf-8")
    (tmp_path / "storage").mkdir()
    (tmp_path / "storage" / "index").write_text("data", encoding="utf-8")
    _remove_source(tmp_path)
    assert not (tmp_path / "app.py").exists()
    assert (tmp_path / "storage" / "index").read_text(encoding="utf-8") == "data"


def test_archive_update_rejects_insecure_url_before_changes(tmp_path: Path) -> None:
    (tmp_path / ".trinaxai-managed").write_text("managed", encoding="utf-8")

    with pytest.raises(SystemExit, match="must use HTTPS"):
        update(tmp_path, "http://example.test/release.zip")


def test_tar_package_validation_rejects_traversal_and_links(tmp_path: Path) -> None:
    traversal = tmp_path / "traversal.tar.gz"
    with tarfile.open(traversal, "w:gz") as bundle:
        member = tarfile.TarInfo("TrinaxAI-main/../../outside")
        member.size = 1
        bundle.addfile(member, io.BytesIO(b"x"))
    with pytest.raises(RuntimeError, match="unsafe path"):
        _extract_archive(traversal, tmp_path / "traversal-extracted")

    link = tmp_path / "link.tar.gz"
    with tarfile.open(link, "w:gz") as bundle:
        member = tarfile.TarInfo("TrinaxAI-main/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "/etc/passwd"
        bundle.addfile(member)
    with pytest.raises(RuntimeError, match="unsafe link"):
        _extract_archive(link, tmp_path / "link-extracted")


def test_archive_update_rejects_tar_path_traversal_before_changes(tmp_path: Path) -> None:
    root = tmp_path / "install"
    root.mkdir()
    (root / ".trinaxai-managed").write_text("managed", encoding="utf-8")
    archive = tmp_path / "release.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        member = tarfile.TarInfo("TrinaxAI-main/../outside.txt")
        payload = b"must not escape"
        member.size = len(payload)
        bundle.addfile(member, io.BytesIO(payload))

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with pytest.raises(SystemExit, match="unsafe path"):
        update(root, archive.as_uri(), digest)

    assert not (tmp_path / "outside.txt").exists()


def test_local_archive_without_checksum_fails_before_changes(tmp_path: Path) -> None:
    root = tmp_path / "install"
    source = tmp_path / "TrinaxAI-local"
    root.mkdir()
    source.mkdir()
    (root / ".trinaxai-managed").write_text("managed", encoding="utf-8")
    (root / "existing.py").write_text("keep", encoding="utf-8")
    (source / "pyproject.toml").write_text("[project]", encoding="utf-8")
    (source / "replacement.py").write_text("new", encoding="utf-8")
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in source.rglob("*"):
            bundle.write(path, path.relative_to(tmp_path))

    with pytest.raises(SystemExit, match="checksum"):
        update(root, archive.as_uri())

    assert (root / "existing.py").read_text(encoding="utf-8") == "keep"
    assert not (root / "replacement.py").exists()


def test_latest_release_resolution_requires_stable_assets(monkeypatch) -> None:
    payload = {
        "draft": False,
        "prerelease": False,
        "tag_name": "v2.3.4",
        "assets": [
            {"name": "TrinaxAI-2.3.4.tar.gz", "browser_download_url": "https://evil.test/source"},
            {"name": "SHA256SUMS"},
        ],
    }
    monkeypatch.setattr(source_update, "_read_remote", lambda *_args: json.dumps(payload).encode())

    release = source_update.resolve_latest_release()

    assert release.version == "2.3.4"
    assert release.archive_url == (
        "https://github.com/TrinaxCode/TrinaxAI/releases/download/v2.3.4/TrinaxAI-2.3.4.tar.gz"
    )
    assert "evil.test" not in release.archive_url


def test_source_update_has_no_main_archive_default() -> None:
    assert source_update.ARCHIVE_URL is None


def test_latest_release_rejects_draft_or_prerelease_metadata(monkeypatch) -> None:
    payload = {"draft": True, "prerelease": False, "tag_name": "v2.3.4", "assets": []}
    monkeypatch.setattr(source_update, "_read_remote", lambda *_args: json.dumps(payload).encode())

    with pytest.raises(RuntimeError, match="stable release"):
        source_update.resolve_latest_release()


def test_operator_checksum_is_preserved_for_custom_https_source() -> None:
    digest = "A" * 64
    assert source_update._expected_checksum("https://example.test/source.tar.gz", digest) == digest.lower()


def test_custom_file_source_requires_operator_checksum(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="file.*--sha256"):
        source_update._expected_checksum((tmp_path / "source.tar.gz").as_uri(), None)


def test_release_checksum_matches_requested_archive_name(monkeypatch) -> None:
    digest = "b" * 64
    monkeypatch.setattr(
        source_update,
        "_read_remote",
        lambda *_args: f"{digest}  TrinaxAI-2.3.4.tar.gz\n".encode(),
    )

    assert source_update._release_checksum("https://example.test/SHA256SUMS", "TrinaxAI-2.3.4.tar.gz") == digest
