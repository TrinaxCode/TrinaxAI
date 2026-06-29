from __future__ import annotations

import sys

import test_system


def test_check_python_returns_structured_result() -> None:
    results = test_system.check_python()
    assert len(results) == 1
    assert results[0].group == "Runtime"
    assert results[0].ok is (sys.version_info >= (3, 10))


def test_summary_output_does_not_raise(capsys) -> None:  # noqa: ANN001
    test_system.print_results(
        [test_system.CheckResult("example", False, "detail", "Group")],
        summary_only=True,
    )
    assert "Se encontraron 1 problemas" in capsys.readouterr().out
