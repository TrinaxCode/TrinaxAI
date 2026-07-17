from __future__ import annotations

from io import BytesIO

import rag_api


def test_extracts_pptx_text() -> None:
    from pptx import Presentation

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "TrinaxAI slides"
    slide.placeholders[1].text = "Readable presentation content"
    data = BytesIO()
    presentation.save(data)

    text = rag_api._extract_document_text("deck.pptx", data.getvalue())

    assert "TrinaxAI slides" in text
    assert "Readable presentation content" in text


def test_extracts_xlsx_text() -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Budget"
    sheet.append(["Item", "Amount"])
    sheet.append(["Hosting", 25])
    data = BytesIO()
    workbook.save(data)

    text = rag_api._extract_document_text("budget.xlsx", data.getvalue())

    assert "[Sheet: Budget]" in text
    assert "Hosting\t25" in text


def test_extracts_rtf_text() -> None:
    text = rag_api._extract_document_text("notes.rtf", br"{\rtf1\ansi TrinaxAI notes}")
    assert "TrinaxAI notes" in text


def test_extracts_odt_text() -> None:
    from odf.opendocument import OpenDocumentText
    from odf.text import P

    document = OpenDocumentText()
    document.text.addElement(P(text="OpenDocument content for TrinaxAI"))
    data = BytesIO()
    document.save(data)

    text = rag_api._extract_document_text("notes.odt", data.getvalue())

    assert "OpenDocument content for TrinaxAI" in text


def test_memory_fallback_never_persists_model_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(rag_api, "_memory_load", lambda: {"memories": [{"text": "Prefiere respuestas breves"}]})
    monkeypatch.setattr(rag_api.config, "PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(rag_api, "get_llm", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    result = rag_api._memory_refresh_sync(rag_api.MemoryRefreshRequest())

    assert result["summary"] == "Prefiere respuestas breves"
    assert "LLM unavailable" not in result["summary"]
