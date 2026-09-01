from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas import ChatRequest
from app.services import document_service, rag_service, runtime_usage, shared_runtime


def _request(scopes: list[str]):
    async def is_disconnected() -> bool:
        return False

    return SimpleNamespace(
        state=SimpleNamespace(trinaxai_identity={"scopes": scopes}, request_id="security-test"),
        is_disconnected=is_disconnected,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("scopes", "loads_memory"), [(["chat"], False), (["chat", "read_private"], True)])
async def test_chat_loads_private_memory_only_for_read_private_scope(monkeypatch, scopes, loads_memory) -> None:
    calls = []

    async def _completed_result():
        return rag_service._TextResponse(text="ok"), [], "test-model", "secret-project"

    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        rag_service,
        "build_task_spec",
        lambda *_args, **_kwargs: SimpleNamespace(use_rag=False, model="test-model", retrieval_mode="model"),
    )
    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: calls.append(messages) or messages)
    monkeypatch.setattr(
        rag_service,
        "run_in_threadpool",
        lambda *_args, **_kwargs: _completed_result(),
    )

    result = await rag_service.chat(
        ChatRequest(messages=[{"role": "user", "content": "hello"}], mode="model"),
        _request(scopes),
    )

    assert result["choices"][0]["message"]["content"] == "ok"
    assert bool(calls) is loads_memory
    assert result["trinaxai"]["project"] == ("secret-project" if loads_memory else None)


@pytest.mark.asyncio
@pytest.mark.parametrize(("scopes", "project"), [(["chat"], None), (["chat", "read_private"], "secret-project")])
async def test_chat_stream_hides_private_project_metadata_without_scope(monkeypatch, scopes, project) -> None:
    async def events(*_args, **_kwargs):
        yield json.dumps({"project": rag_service.detect_project("secret-project")})

    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        rag_service,
        "build_task_spec",
        lambda *_args, **_kwargs: SimpleNamespace(use_rag=False, model="test-model", retrieval_mode="model"),
    )
    monkeypatch.setattr(rag_service, "async_generate_stream", events)
    monkeypatch.setattr(rag_service.state, "known_projects", ["secret-project"])

    response = await rag_service.chat(
        ChatRequest(messages=[{"role": "user", "content": "hello"}], stream=True, mode="model"),
        _request(scopes),
    )

    payload = "".join([event async for event in response.body_iterator])
    assert json.loads(payload)["project"] == project


def test_pdf_ocr_rejects_page_budget_before_rasterization(monkeypatch) -> None:
    pages = [
        SimpleNamespace(mediabox=SimpleNamespace(width=612, height=792), extract_text=lambda: ""),
        SimpleNamespace(mediabox=SimpleNamespace(width=612, height=792), extract_text=lambda: ""),
    ]
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "pypdf",
        SimpleNamespace(PdfReader=lambda _stream: SimpleNamespace(pages=pages)),
    )
    monkeypatch.setitem(
        sys.modules,
        "pdf2image",
        SimpleNamespace(convert_from_bytes=lambda *args, **kwargs: calls.append((args, kwargs))),
    )
    monkeypatch.setitem(
        sys.modules,
        "pytesseract",
        SimpleNamespace(image_to_string=lambda *_args, **_kwargs: "text"),
    )
    monkeypatch.setattr(document_service.config, "TRINAXAI_OCR", True)
    monkeypatch.setattr(document_service, "_OCR_MAX_PAGES", 1)

    with pytest.raises(HTTPException) as raised:
        document_service._extract_pdf_text(b"pdf")

    assert raised.value.status_code == 413
    assert calls == []


def test_pdf_ocr_rejects_pixel_budget_before_rasterization(monkeypatch) -> None:
    page = SimpleNamespace(mediabox=SimpleNamespace(width=72, height=72), extract_text=lambda: "")
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "pypdf",
        SimpleNamespace(PdfReader=lambda _stream: SimpleNamespace(pages=[page])),
    )
    monkeypatch.setitem(
        sys.modules,
        "pdf2image",
        SimpleNamespace(convert_from_bytes=lambda *args, **kwargs: calls.append((args, kwargs))),
    )
    monkeypatch.setitem(
        sys.modules,
        "pytesseract",
        SimpleNamespace(image_to_string=lambda *_args, **_kwargs: "text"),
    )
    monkeypatch.setattr(document_service.config, "TRINAXAI_OCR", True)
    monkeypatch.setattr(document_service, "_OCR_MAX_PIXELS", 10_000)

    with pytest.raises(HTTPException) as raised:
        document_service._extract_pdf_text(b"pdf")

    assert raised.value.status_code == 413
    assert calls == []


def test_usage_dimensions_and_retention_are_bounded(monkeypatch) -> None:
    monkeypatch.setattr(runtime_usage, "_USAGE_MAX_DIMENSIONS", 2)
    summary = runtime_usage._empty_usage_summary()
    for index in range(5):
        runtime_usage._apply_usage_record(
            summary,
            {"ts": index + 1, "engine": f"engine-{index}", "model": f"model-{index}", "est_tokens": 1},
        )

    assert summary["messages_total"] == 5
    assert len(summary["messages_by_engine"]) <= 2
    assert len(summary["model_counts"]) <= 2

    monkeypatch.setattr(runtime_usage, "_USAGE_RETENTION_SECONDS", 10)
    retained = runtime_usage._retained_usage_records(
        [{"ts": 89, "engine": "old"}, {"ts": 95, "engine": "new"}],
        now=100,
    )
    assert [record["ts"] for record in retained] == [95.0]


def test_usage_record_rewrites_log_to_retained_bounded_records(tmp_path, monkeypatch) -> None:
    usage_path = tmp_path / "usage.jsonl"
    summary_path = tmp_path / "usage_summary.json"
    usage_path.write_text(
        '{"ts":1,"engine":"old","model":"old"}\n{"ts":95,"engine":"recent","model":"recent"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(shared_runtime, "USAGE_PATH", str(usage_path))
    monkeypatch.setattr(shared_runtime, "USAGE_SUMMARY_PATH", str(summary_path))
    monkeypatch.setattr(shared_runtime.config, "PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(shared_runtime.time, "time", lambda: 100.0)
    monkeypatch.setattr(runtime_usage, "_USAGE_MAX_RECORDS", 2)
    monkeypatch.setattr(runtime_usage, "_USAGE_RETENTION_SECONDS", 10)

    runtime_usage._record_usage("new", "new-model", None, None, 1)

    records = [json.loads(line) for line in usage_path.read_text(encoding="utf-8").splitlines()]
    assert [record["ts"] for record in records] == [95.0, 100.0]
    assert json.loads(summary_path.read_text(encoding="utf-8"))["messages_total"] == 2
