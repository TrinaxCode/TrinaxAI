from __future__ import annotations

from typing import Any

from trinaxai_cli.commands import _system
from trinaxai_cli.i18n import text


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    action = "stop-all" if getattr(args, "all", False) else "stop-ai"
    language = getattr(ui, "language", "en")
    target = text("stop_all_target" if action == "stop-all" else "stop_ai_target", language)
    if not getattr(args, "yes", False) and not ui.confirm(text("stop_confirm", language, target=target), default=False):
        ui.info(text("cancelled", language))
        return 0
    ui.info(text("stopping", language, target=target))
    return _system.run_service_action(action, ui, timeout=180)
