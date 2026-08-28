import io
import tarfile
import zipfile
from pathlib import Path

import pytest

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

    update(root, archive.as_uri())
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

    with pytest.raises(SystemExit, match="unsafe path"):
        update(root, archive.as_uri())

    assert not (tmp_path / "outside.txt").exists()
