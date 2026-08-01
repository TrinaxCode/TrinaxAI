from __future__ import annotations

import sys
import types
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from trinaxai_cli.agent import extract


def test_document_detection_and_dispatch_are_case_insensitive(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "REPORT.PDF"
    path.write_bytes(b"pdf")
    monkeypatch.setitem(extract._EXTRACTORS, ".pdf", lambda _path: "  extracted  ")

    assert extract.is_document(path)
    assert extract.extract_document_text(path) == "extracted"
    assert not extract.is_document(tmp_path / "notes.txt")

    with pytest.raises(ValueError, match="unsupported document type"):
        extract.extract_document_text(tmp_path / "notes.txt")


def test_pdf_docx_and_presentation_extract_visible_text(tmp_path: Path, monkeypatch) -> None:
    pdf = types.ModuleType("pypdf")
    pdf.PdfReader = lambda _path: SimpleNamespace(
        pages=[
            SimpleNamespace(extract_text=lambda: " First page "),
            SimpleNamespace(extract_text=lambda: ""),
        ]
    )
    monkeypatch.setitem(sys.modules, "pypdf", pdf)

    docx = types.ModuleType("docx2txt")
    docx.process = lambda _path: "Word body"
    monkeypatch.setitem(sys.modules, "docx2txt", docx)

    pptx = types.ModuleType("pptx")
    pptx.Presentation = lambda _path: SimpleNamespace(
        slides=[
            SimpleNamespace(
                shapes=[
                    SimpleNamespace(has_text_frame=True, text="Title"),
                    SimpleNamespace(has_text_frame=False, text="ignored"),
                ]
            )
        ]
    )
    monkeypatch.setitem(sys.modules, "pptx", pptx)

    assert extract._extract_pdf(tmp_path / "report.pdf") == "[page 1]\nFirst page"
    assert extract._extract_docx(tmp_path / "report.docx") == "Word body"
    assert extract._extract_pptx(tmp_path / "slides.pptx") == "[slide 1]\nTitle"


def test_spreadsheet_and_odf_extract_structured_text(tmp_path: Path, monkeypatch) -> None:
    closed: list[bool] = []
    workbook = SimpleNamespace(
        worksheets=[
            SimpleNamespace(
                title="Data",
                iter_rows=lambda values_only: [("Name", "Value"), ("Aurora", None)],
            )
        ],
        close=lambda: closed.append(True),
    )
    openpyxl = types.ModuleType("openpyxl")
    openpyxl.load_workbook = lambda *_args, **_kwargs: workbook
    monkeypatch.setitem(sys.modules, "openpyxl", openpyxl)

    odf = types.ModuleType("odf")
    odf.teletype = SimpleNamespace(extractText=lambda node: node)
    odf.text = SimpleNamespace(P=object())
    opendocument = types.ModuleType("odf.opendocument")
    opendocument.load = lambda _path: SimpleNamespace(getElementsByType=lambda _kind: [" First ", "", "Second"])
    monkeypatch.setitem(sys.modules, "odf", odf)
    monkeypatch.setitem(sys.modules, "odf.opendocument", opendocument)

    assert extract._extract_xlsx(tmp_path / "data.xlsx") == "[sheet Data]\nName\tValue\nAurora"
    assert closed == [True]
    assert extract._extract_odf(tmp_path / "notes.odt") == " First \nSecond"


def test_rtf_extraction_replaces_invalid_bytes(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "notes.rtf"
    path.write_bytes(b"{\\rtf1 hello \xff}")
    striprtf = types.ModuleType("striprtf")
    child = types.ModuleType("striprtf.striprtf")
    child.rtf_to_text = lambda value: value
    monkeypatch.setitem(sys.modules, "striprtf", striprtf)
    monkeypatch.setitem(sys.modules, "striprtf.striprtf", child)

    assert "hello" in extract._extract_rtf(path)


def test_epub_uses_stdlib_for_xhtml_and_lenient_html(tmp_path: Path) -> None:
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "chapter.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Aurora</h1><p>First chapter.</p></body></html>',
        )
        archive.writestr("legacy.html", "<html><body><p>Second chapter.<br></body>")
        archive.writestr("image.png", b"not text")

    text = extract._extract_epub(path)

    assert "[chapter.xhtml]\nAurora\nFirst chapter." in text
    assert "[legacy.html]\nSecond chapter." in text


def test_epub_rejects_excessive_expanded_text(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "large.epub"
    monkeypatch.setattr(extract, "_EPUB_TEXT_LIMIT", 15)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("one.xhtml", "<p>1234</p>")
        archive.writestr("two.xhtml", "<p>5678</p>")

    with pytest.raises(ValueError, match="safe extraction limit"):
        extract._extract_epub(path)
