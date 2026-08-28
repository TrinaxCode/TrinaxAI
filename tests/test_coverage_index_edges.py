from __future__ import annotations

import contextlib
import io
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import config
import index


def test_index_windows_stdout_wrapper_and_lazy_embed_settings(monkeypatch):
    original_stdout = sys.stdout

    class Stream:
        buffer = io.BytesIO()

        def write(self, value):
            return len(value)

        def flush(self):
            return None

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "stdout", Stream())
    try:
        runpy.run_path(str(Path(index.__file__)), run_name="coverage_index_import")
    finally:
        sys.stdout = original_stdout

    index._embed_configured = False
    from llama_index.core.embeddings.mock_embed_model import MockEmbedding

    embedder = MockEmbedding(embed_dim=1)
    monkeypatch.setattr(index.config, "make_embed", lambda: embedder)
    import llama_index.core as llama_core

    index.ensure_embed_settings()
    assert llama_core.Settings.embed_model is embedder


def test_index_splitter_caches_and_batches(monkeypatch):
    import llama_index.core as llama_core
    import llama_index.core.node_parser as node_parser

    class Code:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Sentence:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(node_parser, "CodeSplitter", Code)
    monkeypatch.setattr(node_parser, "SentenceSplitter", Sentence)
    index._code_splitters.clear()
    index._prose_splitter = None
    assert index._code_splitter("python") is index._code_splitter("python")
    assert index._sentence_splitter() is index._sentence_splitter()

    class Vector:
        def __init__(self, batch, **kwargs):
            self.batches = [list(batch)]
            self.kwargs = kwargs

        def insert_nodes(self, batch, **kwargs):
            self.batches.append(list(batch))

    monkeypatch.setattr(llama_core, "VectorStoreIndex", Vector)
    monkeypatch.setattr(index, "INDEX_NODE_BATCH_SIZE", 2)
    progress = []
    monkeypatch.setattr(index, "_emit_embed_progress", lambda done, total: progress.append((done, total)))
    result = index.insert_node_batches(None, [1, 2, 3], initialize=True, storage_context="storage")
    assert result.batches == [[1, 2], [3]]
    assert progress == [(1, 2), (2, 2)]
    existing = Vector([0])
    assert index.insert_node_batches(existing, [4], initialize=False) is existing
    assert existing.batches[-1] == [4]


def test_index_file_loader_dispatch_and_result_errors(monkeypatch):
    loaders = (
        (".pdf", "pdf"),
        (".html", "html"),
        (".ipynb", "notebook"),
        (".eml", "email"),
        (".epub", "epub"),
        (".pptx", "pptx"),
        (".xlsx", "xlsx"),
        (".rtf", "rtf"),
        (".odt", "odf"),
        (".doc", "docx"),
        (".ppt", "pptx-converted"),
        (".xls", "xlsx-converted"),
        (".py", "extracted"),
        (".txt", "text"),
    )
    for extension, label in loaders:
        if label in {"docx", "pptx-converted", "xlsx-converted"}:
            monkeypatch.setattr(index, "_load_converted_office_document", lambda path, target: [target])
        elif label == "text":
            monkeypatch.setattr(index, "_load_text_document", lambda path, result=label: result)
        elif label == "extracted":
            monkeypatch.setattr(index, "EXTRACTOR_EXTS", {".py"})
            monkeypatch.setattr(index, "_load_extracted_documents", lambda path, result=label: [result])
        else:
            function = {
                "pdf": "_load_pdf_documents",
                "html": "_load_html_document",
                "notebook": "_load_notebook_document",
                "email": "_load_email_document",
                "epub": "_load_epub_document",
                "pptx": "_load_pptx_document",
                "xlsx": "_load_xlsx_document",
                "rtf": "_load_rtf_document",
                "odf": "_load_odf_document",
            }[label]
            value = (lambda path, value=label: [value]) if label == "pdf" else (lambda path, value=label: value)
            monkeypatch.setattr(index, function, value)
        expected = {"pptx-converted": "pptx", "xlsx-converted": "xlsx"}.get(label, label)
        assert str(index._load_file_documents(f"file{extension}")[0]).lstrip(".") == expected

    assert index._load_file_documents_result("ok.txt")[1]
    monkeypatch.setattr(index, "_load_file_documents", lambda _path: (_ for _ in ()).throw(RuntimeError("broken")))
    path, documents, error = index._load_file_documents_result("bad.txt")
    assert path == "bad.txt" and documents == [] and isinstance(error, RuntimeError)


def test_index_empty_load_and_prepare_batch_outcomes(monkeypatch, tmp_path: Path):
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    real_build_nodes = index.build_nodes
    assert index.load_docs_with_status([], context).documents == []

    class Document:
        def __init__(self, text, metadata=None):
            self.text = text
            self.metadata = metadata or {}
            self.id_ = ""

    good = Document("content")
    second = Document(" second ")
    paths = [str(tmp_path / name) for name in ("good.txt", "broken.txt", "empty.txt")]

    def load_result(path):
        if path.endswith("broken.txt"):
            return path, [], RuntimeError("read failed")
        if path.endswith("empty.txt"):
            return path, [Document("   ")], None
        return path, [good, second], None

    monkeypatch.setattr(index, "INDEX_LOAD_WORKERS", 2)
    monkeypatch.setattr(index, "_load_file_documents_result", load_result)
    loaded = index.load_docs_with_status(paths, context)
    assert len(loaded.documents) == 2
    assert set(loaded.failures) == {paths[1], paths[2]}
    assert loaded.documents[0].id_.endswith("#0")
    monkeypatch.setattr(index, "load_docs_with_status", lambda *_args, **_kwargs: index.LoadResult(documents=["ok"]))
    assert index.load_docs(paths, context) == ["ok"]

    monkeypatch.setattr(index, "load_docs_with_status", lambda *_args, **_kwargs: index.LoadResult())
    assert index.prepare_batch([], context=context).nodes == []
    document = SimpleNamespace(text="content", metadata={"source_key": "other"})
    monkeypatch.setattr(
        index,
        "load_docs_with_status",
        lambda *_args, **_kwargs: index.LoadResult(documents=[document], loaded_paths={str(tmp_path / "one.txt")}),
    )
    prepared = index.prepare_batch([str(tmp_path / "one.txt")], context=context)
    assert prepared.nodes == []

    document.metadata = {"source_key": context.source_key(str(tmp_path / "one.txt"))}
    monkeypatch.setattr(index, "build_nodes", lambda _documents: (_ for _ in ()).throw(RuntimeError("chunk")))
    prepared = index.prepare_batch([str(tmp_path / "one.txt")], context=context)
    assert "chunk" in prepared.failures[str(tmp_path / "one.txt")]
    monkeypatch.setattr(index, "build_nodes", lambda _documents: [])
    prepared = index.prepare_batch([str(tmp_path / "one.txt")], context=context)
    assert prepared.failures[str(tmp_path / "one.txt")] == "chunking produced no nodes"

    monkeypatch.setattr(index, "build_nodes", lambda _documents: ["node"])
    prepared = index.prepare_batch([str(tmp_path / "one.txt")], context=context)
    assert prepared.nodes == ["node"]
    assert str(tmp_path / "one.txt") in prepared.indexed_paths

    code_document = SimpleNamespace(text="print('x')", metadata={"rel_path": "main.py"})
    monkeypatch.setattr(index, "_code_splitter", lambda _language: (_ for _ in ()).throw(RuntimeError("ast")))
    monkeypatch.setattr(index, "_sentence_splitter", lambda: SimpleNamespace(get_nodes_from_documents=lambda _: []))
    assert real_build_nodes([code_document])


def test_index_recovery_legacy_nodes_and_failure_notice(monkeypatch, tmp_path: Path):
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    empty = SimpleNamespace(metadata={})
    legacy = SimpleNamespace(metadata={"collection_id": "docs", "rel_path": "legacy.txt"})
    identified = SimpleNamespace(
        metadata={
            "collection_id": "docs",
            "source_id": "source",
            "source_root": str(tmp_path),
            "rel_path": "id.txt",
        }
    )
    existing = SimpleNamespace(
        docstore=SimpleNamespace(docs={"empty": empty, "legacy": legacy, "identified": identified})
    )
    update = index.IndexUpdateResult(failures={"legacy.txt": "retry"}, indexed_paths=set())
    published = []
    monkeypatch.setattr(index, "storage_context_for_persist_dir", lambda _path: object())
    monkeypatch.setattr(sys.modules["llama_index.core"], "load_index_from_storage", lambda _storage: existing)
    monkeypatch.setattr(index, "apply_file_updates", lambda *_args, **_kwargs: update)
    monkeypatch.setattr(index, "publish_index_generation", lambda *_args, **kwargs: published.append(kwargs))
    monkeypatch.setattr(index, "print_summary", lambda *_args: None)

    assert index._node_source_key(legacy) == "docs:legacy.txt"
    assert index._node_source_key(identified) == "docs:source:id.txt"
    assert index._node_source_key(empty) is None
    assert index.run_manifest_recovery({}, {}, context) == 0
    assert published


def test_index_full_run_with_only_failed_chunks(monkeypatch, tmp_path: Path):
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    path = str(tmp_path / "bad.txt")
    progress = []
    monkeypatch.setattr(index, "new_storage_context", lambda _path: object())
    monkeypatch.setattr(index, "prepare_batch", lambda *_args, **_kwargs: index.PreparedBatch(failures={path: "bad"}))
    monkeypatch.setattr(index, "emit_progress", lambda *args, **kwargs: progress.append((args, kwargs)))
    monkeypatch.setattr(index, "print_summary", lambda *_args: None)
    assert index.run_full_index([path], {}, context) == 1
    assert progress


def test_index_rolls_back_interrupted_generation_and_main_exit(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "PERSIST_DIR", str(tmp_path / "persist"))
    monkeypatch.setattr(config, "MANIFEST_PATH", str(tmp_path / "persist" / "manifest.json"))
    monkeypatch.setattr(index, "exclusive_process_lock", lambda *_args, **_kwargs: contextlib.nullcontext())
    monkeypatch.setattr(index, "recover_interrupted_transaction", lambda *_args: "rolled_back")
    monkeypatch.setattr(index, "ensure_embed_settings", lambda: None)
    monkeypatch.setattr(index, "collect_files", lambda _root: [])
    monkeypatch.setattr(index, "read_manifest", lambda _context: {})
    monkeypatch.setattr(index, "current_state", lambda *_args: {})
    monkeypatch.setattr(index, "run_full_index", lambda *_args: 0)
    assert index.run_index(str(tmp_path)) == 0

    missing = tmp_path / "missing-main"
    monkeypatch.setattr(config, "PROJECTS_DIRS", [str(missing)])
    exits = []
    monkeypatch.setattr(sys, "exit", exits.append)
    runpy.run_path(str(Path(index.__file__)), run_name="__main__")
    assert exits == [1]
