"""Where the TrinaxAI install root is, relative to this package.

``trinaxai/`` sits directly under the install root (source checkout, Docker
``/app``) or under ``site-packages`` (wheel), so the root is its parent. Keep
this the only place that encodes that assumption.
"""

from __future__ import annotations

import os
from pathlib import Path

# Not symlink-resolved: matches what ``config.BASE_DIR`` has always reported.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Symlink-resolved: matches the ``--base-dir`` default the supervisor used.
PROJECT_ROOT_RESOLVED = Path(__file__).resolve().parents[1]
