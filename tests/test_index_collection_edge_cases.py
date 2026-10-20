from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import config
import index


def test_collect_files_filters_hidden_links_and_oversized_files(tmp_path: Path, monkeypatch) -> None:
    visible = tmp_path / "visible.txt"
    visible.write_text("keep", encoding="utf-8")
    (tmp_path / ".private.txt").write_text("skip", encoding="utf-8")
    oversized = tmp_path / "oversized.txt"
    oversized.write_text("too large", encoding="utf-8")
    binary = tmp_path / "opaque.custom"
    binary.write_bytes(b"\x00\x01\xff")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(visible)
    except OSError:
        link = None
    monkeypatch.setattr(config, "max_file_bytes", lambda path: 0 if Path(path).name == "oversized.txt" else 1024)

    names = {Path(path).name for path in index.collect_files(str(tmp_path))}

    assert names == {visible.name}
    assert link is None or link.name not in names


def test_text_detector_handles_empty_invalid_and_unreadable_files(tmp_path: Path, monkeypatch) -> None:
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    invalid = tmp_path / "invalid.bin"
    invalid.write_bytes(b"text\x90\x90")
    controls = tmp_path / "controls.bin"
    controls.write_bytes(b"\x01" * 100)
    assert index._is_probably_text_file(str(empty)) is True
    assert index._is_probably_text_file(str(invalid)) is False
    assert index._is_probably_text_file(str(controls)) is False
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    assert index._is_probably_text_file(str(empty)) is False


def test_legacy_path_and_decoder_edge_cases(monkeypatch) -> None:
    monkeypatch.setattr(index.os.path, "relpath", lambda *_args: (_ for _ in ()).throw(ValueError()))
    assert index._rel("C:\\outside") == "C:/outside"
    assert index._decode_text_bytes("hello".encode("utf-16")) == "hello"
    with pytest.raises(ValueError, match="no extractable text"):
        index._document("blank.txt", " \n")


def test_source_context_rejects_paths_outside_root(tmp_path: Path) -> None:
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    with pytest.raises(ValueError, match="outside source root"):
        context.relative_path(str(tmp_path.parent / "outside.txt"))
    assert index._source_key(str(tmp_path / "guide.md"), context).startswith("docs:source:")


def test_file_dispatch_covers_supported_loaders(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake(name):
        def load(*args):
            path = args[0]
            calls.append((name, path))
            return [name]

        return load

    for name in (
        "_load_pdf_documents",
        "_load_html_document",
        "_load_notebook_document",
        "_load_email_document",
        "_load_epub_document",
        "_load_pptx_document",
        "_load_xlsx_document",
        "_load_rtf_document",
        "_load_odf_document",
        "_load_converted_office_document",
        "_load_extracted_documents",
        "_load_text_document",
    ):
        monkeypatch.setattr(index, name, fake(name))

    for extension in (".pdf", ".html", ".ipynb", ".eml", ".epub", ".pptx", ".xlsx", ".rtf", ".odt"):
        assert index._load_file_documents(f"file{extension}")
    for extension in (".doc", ".ppt", ".xls"):
        assert index._load_file_documents(f"file{extension}")
    assert index._load_file_documents("file.docx")
    assert index._load_file_documents("file.txt")
    assert len(calls) == 14


def test_loader_result_and_status_preserve_actionable_failures(tmp_path: Path, monkeypatch) -> None:
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    good = str(tmp_path / "good.txt")
    bad = str(tmp_path / "bad.txt")
    blank = str(tmp_path / "blank.txt")
    result_path, result_docs, result_error = index._load_file_documents_result(str(tmp_path / "missing.txt"))
    assert result_path.endswith("missing.txt") and result_docs == []
    assert isinstance(result_error, FileNotFoundError)
    document = SimpleNamespace(text="knowledge", metadata={}, id_=None)
    monkeypatch.setattr(index, "INDEX_LOAD_WORKERS", 1)
    monkeypatch.setattr(
        index,
        "_load_file_documents_result",
        lambda path: (
            (path, [document], None)
            if path == good
            else (path, [], RuntimeError("parser failed"))
            if path == bad
            else (path, [SimpleNamespace(text=" ", metadata={}, id_=None)], None)
        ),
    )
    result = index.load_docs_with_status([good, bad, blank], context)
    assert result.loaded_paths == {good}
    assert result.failures == {bad: "parser failed", blank: "no extractable text"}
    assert result.documents[0].id_ == "docs:source:good.txt"
    assert result.documents[0].metadata["project"] == tmp_path.name


def test_build_nodes_falls_back_from_ast_to_sentence_splitter(monkeypatch) -> None:
    class FailingCode:
        def get_nodes_from_documents(self, _docs):
            raise RuntimeError("unsupported syntax")

    class Sentence:
        def get_nodes_from_documents(self, docs):
            return [f"node:{docs[0].metadata['rel_path']}"]

    monkeypatch.setattr(index, "_code_splitter", lambda _language: FailingCode())
    monkeypatch.setattr(index, "_sentence_splitter", lambda: Sentence())
    docs = [
        SimpleNamespace(metadata={"rel_path": "broken.py"}),
        SimpleNamespace(metadata={"rel_path": "guide.md"}),
    ]
    assert index.build_nodes(docs) == ["node:broken.py", "node:guide.md"]


def test_office_conversion_reports_subprocess_failure(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "legacy.doc"
    source.write_bytes(b"legacy")
    monkeypatch.setattr(index.shutil, "which", lambda _name: "/usr/bin/libreoffice")
    monkeypatch.setattr(
        index.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="bad format")
    )
    with pytest.raises(RuntimeError, match="bad format"):
        index._load_converted_office_document(str(source), ".docx")
