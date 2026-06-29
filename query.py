"""Backward-compatible entrypoint for TrinaxAI CLI.

Deprecated — use ``python -m trinaxai_cli`` or ``python trinaxai_cli.py`` instead.
"""
import warnings

warnings.warn(
    "query.py is deprecated; use 'python -m trinaxai_cli' or 'python trinaxai_cli.py'",
    DeprecationWarning,
    stacklevel=2,
)

from trinaxai_cli.app import main


if __name__ == "__main__":
    raise SystemExit(main())
