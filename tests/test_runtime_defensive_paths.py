"""Defensive paths of usage accounting and private-storage hardening."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from app.services import runtime_context, runtime_usage


def test_usage_records_normalise_hostile_input() -> None:
    normalise = runtime_usage._normalize_usage_record
    assert normalise("not a dict") is None
    assert normalise({"ts": "nope"}) is None  # an unparseable timestamp drops the record
    assert normalise({"engine": "rag"}, allow_missing_timestamp=True)["ts"] == 0.0  # legacy summary rows
    assert normalise({"engine": "rag"}) is None

    class Unprintable:
        def __str__(self) -> str:
            raise RuntimeError("no text form")

    record = normalise({"ts": 5, "project": Unprintable(), "collections": [f"c{n}" for n in range(80)]})
    assert record is not None and record["project"] is None
    assert len(record["collections"]) == 50  # collection fan-out is capped
    assert normalise({"ts": 5, "collections": ["unknown", ""]})["collections"] == []


def test_retention_ignores_unusable_clocks() -> None:
    records = [{"ts": 1.0, "engine": "rag"}]
    assert runtime_usage._retained_usage_records(records, now=float("inf")) == []
    assert runtime_usage._retained_usage_records(records, now="yesterday") == []
    assert runtime_usage._retained_usage_records(records, now=float("nan")) == []


def test_usage_log_write_removes_its_temporary_file_when_the_replace_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "usage.jsonl"
    runtime = runtime_usage._runtime()

    def broken_replace(_src, _dst):
        raise OSError("disk full")

    monkeypatch.setattr(runtime.os, "replace", broken_replace)
    with pytest.raises(OSError):
        runtime_usage._write_usage_log_unlocked([{"ts": 1.0, "engine": "rag", "model": "m"}], path=str(target))
    assert list(tmp_path.iterdir()) == []  # no orphaned temp file is left behind


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_private_directory_hardening_tightens_files_and_skips_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "store"
    (root / "sub").mkdir(parents=True)
    secret = root / "sub" / "doc.json"
    secret.write_text("{}")
    os.chmod(secret, 0o644)
    outside = tmp_path / "outside.txt"
    outside.write_text("x")
    os.chmod(outside, 0o644)
    (root / "link").symlink_to(outside)  # must never be followed

    descriptor = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        runtime_context._harden_private_directory_fd(descriptor)
    finally:
        os.close(descriptor)

    assert stat.S_IMODE(secret.stat().st_mode) == runtime_context.PRIVATE_FILE_MODE
    assert stat.S_IMODE((root / "sub").stat().st_mode) == runtime_context.PRIVATE_DIRECTORY_MODE
    assert stat.S_IMODE(outside.stat().st_mode) == 0o644  # the symlink target is untouched


def test_pdf_page_pixel_estimate_handles_missing_and_hostile_page_boxes() -> None:
    from types import SimpleNamespace

    from app.services import document_service

    unknown = document_service._OCR_UNKNOWN_PAGE_PIXELS
    assert document_service._pdf_page_pixels(SimpleNamespace(), 300) == unknown  # no mediabox at all
    assert (
        document_service._pdf_page_pixels(SimpleNamespace(mediabox=SimpleNamespace(width="x", height=1)), 300)
        == unknown
    )
    assert document_service._pdf_page_pixels(SimpleNamespace(mediabox=SimpleNamespace()), 300) == unknown
    over_budget = document_service._OCR_MAX_PIXELS + 1
    for width, height in ((0, 100), (-5, 100), (float("inf"), 100), (100, float("nan"))):
        box = SimpleNamespace(width=width, height=height)
        assert document_service._pdf_page_pixels(SimpleNamespace(mediabox=box), 300) == over_budget
    letter = SimpleNamespace(mediabox=SimpleNamespace(width=612, height=792))
    assert document_service._pdf_page_pixels(letter, 72) == 612 * 792


def test_recent_sessions_skip_corrupt_lines_and_unreadable_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from trinaxai_cli.session import Session

    good = tmp_path / "agent-good.jsonl"
    good.write_text('{"role": "user", "content": "first"}\nnot json at all\n{"role": "assistant", "content": "a"}\n')
    broken = tmp_path / "agent-broken.jsonl"
    broken.write_text('{"role": "user", "content": "x"}\n')

    original = Path.open

    def flaky(self, *args, **kwargs):
        if self.name == "agent-broken.jsonl":
            raise OSError("permission denied")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", flaky)
    recent = Session.list_recent("agent-", tmp_path)
    assert [item["name"] for item in recent] == ["agent-good"]
    assert recent[0]["turns"] == 1 and recent[0]["preview"] == "first"
