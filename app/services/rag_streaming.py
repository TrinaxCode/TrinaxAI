"""Cancellation-safe synchronous and asynchronous RAG transport."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Callable

from starlette.requests import ClientDisconnect, Request

from app.generation.spec import TaskSpec


class _ServiceProxy:
    def __getattr__(self, name):
        return getattr(_runtime(), name)


def _runtime():
    from . import rag_service

    return rag_service


service = _ServiceProxy()


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False, separators=(',', ':'))}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


def _completion_metadata(reason: str, content: str = "") -> dict:
    incomplete = reason == "length" or (reason == "stop" and service._structurally_incomplete(content))
    return {
        "reason": "length" if incomplete else reason,
        "status": "pending" if incomplete else "complete" if reason == "stop" else reason,
        "can_continue": incomplete,
        "max_continuations": service.config.MAX_CONTINUATIONS,
    }


def _sse_error(exc: Exception) -> str:
    info = service.classify_error(exc, status_code=503)
    service.LOG.error(
        "streaming RAG failure category=%s code=%s exception_type=%s",
        info.category.value,
        info.code,
        type(exc).__name__,
    )
    error = info.to_client_dict()
    error["recovery"] = f"{error['recovery']} Please retry."
    return _sse({"trinaxai_error": error, "trinaxai_finish": _completion_metadata("error")})


def generate_stream(
    messages: list[dict],
    collections: list[str] | None = None,
    *,
    model: str | None = None,
    keep_alive: str | int | None = None,
    aggressive_quant: bool | None = None,
    retrieval_mode: str = "auto",
    request_id: str | None = None,
    thinking: bool = True,
):
    started = time.perf_counter()
    completed = False
    selected_model = model
    thinking_parts: list[str] = []
    thinking_started: float | None = None
    thinking_duration_ms: float | None = None

    def on_thinking(part: str) -> None:
        nonlocal thinking_started
        if not part:
            return
        thinking_started = thinking_started or time.perf_counter()
        thinking_parts.append(part)

    service._model_slots.acquire()
    try:
        with service._inference_process_lock():
            # Resolve the plan up front so the UI preview shows the right model and
            # so we only require an index for tasks that actually need retrieval.
            preview_retrieval_q, _ = service.prepare_query(messages)
            preview_project = service.detect_project(preview_retrieval_q)
            preview_spec = service.build_task_spec(
                messages,
                model_override=model,
                has_index=service.state.fusion_retriever is not None,
                retrieval_mode=retrieval_mode,
            )
            if preview_spec.use_rag and service.state.fusion_retriever is None:
                payload = {
                    "model": preview_spec.model,
                    "project": preview_project,
                    "phase": "retrieving",
                    "mode": preview_spec.retrieval_mode,
                    "rag_used": False,
                    "abstained": True,
                    "collections": list(collections or []),
                    "request_id": request_id,
                }
                yield _sse({"trinaxai": payload})
                yield _sse({"choices": [{"delta": {"content": service.NO_INDEX_MSG}}]})
                yield _sse(
                    {
                        "trinaxai_finish": _completion_metadata("stop", service.NO_INDEX_MSG),
                        "trinaxai_sources": [],
                        "trinaxai_retrieval": {**payload, "result_count": 0},
                    }
                )
                yield _sse_done()
                completed = True
                return
            preview_model = preview_spec.model
            yield _sse(
                {
                    "trinaxai": {
                        "model": preview_model,
                        "project": preview_project,
                        "phase": "retrieving" if preview_spec.use_rag else "generating",
                        "mode": preview_spec.retrieval_mode,
                        "rag_used": preview_spec.use_rag,
                        "collections": list(collections or []),
                        "request_id": request_id,
                    }
                }
            )
            response, nodes, selected_model, project = service.run_rag(
                messages,
                stream=True,
                collections=collections,
                model_override=model,
                keep_alive=keep_alive,
                aggressive_quant=aggressive_quant,
                retrieval_mode=retrieval_mode,
                thinking=thinking,
                on_thinking=on_thinking,
            )
            if selected_model != preview_model or project != preview_project:
                yield _sse({"trinaxai": {"model": selected_model, "project": project}})
            completion_parts: list[str] = []
            emitted_thinking_chars = 0
            for token in response.response_gen:
                if service.state.lifecycle_stopping.is_set():
                    break
                thinking_text = "".join(thinking_parts)
                if len(thinking_text) > emitted_thinking_chars:
                    thinking_delta = thinking_text[emitted_thinking_chars:]
                    emitted_thinking_chars = len(thinking_text)
                    if thinking_delta:
                        yield _sse({"trinaxai_thinking": thinking_delta})
                if token and thinking_started is not None and thinking_duration_ms is None:
                    thinking_duration_ms = round((time.perf_counter() - thinking_started) * 1000, 1)
                completion_parts.append(token)
                yield _sse({"choices": [{"delta": {"content": token}}]})
            thinking_text = "".join(thinking_parts)
            if len(thinking_text) > emitted_thinking_chars:
                thinking_delta = thinking_text[emitted_thinking_chars:]
                if thinking_delta:
                    yield _sse({"trinaxai_thinking": thinking_delta})
            if thinking_started is not None and thinking_duration_ms is None:
                thinking_duration_ms = round((time.perf_counter() - thinking_started) * 1000, 1)
            content = "".join(completion_parts)
            stopping = service.state.lifecycle_stopping.is_set()
            finish_reason = service._response_finish_reason(response, cancelled=stopping)
            abstained = service._is_rag_abstention(content, rag_requested=preview_spec.use_rag)
            yield _sse({"trinaxai_finish": _completion_metadata(finish_reason, content)})
            yield _sse(
                {
                    "trinaxai_sources": service.sources_payload(nodes),
                    "trinaxai_retrieval": {
                        "mode": preview_spec.retrieval_mode,
                        "rag_used": preview_spec.use_rag,
                        "abstained": abstained,
                        "result_count": len(nodes),
                        "collections": list(collections or []),
                    },
                },
            )
            yield _sse(
                {
                    "trinaxai_usage": service._usage_payload(messages, "".join(completion_parts), nodes),
                    "trinaxai_timing": {
                        "total_ms": round((time.perf_counter() - started) * 1000, 1),
                        **({"thinking_duration_ms": thinking_duration_ms} if thinking_duration_ms is not None else {}),
                    },
                    "trinaxai_quality": _stream_quality_payload(
                        preview_spec,
                        messages,
                        content,
                    ),
                }
            )
            completed = not stopping
    except Exception as e:
        yield _sse_error(e)
    finally:
        if not completed:
            service._cancel_ollama_model(selected_model)
        service._model_slots.release()
    yield _sse_done()


async def _run_rag_stream_async(
    messages: list[dict],
    collections: list[str] | None = None,
    *,
    model_override: str | None = None,
    keep_alive: str | int | None = None,
    aggressive_quant: bool | None = None,
    retrieval_mode: str = "auto",
    thinking: bool = True,
    on_thinking: Callable[[str], None] | None = None,
):
    """Prepare a stream without entering Ollama through a worker thread."""
    (
        messages,
        chat,
        current,
        creator_requested,
        retrieval_q,
        synth_q,
        project,
        lang,
        has_index,
        spec,
    ) = service._prepare_rag_context(
        messages,
        model_override=model_override,
        retrieval_mode=retrieval_mode,
    )

    if spec.use_rag:
        if has_index and service._is_catalog_query(current):
            response = service._async_text_response(service._catalog_answer(collections, spanish="Spanish" in lang))
            service._safe_record_usage("rag", spec.model, project, collections, chat, [])
            return response, [], spec.model, project

        nodes = await service.run_in_threadpool(service._cached_retrieve, retrieval_q, current, collections, project)
        service._hide_private_node_metadata(nodes)
        if not nodes or not service._retrieval_is_relevant(nodes):
            nodes = []
            response = service._async_text_response(service.NO_RELEVANT_RESULTS_MSG)
            service._safe_record_usage("rag", spec.model, project, collections, chat, nodes)
            return response, nodes, spec.model, project

        llm = service.get_llm(
            spec.model,
            keep_alive=keep_alive,
            aggressive_quant=aggressive_quant,
            thinking=bool(thinking and getattr(spec, "thinking", False)),
            **spec.llm_kwargs(),
        )
        tracker = service._ThinkingLLM(llm, on_thinking)
        synth = service.get_response_synthesizer(
            llm=tracker,
            text_qa_template=service.grounded_template(creator_requested),
            response_mode=service.ResponseMode.COMPACT,
            streaming=True,
        )

        async def _synthesized_tokens():
            response = await synth.asynthesize(f"{lang}\n\n{synth_q}", nodes=nodes)
            service._safe_record_usage("rag", spec.model, project, collections, chat, nodes)
            response_gen = getattr(response, "async_response_gen", None)
            if callable(response_gen):
                async for token in response_gen():
                    yield token
                return
            # LlamaIndex materializes a normal Response when async refinement
            # consumes intermediate chunks before the final chunk.
            text = getattr(response, "response", None)
            if text:
                yield str(text)

        response = service._AsyncTextResponse(_synthesized_tokens())
        response._finish_tracker = tracker
        return response, nodes, spec.model, project

    llm = service.get_llm(
        spec.model,
        keep_alive=keep_alive,
        aggressive_quant=aggressive_quant,
        thinking=bool(thinking and getattr(spec, "thinking", False)),
        **spec.llm_kwargs(),
    )
    prompt = service.build_generation_prompt(
        spec.regime,
        synth_q,
        language_instruction=lang,
        include_creator_bio=creator_requested,
    )
    response = await service._freeform_generate_async(llm, prompt, on_thinking=on_thinking)
    service._safe_record_usage("gen", spec.model, project, collections, chat, [])
    return response, [], spec.model, project


async def _wait_for_disconnect(request: Request) -> None:
    while True:
        disconnected = request.is_disconnected()
        if hasattr(disconnected, "__await__"):
            disconnected = await disconnected
        if disconnected:
            return
        await asyncio.sleep(0.1)


async def _cancel_async_task(task) -> None:
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except BaseException:
        pass


async def _async_response_tokens(response, request: Request | None):
    iterator = response.async_response_gen()
    if request is None:
        try:
            async for token in iterator:
                yield token
        finally:
            close = getattr(iterator, "aclose", None)
            if close is not None:
                await close()
        return

    monitor = asyncio.create_task(_wait_for_disconnect(request))
    next_token = asyncio.create_task(anext(iterator))
    try:
        while True:
            done, _ = await asyncio.wait({next_token, monitor}, return_when=asyncio.FIRST_COMPLETED)
            if monitor in done:
                await _cancel_async_task(next_token)
                raise asyncio.CancelledError("Client disconnected during generation")
            try:
                token = next_token.result()
            except StopAsyncIteration:
                break
            yield token
            next_token = asyncio.create_task(anext(iterator))
    finally:
        await _cancel_async_task(next_token)
        await _cancel_async_task(monitor)
        close = getattr(iterator, "aclose", None)
        if close is not None:
            await close()


async def _acquire_model_slot_async() -> None:
    while not service._model_slots.acquire(blocking=False):
        await asyncio.sleep(0.05)


@asynccontextmanager
async def _async_inference_process_lock():
    """Acquire the shared process lock without blocking the event loop."""
    lock = service._inference_process_lock()
    await service.run_in_threadpool(lock.__enter__)
    try:
        yield
    finally:
        await service.run_in_threadpool(lock.__exit__, None, None, None)


async def async_generate_stream(
    messages: list[dict],
    collections: list[str] | None = None,
    *,
    model: str | None = None,
    keep_alive: str | int | None = None,
    aggressive_quant: bool | None = None,
    retrieval_mode: str = "auto",
    request_id: str | None = None,
    thinking: bool = True,
    request: Request | None = None,
):
    """Cancellation-safe SSE generator used by the HTTP endpoint."""
    started = time.perf_counter()
    completed = False
    selected_model = model
    thinking_parts: list[str] = []
    thinking_started: float | None = None
    thinking_duration_ms: float | None = None
    token_stream = None

    def on_thinking(part: str) -> None:
        nonlocal thinking_started
        if not part:
            return
        thinking_started = thinking_started or time.perf_counter()
        thinking_parts.append(part)

    slot_acquired = False
    try:
        await service._acquire_model_slot_async()
        slot_acquired = True
        async with service._async_inference_process_lock():
            preview_retrieval_q, _ = service.prepare_query(messages)
            preview_project = service.detect_project(preview_retrieval_q)
            preview_spec = service.build_task_spec(
                messages,
                model_override=model,
                has_index=service.state.fusion_retriever is not None,
                retrieval_mode=retrieval_mode,
            )
            if preview_spec.use_rag and service.state.fusion_retriever is None:
                payload = {
                    "model": preview_spec.model,
                    "project": preview_project,
                    "phase": "retrieving",
                    "mode": preview_spec.retrieval_mode,
                    "rag_used": False,
                    "abstained": True,
                    "collections": list(collections or []),
                    "request_id": request_id,
                }
                yield _sse({"trinaxai": payload})
                yield _sse({"choices": [{"delta": {"content": service.NO_INDEX_MSG}}]})
                yield _sse(
                    {
                        "trinaxai_finish": service._completion_metadata("stop", service.NO_INDEX_MSG),
                        "trinaxai_sources": [],
                        "trinaxai_retrieval": {**payload, "result_count": 0},
                    }
                )
                yield _sse_done()
                completed = True
                return
            preview_model = preview_spec.model
            yield _sse(
                {
                    "trinaxai": {
                        "model": preview_model,
                        "project": preview_project,
                        "phase": "retrieving" if preview_spec.use_rag else "generating",
                        "mode": preview_spec.retrieval_mode,
                        "rag_used": preview_spec.use_rag,
                        "collections": list(collections or []),
                        "request_id": request_id,
                    }
                }
            )
            response, nodes, selected_model, project = await service._run_rag_stream_async(
                messages,
                collections,
                model_override=model,
                keep_alive=keep_alive,
                aggressive_quant=aggressive_quant,
                retrieval_mode=retrieval_mode,
                thinking=thinking,
                on_thinking=on_thinking,
            )
            if selected_model != preview_model or project != preview_project:
                yield _sse({"trinaxai": {"model": selected_model, "project": project}})
            completion_parts: list[str] = []
            emitted_thinking_chars = 0
            token_stream = service._async_response_tokens(response, request)
            async for token in token_stream:
                if service.state.lifecycle_stopping.is_set():
                    break
                thinking_text = "".join(thinking_parts)
                if len(thinking_text) > emitted_thinking_chars:
                    thinking_delta = thinking_text[emitted_thinking_chars:]
                    emitted_thinking_chars = len(thinking_text)
                    if thinking_delta:
                        yield _sse({"trinaxai_thinking": thinking_delta})
                if token and thinking_started is not None and thinking_duration_ms is None:
                    thinking_duration_ms = round((time.perf_counter() - thinking_started) * 1000, 1)
                completion_parts.append(token)
                yield _sse({"choices": [{"delta": {"content": token}}]})
            thinking_text = "".join(thinking_parts)
            if len(thinking_text) > emitted_thinking_chars:
                thinking_delta = thinking_text[emitted_thinking_chars:]
                if thinking_delta:
                    yield _sse({"trinaxai_thinking": thinking_delta})
            if thinking_started is not None and thinking_duration_ms is None:
                thinking_duration_ms = round((time.perf_counter() - thinking_started) * 1000, 1)
            content = "".join(completion_parts)
            stopping = service.state.lifecycle_stopping.is_set()
            finish_reason = service._response_finish_reason(response, cancelled=stopping)
            abstained = service._is_rag_abstention(content, rag_requested=preview_spec.use_rag)
            yield _sse({"trinaxai_finish": service._completion_metadata(finish_reason, content)})
            yield _sse(
                {
                    "trinaxai_sources": service.sources_payload(nodes),
                    "trinaxai_retrieval": {
                        "mode": preview_spec.retrieval_mode,
                        "rag_used": preview_spec.use_rag,
                        "abstained": abstained,
                        "result_count": len(nodes),
                        "collections": list(collections or []),
                    },
                }
            )
            yield _sse(
                {
                    "trinaxai_usage": service._usage_payload(messages, content, nodes),
                    "trinaxai_timing": {
                        "total_ms": round((time.perf_counter() - started) * 1000, 1),
                        **({"thinking_duration_ms": thinking_duration_ms} if thinking_duration_ms is not None else {}),
                    },
                    "trinaxai_quality": service._stream_quality_payload(preview_spec, messages, content),
                }
            )
            completed = not stopping
    except (asyncio.CancelledError, ClientDisconnect, OSError):
        raise
    except Exception as e:
        yield _sse_error(e)
    finally:
        if token_stream is not None:
            close = getattr(token_stream, "aclose", None)
            if close is not None:
                await close()
        if not completed:
            service._cancel_ollama_model(selected_model)
        if slot_acquired:
            service._model_slots.release()
    yield _sse_done()


def _stream_quality_payload(spec: TaskSpec, messages: list[dict], content: str) -> dict:
    """Report post-stream heuristics without pretending they are compilation."""
    if not spec.validate:
        return {"checked": False, "kind": "heuristic"}
    current = next(
        (str(message.get("content") or "") for message in reversed(messages) if message.get("role") == "user"),
        "",
    )
    result = service.validate_output(
        content,
        regime=spec.regime.value,
        deliverables=service._wanted_deliverables(current),
        require_responsive="responsive" in current.lower() or spec.regime is service.Regime.CREATIVE,
    )
    return {
        "checked": True,
        "kind": "heuristic",
        "ok": result.ok,
        "errors": result.errors,
        "missing": result.missing,
    }


__all__ = [name for name in globals() if not name.startswith("__")]
