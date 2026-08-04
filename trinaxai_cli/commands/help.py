from __future__ import annotations

from typing import Any

from trinaxai_cli.app import _build_parser


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    try:
        parser = _build_parser(getattr(ui, "language", None))
    except TypeError:
        parser = _build_parser()
    ui.print(parser.format_help())
    return 0
