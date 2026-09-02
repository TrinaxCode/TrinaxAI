"""Compatibility alias for :mod:`trinaxai_agent.tools`."""

import sys

from trinaxai_agent import tools as implementation

sys.modules[__name__] = implementation
