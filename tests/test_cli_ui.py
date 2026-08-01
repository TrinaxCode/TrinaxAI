from __future__ import annotations

import pytest

from trinaxai_cli.ui import Console


def test_spinner_propagates_command_errors_without_contextmanager_failure() -> None:
    console = Console(no_color=True)

    with pytest.raises(RuntimeError, match="request failed"):
        with console.spinner("Working..."):
            raise RuntimeError("request failed")


def test_failure_hides_unexpected_exception_details(capsys) -> None:
    console = Console(no_color=True)

    try:
        raise RuntimeError("password=secret at /home/service.py:42")
    except RuntimeError as exc:
        console.failure("Research", exc)

    output = capsys.readouterr().out
    assert "Research could not be completed" in output
    assert "password" not in output
    assert "RuntimeError" not in output
    assert "/home/" not in output
