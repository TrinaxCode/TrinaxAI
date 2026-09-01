#!/usr/bin/env python3
"""Evaluate a RAG result set, a deterministic reference, or live Ollama."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import httpx

# Keep the standalone evaluator runnable from a clean checkout; the CLI-only
# wheel intentionally does not install the backend package it evaluates.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from app.evaluation import evaluate_results, load_golden_set

_REFERENCE_DOCUMENTS = {
    "aurora.md": b"# Aurora\nEl animal guardian de Aurora es el quetzal esmeralda.",
    "operaciones.csv": b"servicio,puerto\ntelemetria,4317\n",
    "politica.json": b'{"auditoria": {"retencion_dias": 30}}',
    "runbook.txt": b"La ruta de salud en el runbook es GET /health.",
}
_REFERENCE_GOLDEN = {
    "schema_version": 1,
    "name": "trinaxai-deterministic-reference-v1",
    "description": "Fixture local determinista; no mide un modelo ni requiere Ollama.",
    "cases": [
        {
            "id": "es-guardian",
            "query": "¿Cuál es el animal guardián de Aurora?",
            "expected_sources": ["aurora.md"],
            "answer_contains": ["quetzal esmeralda"],
        },
        {
            "id": "es-csv",
            "query": "¿Qué puerto usa el servicio de telemetría?",
            "expected_sources": ["operaciones.csv"],
            "answer_contains": ["4317"],
        },
        {
            "id": "es-json",
            "query": "¿Cuántos días retiene auditoría la política?",
            "expected_sources": ["politica.json"],
            "answer_contains": ["30"],
        },
        {
            "id": "en-text",
            "query": "¿Cuál es la ruta de salud del runbook?",
            "expected_sources": ["runbook.txt"],
            "answer_contains": ["GET /health"],
        },
        {
            "id": "missing-ceo",
            "query": "¿Quién es el CEO de Aurora?",
            "expected_sources": [],
            "answer_contains": [],
            "should_answer": False,
        },
        {
            "id": "missing-budget",
            "query": "¿Cuál fue el presupuesto de Aurora en 2025?",
            "expected_sources": [],
            "answer_contains": [],
            "should_answer": False,
        },
    ],
}
_STOP_WORDS = {
    "a",
    "cual",
    "de",
    "del",
    "el",
    "en",
    "es",
    "fue",
    "in",
    "is",
    "la",
    "the",
    "what",
    "que",
    "quien",
}


def _tokens(value: str) -> set[str]:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char)).casefold()
    return {token for token in re.findall(r"[a-z0-9]+", text) if token not in _STOP_WORDS}


def deterministic_reference_results() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Exercise local text ingestion, retrieval, citations, and abstention without a model."""
    from app.services.document_service import _extract_document_text

    documents = {name: _extract_document_text(name, content) for name, content in _REFERENCE_DOCUMENTS.items()}
    results: dict[str, dict[str, Any]] = {}
    for case in _REFERENCE_GOLDEN["cases"]:
        query_tokens = _tokens(str(case["query"]))
        ranked = sorted(
            ((len(query_tokens & _tokens(text)), name, text) for name, text in documents.items()),
            reverse=True,
        )
        hits = [(name, text) for score, name, text in ranked if score >= 2]
        results[str(case["id"])] = {
            "answer": hits[0][1] if hits else "No hay evidencia en los documentos.",
            "sources": [{"path": name} for name, _text in hits],
            "abstained": not hits,
        }
    return _REFERENCE_GOLDEN, results


def ollama_smoke(base_url: str, model: str, timeout: float) -> dict[str, Any]:
    """Prove that a reachable Ollama instance has one usable model."""
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        tags_response = client.get("/api/tags")
        tags_response.raise_for_status()
        tags = tags_response.json()
        installed = tags.get("models") if isinstance(tags, dict) else None
        if not isinstance(installed, list):
            raise ValueError("Ollama /api/tags returned no models array")
        model_names = [str(item.get("name") or "").strip() for item in installed if isinstance(item, dict)]
        model_names = [name for name in model_names if name]
        selected = model.strip() or (model_names[0] if model_names else "")
        if not selected:
            raise ValueError("Ollama has no installed models; pass --ollama-model")
        if selected not in model_names:
            raise ValueError(f"Ollama model is not installed: {selected}")

        generation = client.post(
            "/api/generate",
            json={"model": selected, "prompt": "Responde únicamente con OK.", "stream": False},
        )
        generation.raise_for_status()
        payload = generation.json()
        if not isinstance(payload, dict) or not str(payload.get("response") or "").strip():
            raise ValueError("Ollama returned an empty generation")
    return {
        "kind": "live_ollama_smoke",
        "live_api": False,
        "ollama_verified": True,
        "model": selected,
        "installed_models": len(model_names),
    }


def index_api_corpus(
    base_url: str,
    token: str,
    corpus_dir: str | Path,
    collection_id: str,
    embed_model: str,
    timeout: float,
) -> dict[str, Any]:
    """Upload a corpus through the public API and wait for its real index job."""
    root = Path(corpus_dir)
    if not root.is_dir():
        raise ValueError(f"RAG corpus directory does not exist: {root}")
    paths = sorted(path for path in root.rglob("*") if path.is_file())
    if not paths:
        raise ValueError(f"RAG corpus directory contains no files: {root}")

    headers = {"X-Admin-Token": token} if token else {}
    files = [
        ("files", (path.relative_to(root).as_posix(), path.read_bytes(), "application/octet-stream")) for path in paths
    ]
    with httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout) as client:
        response = client.post(
            "/system/index-upload",
            data={
                "label": "rag-live-evaluation",
                "collection_id": collection_id,
                "embed_model": embed_model,
            },
            files=files,
        )
        response.raise_for_status()
        upload = response.json()
        if not isinstance(upload, dict):
            raise ValueError("TrinaxAI index upload returned a non-object response")
        job_id = str(upload.get("job_id") or "").strip()
        if not job_id:
            raise ValueError("TrinaxAI index upload returned no job_id")

        deadline = time.monotonic() + timeout
        while True:
            status_response = client.get(f"/system/index-jobs/{job_id}")
            status_response.raise_for_status()
            job = status_response.json()
            if not isinstance(job, dict):
                raise ValueError("TrinaxAI index job returned a non-object status")
            status = str(job.get("status") or "").strip().lower()
            if status == "completed":
                if job.get("indexed") is not True:
                    raise ValueError("TrinaxAI completed the index job without loading an index")
                try:
                    chunks = int(job.get("chunks_generated") or 0)
                    saved = int(job.get("saved", len(paths)) or 0)
                    skipped = int(job.get("skipped") or 0)
                except (TypeError, ValueError) as exc:
                    raise ValueError("TrinaxAI index job returned invalid file or chunk counts") from exc
                if chunks <= 0:
                    raise ValueError("TrinaxAI completed the index job without generating chunks")
                if saved < len(paths) or skipped:
                    raise ValueError(f"TrinaxAI indexed only {saved}/{len(paths)} uploaded files ({skipped} skipped)")
                return {
                    "job_id": job_id,
                    "collection": collection_id,
                    "files": len(paths),
                    "formats": sorted({path.suffix.lower() or "(none)" for path in paths}),
                    "chunks": chunks,
                }
            if status in {"failed", "cancelled"}:
                detail = str(job.get("error") or job.get("recent_activity") or status)
                raise ValueError(f"TrinaxAI index job {status}: {detail}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"TrinaxAI index job did not finish within {timeout:g}s")
            time.sleep(1)


def _api_results(
    golden: dict[str, Any],
    base_url: str,
    token: str,
    timeout: float,
    *,
    require_rag: bool = False,
) -> dict[str, dict[str, Any]]:
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
            answer = (choices[0].get("message") or {}).get("content") or ""
            metadata = payload.get("trinaxai") or {}
            if require_rag and metadata.get("rag_used") is not True:
                raise ValueError(f"TrinaxAI response for case {case['id']} did not use backend RAG")
            results[str(case["id"])] = {
                "answer": answer,
                "sources": metadata.get("sources") or [],
                "abstained": metadata.get("abstained"),
                "rag_used": metadata.get("rag_used"),
                "model": payload.get("model"),
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
    source.add_argument(
        "--deterministic",
        action="store_true",
        help="Run the mandatory local reference gate (no Ollama or model download)",
    )
    source.add_argument(
        "--ollama-smoke",
        action="store_true",
        help="Run an explicit direct Ollama reachability and generation smoke",
    )
    parser.add_argument("--token", default=os.getenv("TRINAXAI_ADMIN_TOKEN", ""))
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output", default="rag-eval-report.json")
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--ollama-model", default="")
    parser.add_argument(
        "--index-corpus", help="Upload this directory through /system/index-upload before API evaluation"
    )
    parser.add_argument("--collection-id", default="rag-eval")
    parser.add_argument("--embed-model", default=os.getenv("TRINAXAI_EMBED", ""))
    parser.add_argument("--min-recall-10", type=float, default=0.75)
    parser.add_argument("--min-mrr", type=float, default=0.60)
    parser.add_argument("--min-ndcg", type=float, default=0.60)
    parser.add_argument("--min-citation-precision", type=float, default=0.70)
    parser.add_argument("--min-answer-term-recall", type=float, default=0.70)
    parser.add_argument("--min-no-answer-correct", type=float, default=0.90)
    args = parser.parse_args()
    if args.index_corpus and not args.api_url:
        parser.error("--index-corpus requires --api-url")

    if args.ollama_smoke:
        execution = ollama_smoke(args.ollama_url, args.ollama_model, args.timeout)
        report = {
            "schema_version": 1,
            "dataset": "ollama-live-smoke",
            "cases": 1,
            "metrics": {"ollama_reachable": 1.0, "ollama_generation": 1.0},
            "results": [],
            "thresholds": {},
            "passed": True,
            "failures": [],
            "execution": execution,
        }
        failures = []
    else:
        execution: dict[str, Any]
        if args.deterministic:
            golden, results = deterministic_reference_results()
            execution = {
                "kind": "deterministic_reference",
                "live_api": False,
                "ollama_verified": False,
                "formats": sorted(Path(name).suffix for name in _REFERENCE_DOCUMENTS),
            }
        else:
            golden = load_golden_set(args.golden)
        if args.results:
            loaded = json.loads(Path(args.results).read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("--results must contain a JSON object keyed by golden case id")
            results = loaded.get("results", loaded)
            if not isinstance(results, dict):
                raise ValueError("--results must contain a JSON object keyed by golden case id")
            execution = {"kind": "saved_results", "live_api": False, "ollama_verified": False}
        elif args.api_url:
            indexed = None
            if args.index_corpus:
                indexed = index_api_corpus(
                    args.api_url,
                    args.token,
                    args.index_corpus,
                    args.collection_id,
                    args.embed_model,
                    args.timeout,
                )
            results = _api_results(golden, args.api_url, args.token, args.timeout, require_rag=bool(indexed))
            execution = {
                "kind": "live_backend_rag" if indexed else "live_api_smoke",
                "live_api": True,
                "ollama_verified": bool(indexed),
                "models": sorted({str(result.get("model")) for result in results.values() if result.get("model")}),
                "index": indexed,
            }
        report = evaluate_results(golden, results)
        thresholds = {
            "recall_at_10": args.min_recall_10,
            "reciprocal_rank": args.min_mrr,
            "ndcg": args.min_ndcg,
            "citation_precision": args.min_citation_precision,
            "answer_term_recall": args.min_answer_term_recall,
            "no_answer_correct": args.min_no_answer_correct,
        }
        failures = _threshold_failures(report, thresholds)
        report["thresholds"] = thresholds
        report["passed"] = not failures
        report["failures"] = failures
        report["execution"] = execution
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output != "-":
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    sys.stdout.write(output + "\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, httpx.HTTPError) as exc:
        sys.stderr.write(f"RAG evaluation failed: {exc}\n")
        raise SystemExit(2) from exc
