#!/usr/bin/env python3
"""Run TrinaxAI's versioned RAG golden set against an API or saved results."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from app.evaluation import evaluate_results, load_golden_set


def _api_results(golden: dict[str, Any], base_url: str, token: str, timeout: float) -> dict[str, dict[str, Any]]:
    headers = {"X-Admin-Token": token} if token else {}
    results: dict[str, dict[str, Any]] = {}
    with httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout) as client:
        for case in golden["cases"]:
            started = time.perf_counter()
            response = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": case["query"]}],
                    "collections": case.get("collections"),
                    "mode": "knowledge",
                    "stream": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
            choices = payload.get("choices") or [{}]
            answer = ((choices[0].get("message") or {}).get("content") or "")
            metadata = payload.get("trinaxai") or {}
            results[str(case["id"])] = {
                "answer": answer,
                "sources": metadata.get("sources") or [],
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
    return results


def _threshold_failures(report: dict[str, Any], thresholds: dict[str, float]) -> list[str]:
    failures = []
    metrics = report["metrics"]
    for name, minimum in thresholds.items():
        actual = float(metrics.get(name, 0.0))
        if actual < minimum:
            failures.append(f"{name}={actual:.3f} < {minimum:.3f}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate TrinaxAI RAG quality")
    parser.add_argument("--golden", default="tests/fixtures/rag_golden.json")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--results", help="Saved JSON object keyed by golden case id")
    source.add_argument("--api-url", help="Live TrinaxAI API base URL")
    parser.add_argument("--token", default=os.getenv("TRINAXAI_ADMIN_TOKEN", ""))
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output", default="rag-eval-report.json")
    parser.add_argument("--min-recall-10", type=float, default=0.75)
    parser.add_argument("--min-mrr", type=float, default=0.60)
    parser.add_argument("--min-ndcg", type=float, default=0.60)
    parser.add_argument("--min-citation-precision", type=float, default=0.70)
    parser.add_argument("--min-answer-term-recall", type=float, default=0.70)
    args = parser.parse_args()

    golden = load_golden_set(args.golden)
    if args.results:
        loaded = json.loads(Path(args.results).read_text(encoding="utf-8"))
        results = loaded.get("results", loaded) if isinstance(loaded, dict) else {}
    else:
        results = _api_results(golden, args.api_url, args.token, args.timeout)
    report = evaluate_results(golden, results)
    thresholds = {
        "recall_at_10": args.min_recall_10,
        "reciprocal_rank": args.min_mrr,
        "ndcg": args.min_ndcg,
        "citation_precision": args.min_citation_precision,
        "answer_term_recall": args.min_answer_term_recall,
    }
    failures = _threshold_failures(report, thresholds)
    report["thresholds"] = thresholds
    report["passed"] = not failures
    report["failures"] = failures
    output = json.dumps(report, ensure_ascii=False, indent=2)
    Path(args.output).write_text(output + "\n", encoding="utf-8")
    sys.stdout.write(output + "\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
