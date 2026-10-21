"""Compatibility alias for :mod:`trinaxai.config` (see docs/adr/0001-python-package-layout.md)."""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

from trinaxai import config as _impl  # noqa: E402

sys.modules[__name__] = _impl
