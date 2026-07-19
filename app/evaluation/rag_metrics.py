"""Metrics for versioned TrinaxAI retrieval/generation golden sets.

The evaluator never sends corpus text anywhere. It consumes expected source
identifiers and compact answer assertions, then reports deterministic metrics
that can be compared between branches and model/profile configurations.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any


def _normalise(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip().casefold()


def _source_id(hit: object) -> str:
    if isinstance(hit, str):
        return _normalise(hit)
    if isinstance(hit, dict):
        for key in ("source_key", "source_id", "path", "file", "source", "id"):
            if hit.get(key):
                return _normalise(hit[key])
    return ""


def load_golden_set(path: str | Path) -> dict[str, Any]:
    """Load and validate a golden-set JSON file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("golden set must be an object with a cases array")
    seen: set[str] = set()
    for index, case in enumerate(payload["cases"]):
        if not isinstance(case, dict):
            raise ValueError(f"case {index} must be an object")
        case_id = str(case.get("id") or "").strip()
        query = str(case.get("query") or "").strip()
        if not case_id or not query:
            raise ValueError(f"case {index} requires non-empty id and query")
        if case_id in seen:
            raise ValueError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        expected = case.get("expected_sources") or []
        if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
            raise ValueError(f"case {case_id} expected_sources must be a string array")
        if bool(case.get("should_answer", True)) and not expected:
            raise ValueError(f"answerable case {case_id} requires at least one expected source")
    return payload


def _dcg(relevances: list[int]) -> float:
    return sum(value / math.log2(rank + 2) for rank, value in enumerate(relevances))


def _looks_abstained(answer: str) -> bool:
    text = _normalise(answer)
    markers = (
        "no se",
        "no encontre",
        "no hay evidencia",
        "no aparece en",
        "no puedo determinar",
        "i don't know",
        "i do not know",
        "not found in",
        "no evidence",
        "cannot determine",
    )
    return not text or any(marker in text for marker in markers)


def _evaluate_case(case: dict[str, Any], result: dict[str, Any], k_values: tuple[int, ...]) -> dict[str, Any]:
    expected = {_normalise(item) for item in case.get("expected_sources") or []}
    ranked = [_source_id(hit) for hit in result.get("sources") or []]
    ranked = [item for item in ranked if item]
    relevant_flags = [1 if item in expected else 0 for item in ranked]
    should_answer = bool(case.get("should_answer", True))

    recalls: dict[str, float] = {}
    for k in k_values:
        found = expected.intersection(ranked[:k])
        recalls[f"recall_at_{k}"] = len(found) / len(expected) if expected else float(not ranked[:k])

    first_rank = next((rank for rank, item in enumerate(ranked, start=1) if item in expected), None)
    reciprocal_rank = (1.0 / first_rank) if first_rank else 0.0
    ideal = [1] * min(len(expected), len(ranked))
    ndcg = (_dcg(relevant_flags) / _dcg(ideal)) if ideal else float(not ranked)
    citation_precision = sum(relevant_flags) / len(relevant_flags) if relevant_flags else float(not should_answer)

    answer = str(result.get("answer") or "")
    terms = [_normalise(term) for term in case.get("answer_contains") or [] if str(term).strip()]
    answer_norm = _normalise(answer)
    term_recall = sum(term in answer_norm for term in terms) / len(terms) if terms else 1.0
    explicit_abstained = result.get("abstained")
    abstained = bool(explicit_abstained) if explicit_abstained is not None else _looks_abstained(answer)
    no_answer_correct = float((not should_answer and abstained) or (should_answer and not abstained))

    return {
        "id": case["id"],
        **recalls,
        "reciprocal_rank": reciprocal_rank,
        "ndcg": ndcg,
        "citation_precision": citation_precision,
        "answer_term_recall": term_recall,
        "no_answer_correct": no_answer_correct,
        "returned_sources": ranked,
    }


def evaluate_results(
    golden: dict[str, Any],
    results: dict[str, dict[str, Any]],
    *,
    k_values: tuple[int, ...] = (5, 10),
) -> dict[str, Any]:
    """Evaluate keyed results and return per-case plus aggregate metrics."""
    if not k_values or any(k <= 0 for k in k_values):
        raise ValueError("k_values must contain positive integers")
    cases = golden.get("cases") or []
    evaluated = [_evaluate_case(case, results.get(str(case["id"]), {}), k_values) for case in cases]
    metric_names = [f"recall_at_{k}" for k in k_values] + [
        "reciprocal_rank",
        "ndcg",
        "citation_precision",
        "answer_term_recall",
        "no_answer_correct",
    ]
    count = len(evaluated)
    metrics = {name: (sum(float(case[name]) for case in evaluated) / count if count else 0.0) for name in metric_names}
    latencies = sorted(
        float(result["latency_ms"])
        for result in results.values()
        if isinstance(result, dict)
        and isinstance(result.get("latency_ms"), (int, float))
        and float(result["latency_ms"]) >= 0
    )

    def percentile(fraction: float) -> float | None:
        if not latencies:
            return None
        rank = max(0, math.ceil(fraction * len(latencies)) - 1)
        return round(latencies[rank], 2)

    report = {
        "schema_version": 1,
        "dataset": golden.get("name") or "unnamed",
        "cases": count,
        "metrics": metrics,
        "results": evaluated,
    }
    if latencies:
        report["performance"] = {
            "samples": len(latencies),
            "latency_ms_p50": percentile(0.50),
            "latency_ms_p95": percentile(0.95),
            "latency_ms_max": round(latencies[-1], 2),
        }
    return report
