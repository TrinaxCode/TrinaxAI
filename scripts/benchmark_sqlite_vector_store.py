"""Benchmark streaming DEFAULT and MMR queries on synthetic SQLite snapshots.

Run from the repository root, for example:

    ./.venv/bin/python scripts/benchmark_sqlite_vector_store.py
    ./.venv/bin/python scripts/benchmark_sqlite_vector_store.py --dimensions 768
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import resource
except ImportError:  # pragma: no cover - resource is unavailable on Windows.
    resource = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llama_index.core.vector_stores.types import VectorStoreQuery, VectorStoreQueryMode

from trinaxai_index_storage import SQLiteVectorStore


def _peak_rss_mib() -> float | None:
    if resource is None:
        return None
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024


def _create_snapshot(root: Path, count: int, dimensions: int) -> Path:
    path = root / "vectors.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute(
        "CREATE TABLE embeddings ("
        "node_id TEXT PRIMARY KEY, ref_doc_id TEXT NOT NULL, dimensions INTEGER NOT NULL, "
        "embedding BLOB NOT NULL, metadata TEXT NOT NULL)"
    )
    generator = random.Random(count * 1_000_003 + dimensions)
    rows: list[tuple[str, str, int, bytes, str]] = []
    for index in range(count):
        embedding = struct.pack(f"<{dimensions}f", *(generator.uniform(-1.0, 1.0) for _ in range(dimensions)))
        rows.append((f"node-{index:07d}", f"doc-{index // 8:07d}", dimensions, embedding, "{}"))
        if len(rows) == 256:
            connection.executemany("INSERT INTO embeddings VALUES (?, ?, ?, ?, ?)", rows)
            rows.clear()
    if rows:
        connection.executemany("INSERT INTO embeddings VALUES (?, ?, ?, ?, ?)", rows)
    connection.commit()
    connection.close()
    return path


def _query_snapshot(root: Path, dimensions: int, mode: str, top_k: int) -> None:
    store = SQLiteVectorStore.for_persist_dir(root)
    query = VectorStoreQuery(
        query_embedding=[((index * 17) % 101) / 101.0 for index in range(dimensions)],
        similarity_top_k=top_k,
        mode=VectorStoreQueryMode(mode),
        mmr_threshold=0.5,
    )
    started = time.perf_counter()
    result = store.query(query)
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "mode": mode,
                "seconds": elapsed,
                "results": len(result.ids),
                "peak_rss_mib": _peak_rss_mib(),
            }
        ),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", nargs="+", type=int, default=[10_000, 100_000])
    parser.add_argument("--dimensions", type=int, default=384)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--query", nargs=4, metavar=("ROOT", "DIMENSIONS", "MODE", "TOP_K"))
    args = parser.parse_args()

    if args.query:
        root, dimensions, mode, top_k = args.query
        _query_snapshot(Path(root), int(dimensions), mode, int(top_k))
        return

    for count in args.counts:
        with tempfile.TemporaryDirectory(prefix="sqlite-vector-benchmark-") as temporary:
            root = Path(temporary)
            snapshot = _create_snapshot(root, count, args.dimensions)
            print(
                f"count={count} dimensions={args.dimensions} snapshot_mib={snapshot.stat().st_size / 1024 / 1024:.1f}",
                flush=True,
            )
            for mode in ("default", "mmr"):
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--query",
                        str(root),
                        str(args.dimensions),
                        mode,
                        str(args.top_k),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                print(completed.stdout.strip(), flush=True)


if __name__ == "__main__":
    main()
