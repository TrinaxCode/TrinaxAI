"""TrinaxAI CLI v2 — modular local-first terminal assistant.

See ``trinaxai_cli.app`` for the entry point and ``trinaxai_cli.commands``
for the individual subcommand implementations.
"""

import importlib.util
import os
import sys

# An editable install made before the ``trinaxai`` package existed maps only the
# older top-level names. Fall back to the directory that holds this package so
# an upgraded tree keeps working until ``pip install -e .`` is re-run.
if importlib.util.find_spec("trinaxai") is None:
    _package_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _package_parent not in sys.path:
        sys.path.append(_package_parent)
