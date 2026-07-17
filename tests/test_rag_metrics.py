from __future__ import annotations

import json

import pytest

from app.evaluation.rag_metrics import evaluate_results, load_golden_set


def test_rag_metrics_reward_ranked_grounded_answers(tmp_path) -> None:
    golden_path = tmp_path / "golden.json"
    golden_path.write_text(
        json.dumps(
            {
                "name": "unit",
                "cases": [
                    {
                        "id": "answerable",
                        "query": "guardian?",
                        "expected_sources": ["aurora.md"],
                        "answer_contains": ["quetzal"],
                    },
                    {
                        "id": "absent",
                        "query": "missing?",
                        "expected_sources": [],
                        "should_answer": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    golden = load_golden_set(golden_path)
    report = evaluate_results(
        golden,
        {
            "answerable": {
                "answer": "El guardián es un quetzal.",
                "sources": [{"path": "aurora.md"}, {"path": "noise.md"}],
                "latency_ms": 120,
            },
            "absent": {
                "answer": "No hay evidencia en los documentos.",
                "sources": [],
                "latency_ms": 240,
            },
        },
    )
    assert report["metrics"]["recall_at_5"] == 1.0
    assert report["metrics"]["reciprocal_rank"] == 0.5
    assert report["metrics"]["answer_term_recall"] == 1.0
    assert report["metrics"]["no_answer_correct"] == 1.0
    assert report["performance"] == {
        "samples": 2,
        "latency_ms_p50": 120.0,
        "latency_ms_p95": 240.0,
        "latency_ms_max": 240.0,
    }


def test_golden_validation_rejects_duplicates_and_answer_without_source(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {"id": "x", "query": "one", "expected_sources": ["a"]},
                    {"id": "x", "query": "two", "expected_sources": ["b"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_golden_set(path)

    path.write_text(
        json.dumps({"cases": [{"id": "x", "query": "one", "expected_sources": []}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="requires at least one"):
        load_golden_set(path)
