from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import index as indexer


def test_optional_document_loaders_extract_structured_content(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "manual.pdf"
    pdf.write_bytes(b"%PDF")
    pages = [SimpleNamespace(extract_text=lambda: "First"), SimpleNamespace(extract_text=lambda: "")]
    monkeypatch.setitem(
        sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda *_args, **_kwargs: SimpleNamespace(pages=pages))
    )
    pdf_docs = indexer._load_pdf_documents(str(pdf))
    assert len(pdf_docs) == 1 and "[Page 1]" in pdf_docs[0].text

    text_shape = SimpleNamespace(has_text_frame=True, has_table=False, text="Title")
    cell = lambda value: SimpleNamespace(text=value)
    table_shape = SimpleNamespace(
        has_text_frame=False,
        has_table=True,
        table=SimpleNamespace(rows=[SimpleNamespace(cells=[cell("A"), cell("B")])]),
    )
    slide = SimpleNamespace(
        shapes=[text_shape, table_shape],
        has_notes_slide=True,
        notes_slide=SimpleNamespace(notes_text_frame=SimpleNamespace(text="Speaker note")),
    )
    monkeypatch.setitem(
        sys.modules, "pptx", SimpleNamespace(Presentation=lambda _path: SimpleNamespace(slides=[slide]))
    )
    presentation = indexer._load_pptx_document(str(tmp_path / "deck.pptx"))
    assert "Title" in presentation.text and "A | B" in presentation.text and "Speaker note" in presentation.text

    workbook = SimpleNamespace(
        worksheets=[
            SimpleNamespace(
                title="Data",
                iter_rows=lambda values_only=True: [(1, "two", None), (None, None)],
            )
        ],
        close=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "openpyxl", SimpleNamespace(load_workbook=lambda *_args, **_kwargs: workbook))
    spreadsheet = indexer._load_xlsx_document(str(tmp_path / "sheet.xlsx"))
    assert "[Sheet: Data]" in spreadsheet.text and "1\ttwo" in spreadsheet.text

    rtf = tmp_path / "note.rtf"
    rtf.write_bytes(b"{\\rtf1 hello}")
    monkeypatch.setitem(sys.modules, "striprtf", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "striprtf.striprtf",
        SimpleNamespace(rtf_to_text=lambda _value: "hello"),
    )
    assert indexer._load_rtf_document(str(rtf)).text == "hello"


def test_converted_office_documents_require_converter_and_restore_original_path(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "legacy.doc"
    source.write_bytes(b"legacy")
    monkeypatch.setattr(indexer.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="LibreOffice"):
        indexer._load_converted_office_document(str(source), ".docx")

    monkeypatch.setattr(indexer.shutil, "which", lambda _name: "/usr/bin/libreoffice")

    def convert(command, **_kwargs):
        output = Path(command[command.index("--outdir") + 1]) / "legacy.docx"
        output.write_bytes(b"converted")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    document = SimpleNamespace(metadata={"file_path": "converted.docx"})
    monkeypatch.setattr(indexer.subprocess, "run", convert)
    monkeypatch.setattr(indexer, "_load_file_documents", lambda _path: [document])
    assert indexer._load_converted_office_document(str(source), ".docx")[0].metadata["file_path"] == str(source)


def test_build_nodes_falls_back_when_code_splitter_returns_no_nodes(monkeypatch) -> None:
    document = SimpleNamespace(
        text="def answer():\n    return 'grounded'",
        metadata={"rel_path": "answer.py", "collection_id": "docs", "source_id": "source"},
    )
    monkeypatch.setattr(
        indexer, "_code_splitter", lambda _language: SimpleNamespace(get_nodes_from_documents=lambda _documents: [])
    )
    monkeypatch.setattr(
        indexer, "_sentence_splitter", lambda: SimpleNamespace(get_nodes_from_documents=lambda _documents: [])
    )

    nodes = indexer.build_nodes([document])

    assert len(nodes) == 1
    assert nodes[0].get_content() == document.text
    assert nodes[0].metadata["collection_id"] == "docs"
    assert nodes[0].metadata["source_id"] == "source"


def test_full_index_publishes_only_successful_files(monkeypatch, tmp_path: Path) -> None:
    first = tmp_path / "one.txt"
    second = tmp_path / "two.txt"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    context = indexer.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    state = {
        context.source_key(str(first)): {"hash": "one", "source_id": context.source_id},
        context.source_key(str(second)): {"hash": "two", "source_id": context.source_id},
    }
    prepared = indexer.PreparedBatch(nodes=["node"], indexed_paths={str(first)}, failures={str(second): "bad"})
    published = []
    monkeypatch.setattr(indexer, "prepare_batch", lambda *_args, **_kwargs: prepared)
    fake_index = SimpleNamespace()
    monkeypatch.setattr(indexer, "insert_node_batches", lambda *_args, **_kwargs: fake_index)
    monkeypatch.setattr(
        indexer, "publish_index_generation", lambda index, manifest, **kwargs: published.append((index, manifest))
    )
    monkeypatch.setattr(indexer, "print_summary", lambda *_args: None)

    assert indexer.run_full_index([str(first), str(second)], state, context) == 0
    assert published[0][0] is fake_index
    stored_sources = next(iter(published[0][1].values()))["sources"]
    assert list(stored_sources) == [context.source_id]
    assert indexer.run_full_index([], {}, context) == 1


def test_incremental_noop_and_publication_paths(monkeypatch, tmp_path: Path) -> None:
    context = indexer.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    key = context.source_key_for_relative("guide.md")
    unchanged = {key: {"hash": "same", "source_id": context.source_id}}
    assert indexer.run_incremental(unchanged, unchanged, {key: str(tmp_path / "guide.md")}, context) == 0

    import llama_index.core as llama_core

    fake_index = SimpleNamespace()
    monkeypatch.setattr(llama_core.StorageContext, "from_defaults", lambda **_kwargs: object())
    monkeypatch.setattr(llama_core, "load_index_from_storage", lambda _storage: fake_index)
    update = indexer.IndexUpdateResult(
        total_nodes=1,
        removed_nodes=2,
        indexed_paths={str(tmp_path / "guide.md")},
        failures={str(tmp_path / "bad.md"): "bad"},
    )
    monkeypatch.setattr(indexer, "apply_file_updates", lambda *_args, **_kwargs: update)
    published = []
    monkeypatch.setattr(
        indexer, "publish_index_generation", lambda index, manifest, **kwargs: published.append(manifest)
    )
    monkeypatch.setattr(indexer, "print_summary", lambda *_args: None)
    changed = {key: {"hash": "new", "source_id": context.source_id}}

    assert indexer.run_incremental({}, changed, {key: str(tmp_path / "guide.md")}, context) == 0
    assert published


@pytest.mark.parametrize(
    ("index_exists", "old_state", "expected"),
    [
        (True, {"old": {}}, "incremental"),
        (True, {}, "recovery"),
        (False, {}, "full"),
    ],
)
def test_run_index_dispatches_existing_recovery_and_first_run(
    monkeypatch,
    tmp_path: Path,
    index_exists: bool,
    old_state: dict,
    expected: str,
) -> None:
    monkeypatch.setattr(indexer.os.path, "isdir", lambda _path: True)
    monkeypatch.setattr(indexer, "exclusive_process_lock", lambda *_args, **_kwargs: contextlib.nullcontext())
    monkeypatch.setattr(indexer, "recover_interrupted_transaction", lambda *_args: "committed")
    monkeypatch.setattr(indexer, "ensure_embed_settings", lambda: None)
    path = str(tmp_path / "guide.md")
    monkeypatch.setattr(indexer, "collect_files", lambda _root: [path])
    monkeypatch.setattr(indexer, "read_manifest", lambda _context: old_state)
    monkeypatch.setattr(indexer, "current_state", lambda _paths, context: {context.source_key(path): {"new": True}})
    real_exists = indexer.os.path.exists
    monkeypatch.setattr(
        indexer.os.path,
        "exists",
        lambda value: index_exists if str(value).endswith("docstore.json") else real_exists(value),
    )
    called = []
    monkeypatch.setattr(indexer, "run_incremental", lambda *_args: called.append("incremental") or 0)
    monkeypatch.setattr(indexer, "run_manifest_recovery", lambda *_args: called.append("recovery") or 0)
    monkeypatch.setattr(indexer, "run_full_index", lambda *_args: called.append("full") or 0)

    assert indexer.run_index(str(tmp_path)) == 0
    assert called == [expected]


def test_run_index_reports_missing_root_lock_timeout_and_publication_failure(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert indexer.run_index(str(missing)) == 1

    @contextlib.contextmanager
    def timeout(*_args, **_kwargs):
        raise TimeoutError("busy")
        yield

    monkeypatch.setattr(indexer, "exclusive_process_lock", timeout)
    assert indexer.run_index(str(tmp_path)) == 2

    @contextlib.contextmanager
    def failure(*_args, **_kwargs):
        raise RuntimeError("storage unavailable")
        yield

    monkeypatch.setattr(indexer, "exclusive_process_lock", failure)
    assert indexer.run_index(str(tmp_path)) == 3
