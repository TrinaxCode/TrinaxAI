"""Compatibility alias for :mod:`trinaxai_agent.engine`."""

import sys

from trinaxai_agent import engine as implementation

sys.modules[__name__] = implementation
