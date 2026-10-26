#!/usr/bin/env python3
"""Print one release's section of docs/CHANGELOG.md, to use as the GitHub release notes.

The release workflow fails when the section is missing or empty, so a tag can never
publish notes that skip the known limits written in the changelog.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANGELOG = ROOT / "docs" / "CHANGELOG.md"


def extract_release_notes(changelog: str, version: str) -> str:
    """Return the body under ``## [version]`` up to the next ``## `` heading."""
    heading = re.compile(rf"^## \[{re.escape(version)}\][^\n]*(?:\n|$)", re.MULTILINE)
    start = heading.search(changelog)
    if start is None:
        raise ValueError(f"CHANGELOG has no section for version {version}")
    rest = changelog[start.end() :]
    following = re.search(r"^## ", rest, re.MULTILINE)
    body = (rest[: following.start()] if following else rest).strip()
    if not body:
        raise ValueError(f"CHANGELOG section for version {version} is empty")
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="release version without the leading v, for example 1.4.0")
    parser.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    args = parser.parse_args(argv)
    try:
        notes = extract_release_notes(args.changelog.read_text(encoding="utf-8"), args.version)
    except (OSError, ValueError) as exc:
        print(f"release notes: {exc}", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
