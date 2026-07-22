from __future__ import annotations

from starlette.testclient import TestClient

import rag_api


def test_usage_summary_accumulates_counts() -> None:
    summary = rag_api._empty_usage_summary()

    rag_api._apply_usage_record(
        summary,
        {
            "ts": 10.0,
            "engine": "ollama",
            "model": "llama3.2:3b",
            "collections": ["default"],
            "est_tokens": 20,
        },
    )
    rag_api._apply_usage_record(
        summary,
        {
            "ts": 20.0,
            "engine": "rag",
            "model": "qwen2.5-coder:3b",
            "collections": ["default", "docs"],
            "est_tokens": 30,
        },
    )

    out = rag_api._usage_summary_response(summary)

    assert out["messages_total"] == 2
    assert out["tokens_estimated"] == 50
    assert out["messages_by_engine"] == {"ollama": 1, "rag": 1}
    assert out["top_collections"][0] == {"id": "default", "count": 2}
    assert out["first_seen"] == 10.0
    assert out["last_seen"] == 20.0


def test_usage_endpoints_persist_and_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(rag_api, "USAGE_PATH", str(tmp_path / "usage.jsonl"))
    monkeypatch.setattr(rag_api, "USAGE_SUMMARY_PATH", str(tmp_path / "usage_summary.json"))
    client = TestClient(rag_api.app, client=("127.0.0.1", 50000))

    recorded = client.post(
        "/v1/usage",
        json={"engine": "ollama", "model": "test-model", "collections": ["default"], "est_tokens": 12},
    )
    stats = client.get("/v1/stats").json()

    assert recorded.json() == {"ok": True}
    assert stats["messages_total"] == 1
    assert stats["tokens_estimated"] == 12
    assert stats["top_models"] == [{"model": "test-model", "count": 1}]
