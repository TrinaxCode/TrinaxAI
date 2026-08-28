"""``trinaxai research`` — multi-pass deep research."""

from __future__ import annotations

from typing import Any

from trinaxai_cli.session import Session

_RESEARCH_META_KEYS = (
    "search_query",
    "sub_questions",
    "passes",
    "web_search",
    "web_provider",
    "degraded",
    "error_code",
    "error_detail",
    "failure_reason",
    "failure_message",
    "sources",
)


def _research_metadata(result: dict[str, Any]) -> dict[str, Any]:
    return {key: result[key] for key in _RESEARCH_META_KEYS if key in result}


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    query = getattr(args, "query", None)
    if not query:
        ui.error("--query is required.")
        return 1
    collections = getattr(args, "collections", None) or []
    if isinstance(collections, str):
        collections = [c.strip() for c in collections.split(",") if c.strip()]
    depth = int(getattr(args, "depth", 2) or 2)
    try:
        with ui.spinner(f"Researching (depth={depth})..."):
            research_kwargs: dict[str, Any] = {"query": query, "collections": collections, "depth": depth}
            if hasattr(config, "thinking_enabled"):
                thinking = config.thinking_enabled
                if getattr(args, "thinking", None) is not None:
                    thinking = bool(args.thinking)
                research_kwargs["thinking"] = bool(thinking)
            res = client.research(**research_kwargs)
        session_name = getattr(args, "session", None)
        if session_name:
            with Session(str(session_name)) as session:
                session.append("user", str(query), {"mode": "deep_research"})
                session.append(
                    "assistant",
                    str(res.get("answer") or ""),
                    {"mode": "deep_research", "research": _research_metadata(res)},
                )
        ui.success(f"Passes: {res.get('passes')} | Model: {res.get('model', '?')}")
        if session_name:
            ui.info(f"Saved session: {session_name}")
        if res.get("sub_questions"):
            ui.panel("\n".join(f"- {q}" for q in res["sub_questions"]), title="Sub-questions")
        ui.markdown(res.get("answer", ""))
        if res.get("sources"):
            ui.info(f"\n{len(res['sources'])} source(s):")
            for s in res["sources"][:8]:
                label = s.get("file") or s.get("url") or s.get("title") or "?"
                ui.info(f"  - {label}{' p. ' + str(s.get('page')) if s.get('page') else ''}")
        return 0
    except Exception as exc:
        ui.failure("Research", exc)
        return 1
