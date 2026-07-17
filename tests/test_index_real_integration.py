from __future__ import annotations

import json
import os

import pytest

import config
import index as index_module

pytestmark = pytest.mark.skipif(
    os.getenv("TRINAXAI_RUN_REAL_INDEX_TEST") != "1",
    reason="requires a running Ollama server and the configured embedding model",
)


def test_real_embedding_index_incremental_lifecycle(tmp_path, monkeypatch) -> None:
    """Exercise extraction, Ollama embeddings, retrieval, replace, and delete."""
    from llama_index.core import StorageContext, load_index_from_storage

    root = tmp_path / "documents"
    storage = tmp_path / "storage"
    root.mkdir()
    source = root / "manual.uncommon-extension"
    source.write_text(
        "El animal guardián del archivo Aurora es el ajolote violeta.",
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(config, "MANIFEST_PATH", str(storage / "manifest.json"))
    monkeypatch.setattr(index_module, "_embed_configured", False)

    assert index_module.run_index(str(root)) == 0
    loaded = load_index_from_storage(StorageContext.from_defaults(persist_dir=str(storage)))
    matches = loaded.as_retriever(similarity_top_k=3).retrieve("¿Qué animal protege el archivo Aurora?")
    assert any("ajolote violeta" in match.node.get_content() for match in matches)

    source.write_text(
        "El animal guardián del archivo Aurora ahora es el quetzal dorado.",
        encoding="utf-8",
    )
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert index_module.run_index(str(root)) == 0
    loaded = load_index_from_storage(StorageContext.from_defaults(persist_dir=str(storage)))
    contents = "\n".join(node.get_content() for node in loaded.docstore.docs.values())
    assert "quetzal dorado" in contents
    assert "ajolote violeta" not in contents

    source.unlink()
    assert index_module.run_index(str(root)) == 0
    loaded = load_index_from_storage(StorageContext.from_defaults(persist_dir=str(storage)))
    assert not loaded.docstore.docs


def test_real_multiple_roots_with_same_relative_path_are_isolated(tmp_path, monkeypatch) -> None:
    from llama_index.core import StorageContext, load_index_from_storage

    root_a = tmp_path / "alpha"
    root_b = tmp_path / "beta"
    storage = tmp_path / "storage"
    root_a.mkdir()
    root_b.mkdir()
    source_a = root_a / "shared.txt"
    source_b = root_b / "shared.txt"
    source_a.write_text("La clave exclusiva de Alpha es AMATISTA.", encoding="utf-8")
    source_b.write_text("La clave exclusiva de Beta es ZAFIRO.", encoding="utf-8")
    monkeypatch.setattr(config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(config, "MANIFEST_PATH", str(storage / "manifest.json"))
    monkeypatch.setattr(index_module, "_embed_configured", False)

    assert index_module.run_index(str(root_a)) == 0
    assert index_module.run_index(str(root_b)) == 0
    loaded = load_index_from_storage(StorageContext.from_defaults(persist_dir=str(storage)))
    contents = "\n".join(node.get_content() for node in loaded.docstore.docs.values())
    assert "AMATISTA" in contents
    assert "ZAFIRO" in contents
    stored_manifest = json.loads((storage / "manifest.json").read_text(encoding="utf-8"))
    assert len(stored_manifest["default:shared.txt"]["sources"]) == 2

    source_a.unlink()
    assert index_module.run_index(str(root_a)) == 0
    loaded = load_index_from_storage(StorageContext.from_defaults(persist_dir=str(storage)))
    contents = "\n".join(node.get_content() for node in loaded.docstore.docs.values())
    assert "AMATISTA" not in contents
    assert "ZAFIRO" in contents
