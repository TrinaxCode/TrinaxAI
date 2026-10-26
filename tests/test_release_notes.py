import re
from pathlib import Path

import pytest

from scripts import release_notes

CHANGELOG = """# Changelog

## [Unreleased]

## [1.4.0] — 2026-10-26

### Added

- Something new.

### Known limits

- A limit.

## [1.3.0] — 2026-10-18

- Older.
"""


def test_extracts_only_the_requested_section() -> None:
    notes = release_notes.extract_release_notes(CHANGELOG, "1.4.0")

    assert notes.startswith("### Added")
    assert "### Known limits" in notes
    assert "Older." not in notes
    assert "[1.4.0]" not in notes


def test_last_section_runs_to_the_end_of_the_file() -> None:
    assert release_notes.extract_release_notes(CHANGELOG, "1.3.0") == "- Older."


def test_missing_or_empty_sections_are_errors() -> None:
    with pytest.raises(ValueError, match="no section for version 9.9.9"):
        release_notes.extract_release_notes(CHANGELOG, "9.9.9")
    with pytest.raises(ValueError, match="empty"):
        release_notes.extract_release_notes(CHANGELOG, "Unreleased")
    with pytest.raises(ValueError, match="no section"):
        release_notes.extract_release_notes(CHANGELOG, "1.4")


def test_cli_prints_notes_and_fails_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")

    assert release_notes.main(["1.4.0", "--changelog", str(changelog)]) == 0
    assert "### Known limits" in capsys.readouterr().out
    assert release_notes.main(["2.0.0", "--changelog", str(changelog)]) == 1
    assert "no section for version 2.0.0" in capsys.readouterr().err
    assert release_notes.main(["1.4.0", "--changelog", str(tmp_path / "missing.md")]) == 1


def test_the_repository_changelog_has_notes_for_the_current_version() -> None:
    root = Path(release_notes.__file__).resolve().parents[1]
    match = re.search(r'^version = "([^"]+)"$', (root / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None
    version = match.group(1)

    notes = release_notes.extract_release_notes((root / "docs" / "CHANGELOG.md").read_text(encoding="utf-8"), version)

    assert notes
