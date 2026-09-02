"""Compatibility alias for :mod:`trinaxai_agent.extract`."""

import sys

from trinaxai_agent import extract as implementation

sys.modules[__name__] = implementation
