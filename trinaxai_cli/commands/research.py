"""``trinaxai research`` — multi-pass deep research."""

from __future__ import annotations

from typing import Any


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
            res = client.research(query=query, collections=collections, depth=depth)
        ui.success(f"Passes: {res.get('passes')} · Model: {res.get('model', '?')}")
        if res.get("sub_questions"):
            ui.panel("\n".join(f"• {q}" for q in res["sub_questions"]), title="Sub-questions")
        ui.markdown(res.get("answer", ""))
        if res.get("sources"):
            ui.info(f"\n{len(res['sources'])} source(s):")
            for s in res["sources"][:8]:
                ui.info(f"  • {s.get('file')}{' p. ' + str(s.get('page')) if s.get('page') else ''}")
        return 0
    except Exception as exc:
        ui.error(f"research: {exc}")
        return 1
