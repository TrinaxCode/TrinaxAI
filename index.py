"""Indexer entry point and compatibility alias for :mod:`trinaxai.indexing.indexer`.

This file stays at the install root because the API, the file watcher, the CLI
and the installers run it by path (see docs/adr/0001-python-package-layout.md).
Run as a script it indexes; imported as ``index`` it *is* the real module.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

from trinaxai.indexing import indexer as _impl  # noqa: E402

if __name__ == "__main__":
    sys.exit(_impl.run_index())

sys.modules[__name__] = _impl
