from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evaluation.rag_metrics import evaluate_results, load_golden_set
from app.services import rag_service
from scripts import evaluate_rag
from scripts.evaluate_rag import deterministic_reference_results


def test_checked_in_rag_golden_fixture_is_the_ci_baseline() -> None:
    fixture = Path(__file__).parent / "fixtures" / "rag_golden.json"
    golden = load_golden_set(fixture)
    assert golden["schema_version"] == 1
    assert golden["name"] == "trinaxai-synthetic-v1"
    assert len(golden["cases"]) == 20
    corpus = {path.name for path in (fixture.parent / "rag_eval" / "corpus").iterdir() if path.is_file()}
    expected_sources = {source for case in golden["cases"] for source in case["expected_sources"]}
    assert expected_sources <= corpus
    assert any("¿" in case["query"] for case in golden["cases"])
    assert sum(not case.get("should_answer", True) for case in golden["cases"]) >= 3


def test_deterministic_reference_gate_covers_formats_grounding_and_abstention() -> None:
    golden, results = deterministic_reference_results()

    report = evaluate_results(golden, results)

    assert {Path(source["path"]).suffix for result in results.values() for source in result["sources"]} >= {
        ".csv",
        ".json",
        ".md",
        ".txt",
    }
    assert any("¿" in case["query"] for case in golden["cases"])
    assert report["metrics"]["recall_at_5"] == 1.0
    assert report["metrics"]["recall_at_10"] == 1.0
    assert report["metrics"]["citation_precision"] == 1.0
    assert report["metrics"]["answer_term_recall"] == 1.0
    assert report["metrics"]["no_answer_correct"] == 1.0
    assert report["metrics"]["reciprocal_rank"] == pytest.approx(2 / 3)
    assert all(results[case["id"]]["abstained"] for case in golden["cases"] if not case.get("should_answer", True))


def test_live_rag_fixture_covers_heterogeneous_spanish_and_abstention() -> None:
    fixture = Path(__file__).parent / "fixtures" / "rag_live_golden.json"
    golden = load_golden_set(fixture)
    corpus = fixture.parent / "rag_eval" / "corpus"

    assert {path.suffix for path in corpus.iterdir() if path.is_file()} >= {".csv", ".json", ".md", ".txt"}
    assert sum("¿" in case["query"] for case in golden["cases"]) >= 3
    assert sum(not case.get("should_answer", True) for case in golden["cases"]) >= 2
    assert {source for case in golden["cases"] for source in case["expected_sources"]} <= {
        path.name for path in corpus.iterdir() if path.is_file()
    }


def test_index_api_corpus_uploads_and_waits_for_loaded_index(tmp_path, monkeypatch) -> None:
    (tmp_path / "documento.md").write_text("evidencia", encoding="utf-8")
    statuses = iter(
        [
            {"status": "indexing", "progress": 65},
            {"status": "completed", "indexed": True, "chunks_generated": 3},
        ]
    )

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self.payload

    class Client:
        def __init__(self, base_url, headers, timeout):
            assert (base_url, headers, timeout) == ("http://api", {"X-Admin-Token": "token"}, 30)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, path, *, data, files):
            assert path == "/system/index-upload"
            assert data == {
                "label": "rag-live-evaluation",
                "collection_id": "rag-eval",
                "embed_model": "embed:1",
            }
            assert files == [("files", ("documento.md", b"evidencia", "application/octet-stream"))]
            return Response({"job_id": "job-1"})

        def get(self, path):
            assert path == "/system/index-jobs/job-1"
            return Response(next(statuses))

    monkeypatch.setattr(evaluate_rag.httpx, "Client", Client)
    monkeypatch.setattr(evaluate_rag.time, "sleep", lambda _seconds: None)

    assert evaluate_rag.index_api_corpus("http://api/", "token", tmp_path, "rag-eval", "embed:1", 30) == {
        "job_id": "job-1",
        "collection": "rag-eval",
        "files": 1,
        "formats": [".md"],
        "chunks": 3,
    }


def test_ollama_smoke_requires_direct_model_generation(monkeypatch) -> None:
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self.payload

    class Client:
        def __init__(self, base_url, timeout):
            assert base_url == "http://ollama"
            assert timeout == 5

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, path):
            assert path == "/api/tags"
            return Response({"models": [{"name": "modelo:1b"}]})

        def post(self, path, *, json):
            assert path == "/api/generate"
            assert json == {"model": "modelo:1b", "prompt": "Responde únicamente con OK.", "stream": False}
            return Response({"response": "OK"})

    monkeypatch.setattr(evaluate_rag.httpx, "Client", Client)

    assert evaluate_rag.ollama_smoke("http://ollama/", "modelo:1b", 5) == {
        "kind": "live_ollama_smoke",
        "live_api": False,
        "ollama_verified": True,
        "model": "modelo:1b",
        "installed_models": 1,
    }


def test_live_api_evaluation_requires_backend_rag_metadata(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "choices": [{"message": {"content": "answer"}}],
                "trinaxai": {"rag_used": False},
            }

    class Client:
        def __init__(self, base_url, headers, timeout):
            assert (base_url, headers, timeout) == ("http://api", {}, 5)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, path, *, json):
            assert path == "/v1/chat/completions"
            assert json["mode"] == "knowledge"
            return Response()

    monkeypatch.setattr(evaluate_rag.httpx, "Client", Client)
    golden = {
        "cases": [{"id": "case-1", "query": "question", "expected_sources": ["doc.md"]}],
    }

    with pytest.raises(ValueError, match="did not use backend RAG"):
        evaluate_rag._api_results(golden, "http://api/", "", 5, require_rag=True)


def test_backend_abstention_markers_match_live_model_refusals() -> None:
    assert rag_service._is_rag_abstention("No se encuentra información en los documentos.", rag_requested=True)
    assert rag_service._is_rag_abstention("I did not find that in the indexed documents.", rag_requested=True)


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
