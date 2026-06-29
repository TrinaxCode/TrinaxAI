from __future__ import annotations

from typing import Any

from trinaxai_cli.app import _build_parser


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    ui.print(_build_parser().format_help())
    return 0
