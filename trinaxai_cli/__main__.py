"""Allow ``python -m trinaxai_cli`` invocation.

This is the canonical entry point referenced by the bash wrapper installed
in Chunk 4 (and by IDEs / task runners that prefer module-style launch).
"""

from trinaxai_cli.app import main

raise SystemExit(main())
