from __future__ import annotations

from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, VectorStoreQuery

from trinaxai_index_storage import SQLiteVectorStore


def test_sqlite_vector_store_queries_filters_and_persists_only_on_publish(tmp_path) -> None:
    store = SQLiteVectorStore.empty(tmp_path / "active")
    store.add(
        [
            TextNode(id_="alpha", text="alpha", embedding=[1.0, 0.0], metadata={"group": "a"}),
            TextNode(id_="beta", text="beta", embedding=[0.0, 1.0], metadata={"group": "b"}),
        ]
    )

    result = store.query(
        VectorStoreQuery(
            query_embedding=[0.9, 0.1],
            similarity_top_k=2,
            filters=MetadataFilters(filters=[MetadataFilter(key="group", value="a")]),
        )
    )
    assert result.ids == ["alpha"]
    assert not (tmp_path / "active" / "vectors.sqlite3").exists()

    store.persist(str(tmp_path / "staged" / "default__vector_store.json"))
    reloaded = SQLiteVectorStore.for_persist_dir(tmp_path / "staged")
    assert reloaded.query(VectorStoreQuery(query_embedding=[0.0, 1.0], similarity_top_k=1)).ids == ["beta"]


def test_sqlite_vector_store_migrates_legacy_json(tmp_path) -> None:
    from llama_index.core.vector_stores.simple import SimpleVectorStore

    legacy = SimpleVectorStore()
    legacy.add([TextNode(id_="legacy", text="legacy", embedding=[1.0, 0.0], metadata={"kind": "old"})])
    legacy.persist(str(tmp_path / "default__vector_store.json"))

    store = SQLiteVectorStore.for_persist_dir(tmp_path)

    assert (tmp_path / "vectors.sqlite3").is_file()
    assert store.query(VectorStoreQuery(query_embedding=[1.0, 0.0], similarity_top_k=1)).ids == ["legacy"]
