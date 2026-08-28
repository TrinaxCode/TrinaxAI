from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest

from trinaxai_cli.commands import export
from trinaxai_cli.session import Session

RECORDS = [
    {"role": "user", "content": "hello", "ts": 1000},
    {"role": "assistant", "content": "hi there", "ts": 1001},
]


def test_export_supports_markdown_pdf_and_word(tmp_path) -> None:
    expected = {
        "md": ("session.md", lambda path: "# TrinaxAI session: report" in path.read_text(encoding="utf-8")),
        "pdf": ("session.pdf", lambda path: path.read_bytes().startswith(b"%PDF-1.4")),
        "docx": ("session.docx", lambda path: "hello" in ZipFile(path).read("word/document.xml").decode()),
    }
    for fmt, (filename, check) in expected.items():
        output = tmp_path / filename
        with patch.object(Session, "load", return_value=RECORDS):
            result = export.run(
                SimpleNamespace(session="report", format=fmt, output=str(output)), MagicMock(), MagicMock(), MagicMock()
            )
        assert result == 0
        assert output.is_file()
        assert check(output)


def test_export_rejects_unknown_format_and_invalid_output(tmp_path) -> None:
    ui = MagicMock()
    with patch.object(Session, "load", return_value=RECORDS):
        assert export.run(SimpleNamespace(session="report", format="html", output=None), None, ui, None) == 1
    ui.error.assert_called_once()

    ui.reset_mock()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    with patch.object(Session, "load", return_value=RECORDS):
        assert export.run(SimpleNamespace(session="report", format="md", output=str(output_dir)), None, ui, None) == 1
    ui.error.assert_called_once()


def test_export_formats_are_exposed_for_parser_integration() -> None:
    assert export.SUPPORTED_FORMATS == ("md", "pdf", "docx")


@pytest.mark.parametrize("fmt", ["md", "pdf", "docx"])
def test_export_keeps_public_research_metadata_and_sources(tmp_path, fmt) -> None:
    records = [
        {
            "role": "assistant",
            "content": "Verified answer",
            "ts": 1002,
            "meta": {
                "mode": "deep_research",
                "research": {
                    "passes": 3,
                    "search_query": "official query",
                    "sources": [{"title": "Official source", "url": "https://example.test", "page": 2}],
                    "api_key": "nested-secret",
                },
                "api_key": "must-not-export",
            },
        }
    ]
    output = tmp_path / f"research.{fmt}"
    with patch.object(Session, "load", return_value=records):
        assert (
            export.run(
                SimpleNamespace(session="research", format=fmt, output=str(output)), MagicMock(), MagicMock(), None
            )
            == 0
        )
    if fmt == "md":
        content = output.read_text(encoding="utf-8")
    elif fmt == "pdf":
        content = output.read_bytes().decode("cp1252", errors="replace")
    else:
        content = ZipFile(output).read("word/document.xml").decode()
    assert "official query" in content
    assert "Official source" in content
    assert "must-not-export" not in content
    assert "nested-secret" not in content


def test_pdf_lines_split_long_unbroken_text() -> None:
    lines = export._pdf_lines("x" * 25, width=10)
    assert lines == ["xxxxxxxxxx", "xxxxxxxxxx", "xxxxx"]
