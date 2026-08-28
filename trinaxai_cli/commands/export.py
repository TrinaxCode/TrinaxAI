"""``trinaxai export`` — export a saved session as Markdown, PDF, or Word."""

from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from zipfile import ZIP_DEFLATED, ZipFile

from trinaxai_cli.session import Session

# ``app.py`` owns argparse and is intentionally outside this task's scope.
# It can use this tuple as its choices when the parser integration is enabled.
SUPPORTED_FORMATS = ("md", "pdf", "docx")
_FORMAT_ALIASES = {
    "md": "md",
    "markdown": "md",
    "pdf": "pdf",
    "doc": "docx",
    "docx": "docx",
    "word": "docx",
}
_EXTENSIONS = {"md": "md", "pdf": "pdf", "docx": "docx"}
_SENSITIVE_META = ("token", "secret", "password", "credential", "authorization", "api_key", "api-key")


def _format_name(value: Any) -> str | None:
    value = str(value or "md").strip().lower().lstrip(".")
    return _FORMAT_ALIASES.get(value)


def _safe_name(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").replace("..", "_").strip() or "default"


def _markdown(name: str, records: list[dict[str, Any]]) -> str:
    lines = [f"# TrinaxAI session: {name}", ""]
    for record in records:
        role = record.get("role", "?")
        content = str(record.get("content") or "").rstrip()
        timestamp = record.get("ts", 0)
        lines += [f"## {role}  ({timestamp})", "", content, ""]
        meta = record.get("meta")
        if isinstance(meta, dict):
            public_meta = {
                str(key): value
                for key, value in meta.items()
                if not any(term in str(key).lower() for term in _SENSITIVE_META) and value not in (None, "", [], {})
            }
            if public_meta:
                lines += ["### Metadata", ""]
                for key, value in public_meta.items():
                    if key == "research" and isinstance(value, dict):
                        lines.append("- research:")
                        for research_key, research_value in value.items():
                            if (
                                research_key == "sources"
                                or any(term in str(research_key).lower() for term in _SENSITIVE_META)
                                or research_value in (None, "", [], {})
                            ):
                                continue
                            lines.append(f"  - {research_key}: {research_value}")
                        sources = value.get("sources")
                        if isinstance(sources, list) and sources:
                            lines.append("  - sources:")
                            for index, source in enumerate(sources, 1):
                                if isinstance(source, dict):
                                    label = source.get("title") or source.get("file") or source.get("url") or "Source"
                                    url = source.get("url")
                                    details = " | ".join(
                                        f"{field}: {source[field]}"
                                        for field in ("page", "collection", "provider", "authority", "snippet")
                                        if source.get(field) not in (None, "")
                                    )
                                    lines.append(
                                        f"    {index}. {label}{f' ({url})' if url else ''}{f' — {details}' if details else ''}"
                                    )
                                else:
                                    lines.append(f"    {index}. {source}")
                    else:
                        lines.append(f"- {key}: {value}")
                lines.append("")
    return "\n".join(lines)


def _pdf_escape(value: str) -> bytes:
    # WinAnsi keeps Spanish accents and common typographic punctuation in the
    # built-in Helvetica font without adding a font dependency.
    encoded = value.encode("cp1252", "replace")
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _pdf_lines(text: str, width: int = 88) -> list[str]:
    result: list[str] = []
    for line in text.splitlines() or [""]:
        while len(line) > width:
            split_at = line.rfind(" ", 0, width + 1)
            split_at = split_at if split_at > 0 else width
            result.append(line[:split_at].rstrip())
            line = line[split_at:].lstrip()
        result.append(line)
    return result


def _pdf(text: str) -> bytes:
    lines = _pdf_lines(text)
    page_size = 48
    pages = [lines[index : index + page_size] for index in range(0, len(lines), page_size)] or [[]]
    page_ids = [3 + index for index in range(len(pages))]
    content_ids = [3 + len(pages) + index for index in range(len(pages))]
    font_id = 3 + 2 * len(pages)

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(pages)} >>".encode(),
        font_id: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for page_id, content_id, page_lines in zip(page_ids, content_ids, pages, strict=True):
        commands = [b"BT", b"/F1 10 Tf", b"54 738 Td"]
        for index, line in enumerate(page_lines):
            if index:
                commands.append(b"0 -14 Td")
            commands.append(b"(" + _pdf_escape(line) + b") Tj")
        stream = b"\n".join(commands) + b"\nET"
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()
        objects[content_id] = f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"

    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, font_id + 1):
        offsets.append(len(document))
        document += f"{object_id} 0 obj\n".encode() + objects[object_id] + b"\nendobj\n"
    xref = len(document)
    document += f"xref\n0 {font_id + 1}\n0000000000 65535 f \n".encode()
    document += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    document += f"trailer\n<< /Size {font_id + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(document)


def _docx_paragraph(value: str) -> str:
    if not value:
        return "<w:p/>"
    return f'<w:p><w:r><w:t xml:space="preserve">{escape(value)}</w:t></w:r></w:p>'


def _docx(name: str, records: list[dict[str, Any]]) -> bytes:
    paragraphs = _markdown(name, records).splitlines()
    body = "".join(_docx_paragraph(paragraph) for paragraph in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>'
    ).encode()
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    ).encode()
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    ).encode()
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", document)
    return output.getvalue()


def _output_path(raw_output: Any, name: str, fmt: str) -> Path:
    if raw_output is None:
        return (Path.cwd() / f"trinaxai-{_safe_name(name)}.{_EXTENSIONS[fmt]}").resolve()
    if not str(raw_output).strip():
        raise ValueError("Output path cannot be empty.")
    output = Path(raw_output).expanduser().resolve()
    if output.exists() and output.is_dir():
        raise IsADirectoryError(output)
    if not output.parent.is_dir():
        raise FileNotFoundError(output.parent)
    return output


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    name = str(getattr(args, "session", None) or "default")
    fmt = _format_name(getattr(args, "format", "md"))
    if fmt is None:
        ui.error(f"Unsupported export format. Choose one of: {', '.join(SUPPORTED_FORMATS)}.")
        return 1
    try:
        out_path = _output_path(getattr(args, "output", None), name, fmt)
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        ui.error(f"Invalid output path: {exc}")
        return 1
    try:
        records = Session.load(name)
    except Exception as exc:
        ui.failure(f"Load session '{name}'", exc)
        return 1
    if not records:
        ui.error(f"Session '{name}' is empty.")
        return 1

    renderers: dict[str, Callable[[], str | bytes]] = {
        "md": lambda: _markdown(name, records),
        "pdf": lambda: _pdf(_markdown(name, records)),
        "docx": lambda: _docx(name, records),
    }
    try:
        rendered = renderers[fmt]()
        if isinstance(rendered, bytes):
            out_path.write_bytes(rendered)
        else:
            out_path.write_text(rendered, encoding="utf-8")
    except Exception as exc:
        ui.failure(f"Write '{out_path}'", exc)
        return 1
    ui.success(f"Exported {len(records)} record(s) -> {out_path}")
    return 0
