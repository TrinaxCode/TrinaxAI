from __future__ import annotations

import pytest

from trinaxai_cli.ui import Console


def test_spinner_propagates_command_errors_without_contextmanager_failure() -> None:
    console = Console(no_color=True)

    with pytest.raises(RuntimeError, match="request failed"):
        with console.spinner("Working..."):
            raise RuntimeError("request failed")
