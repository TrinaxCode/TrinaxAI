from __future__ import annotations

from pathlib import Path

from trinaxai_cli.agent.tools import _glob, _grep, _list_dir


def test_list_dir_rejects_an_accidentally_broad_root(tmp_path: Path) -> None:
    for index in range(201):
        (tmp_path / f"file-{index}.txt").write_text("x", encoding="utf-8")
    result = _list_dir(tmp_path)
    assert "too broad" in result
    assert "project folder" in result


def test_glob_is_root_only_unless_recursive_pattern_is_explicit(tmp_path: Path) -> None:
    (tmp_path / "root.py").write_text("x", encoding="utf-8")
    nested = tmp_path / "src"
    nested.mkdir()
    (nested / "nested.py").write_text("x", encoding="utf-8")
    assert _glob(tmp_path, "*.py") == "root.py"
    assert "src/nested.py" in _glob(tmp_path, "**/*.py").replace("\\", "/")


def test_grep_marks_bounded_results(tmp_path: Path) -> None:
    for index in range(110):
        (tmp_path / f"file-{index}.txt").write_text("needle\n", encoding="utf-8")
    result = _grep(tmp_path, "needle")
    assert "truncated" in result
