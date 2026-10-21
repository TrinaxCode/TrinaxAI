"""Recovery server entry point and compatibility alias for :mod:`trinaxai.supervisor.recovery_server`.

This file stays at the install root because units, scheduled tasks, installers
and the CLI run it by path (see docs/adr/0001-python-package-layout.md).
Run as a script it executes the command; imported as ``recovery_server`` it *is* the
real module.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

from trinaxai.supervisor import recovery_server as _impl  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_impl.main())

sys.modules[__name__] = _impl
