from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evaluation.rag_metrics import evaluate_results, load_golden_set


def test_checked_in_rag_golden_fixture_is_the_ci_baseline() -> None:
    fixture = Path(__file__).parent / "fixtures" / "rag_golden.json"
    golden = load_golden_set(fixture)
    assert golden["schema_version"] == 1
    assert golden["name"] == "trinaxai-synthetic-v1"
    assert len(golden["cases"]) == 20
    corpus = {path.name for path in (fixture.parent / "rag_eval" / "corpus").iterdir() if path.is_file()}
    expected_sources = {source for case in golden["cases"] for source in case["expected_sources"]}
    assert expected_sources <= corpus


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


def test_rag_metrics_reject_incomplete_or_unexpected_results() -> None:
    golden = {
        "cases": [
            {"id": "known", "query": "one", "expected_sources": ["a"]},
        ]
    }
    with pytest.raises(ValueError, match="missing: known"):
        evaluate_results(golden, {})
    with pytest.raises(ValueError, match="unexpected: extra"):
        evaluate_results(golden, {"known": {}, "extra": {}})
    with pytest.raises(ValueError, match="invalid: known"):
        evaluate_results(golden, {"known": None})


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


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("should_answer", "false", "should_answer must be a boolean"),
        ("answer_contains", "term", "answer_contains must be a string array"),
        ("expected_sources", "source.md", "expected_sources must be a string array"),
    ],
)
def test_golden_validation_rejects_coercible_wrong_field_types(tmp_path, field, value, message) -> None:
    path = tmp_path / "bad-types.json"
    case = {
        "id": "x",
        "query": "one",
        "expected_sources": ["source.md"],
        "answer_contains": [],
    }
    case[field] = value
    path.write_text(json.dumps({"cases": [case]}), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_golden_set(path)


def test_rag_metrics_recognize_natural_language_abstention(tmp_path) -> None:
    path = tmp_path / "golden.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "absent",
                        "query": "missing?",
                        "expected_sources": [],
                        "should_answer": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_results(
        load_golden_set(path),
        {"absent": {"answer": "I am unable to answer from the provided context."}},
    )

    assert report["metrics"]["no_answer_correct"] == 1.0
