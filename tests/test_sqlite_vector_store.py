from __future__ import annotations

from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.core.vector_stores.types import (
    MetadataFilter,
    MetadataFilters,
    VectorStoreQuery,
    VectorStoreQueryMode,
)

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
    assert reloaded.query(
        VectorStoreQuery(
            query_embedding=[1.0, 0.0],
            similarity_top_k=2,
            mode=VectorStoreQueryMode.MMR,
            mmr_threshold=1.0,
        )
    ).ids == ["alpha", "beta"]
    assert reloaded.query(
        VectorStoreQuery(
            query_embedding=[1.0, 0.0],
            similarity_top_k=0,
            mode=VectorStoreQueryMode.MMR,
            mmr_threshold=1.0,
        )
    ).ids == ["alpha", "beta"]


def test_sqlite_vector_store_migrates_legacy_json(tmp_path) -> None:
    from llama_index.core.vector_stores.simple import SimpleVectorStore

    legacy = SimpleVectorStore()
    legacy.add([TextNode(id_="legacy", text="legacy", embedding=[1.0, 0.0], metadata={"kind": "old"})])
    legacy.persist(str(tmp_path / "default__vector_store.json"))

    store = SQLiteVectorStore.for_persist_dir(tmp_path)

    assert (tmp_path / "vectors.sqlite3").is_file()
    assert store.query(VectorStoreQuery(query_embedding=[1.0, 0.0], similarity_top_k=1)).ids == ["legacy"]


def test_sqlite_query_is_lazy_and_decodes_only_sql_filtered_dimensions(tmp_path, monkeypatch) -> None:
    source = lambda doc_id: {NodeRelationship.SOURCE: RelatedNodeInfo(node_id=doc_id)}  # noqa: E731
    store = SQLiteVectorStore.empty(tmp_path)
    store.add(
        [
            TextNode(
                id_="keep",
                text="keep",
                embedding=[1.0, 0.0],
                metadata={"group": "a"},
                relationships=source("doc-a"),
            ),
            TextNode(
                id_="metadata-filtered",
                text="filtered",
                embedding=[0.0, 1.0],
                metadata={"group": "b"},
                relationships=source("doc-a"),
            ),
            TextNode(
                id_="wrong-dimensions",
                text="wrong dimensions",
                embedding=[1.0, 0.0, 0.0],
                metadata={"group": "a"},
                relationships=source("doc-a"),
            ),
            TextNode(
                id_="wrong-document",
                text="wrong document",
                embedding=[1.0, 0.0],
                metadata={"group": "a"},
                relationships=source("doc-b"),
            ),
        ]
    )
    store.persist(str(tmp_path / "vectors.sqlite3"))

    decoded_dimensions: list[int] = []
    unpack = SQLiteVectorStore._unpack_embedding
    monkeypatch.setattr(
        SQLiteVectorStore,
        "_read_snapshot",
        classmethod(lambda *_args: (_ for _ in ()).throw(AssertionError("query loaded the full snapshot"))),
    )
    monkeypatch.setattr(
        SQLiteVectorStore,
        "_unpack_embedding",
        staticmethod(lambda blob, dimensions: decoded_dimensions.append(dimensions) or unpack(blob, dimensions)),
    )
    reloaded = SQLiteVectorStore.for_persist_dir(tmp_path)
    result = reloaded.query(
        VectorStoreQuery(
            query_embedding=[1.0, 0.0],
            similarity_top_k=4,
            node_ids=["keep", "metadata-filtered", "wrong-dimensions", "wrong-document"],
            doc_ids=["doc-a"],
            filters=MetadataFilters(filters=[MetadataFilter(key="group", value="a")]),
        )
    )

    assert result.ids == ["keep"]
    assert decoded_dimensions == [2]
    assert reloaded._entries is None
    result = reloaded.query(VectorStoreQuery(query_embedding=[1.0, 0.0], similarity_top_k=0))
    assert result.ids == []
    assert result.similarities == []
    assert decoded_dimensions == [2]


def test_mmr_caches_query_similarity_without_changing_exact_results(tmp_path, monkeypatch) -> None:
    embeddings = [
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    store = SQLiteVectorStore.empty(tmp_path)
    store.add(
        [TextNode(id_=f"node-{index}", text="node", embedding=embedding) for index, embedding in enumerate(embeddings)]
    )
    store.persist(str(tmp_path / "vectors.sqlite3"))
    reloaded = SQLiteVectorStore.for_persist_dir(tmp_path)

    similarity_calls = 0
    similarity_and_norm = SQLiteVectorStore._similarity_and_norm

    def counted_similarity(left, right, left_norm):
        nonlocal similarity_calls
        similarity_calls += 1
        return similarity_and_norm(left, right, left_norm)

    monkeypatch.setattr(SQLiteVectorStore, "_similarity_and_norm", staticmethod(counted_similarity))
    result = reloaded.query(
        VectorStoreQuery(
            query_embedding=[1.0, 0.0, 0.0],
            similarity_top_k=3,
            mode=VectorStoreQueryMode.MMR,
            mmr_threshold=0.5,
        )
    )

    assert result.ids == ["node-0", "node-1", "node-3"]
    assert result.similarities == [0.5, 0.0, 0.0]
    assert similarity_calls == len(embeddings)
    assert reloaded._entries is None
