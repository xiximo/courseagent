from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.processing.docx_converter import convert_docx_to_markdown
from app.processing.pdf_converter import convert_pdf_to_markdown


@dataclass(frozen=True)
class ParseResult:
    content: str
    parse_engine: str
    parse_quality: str
    has_tables: bool
    has_figures: bool
    page_count: int | None
    char_count: int
    figure_assets: list[dict[str, Any]] = field(default_factory=list)


def extract_attachment_text(
    payload: bytes,
    file_type: str,
    file_name: str,
) -> ParseResult:
    normalized = (file_type or "").lower()
    name_lower = (file_name or "").lower()

    if normalized == "docx" or name_lower.endswith(".docx"):
        return _parse_docx(payload, file_name)
    if normalized == "pdf" or name_lower.endswith(".pdf"):
        return _parse_pdf(payload, file_name)
    if normalized == "doc" or name_lower.endswith(".doc"):
        raise ValueError(
            "DOC 格式需先转换为 DOCX（LibreOffice headless），暂不支持直接解析"
        )
    if normalized in {"md", "markdown"} or name_lower.endswith((".md", ".markdown")):
        text = payload.decode("utf-8", errors="replace").strip()
        return ParseResult(
            content=text,
            parse_engine="markdown",
            parse_quality="high" if text else "low",
            has_tables=_contains_markdown_table(text),
            has_figures=False,
            page_count=None,
            char_count=len(text),
        )
    if normalized == "txt" or name_lower.endswith(".txt"):
        text = payload.decode("utf-8", errors="replace").strip()
        return ParseResult(
            content=text,
            parse_engine="plain-text",
            parse_quality="high" if text else "low",
            has_tables=False,
            has_figures=False,
            page_count=None,
            char_count=len(text),
        )
    raise ValueError(f"暂不支持的附件类型: {file_type or file_name}")


def _parse_docx(payload: bytes, file_name: str = "") -> ParseResult:
    result = convert_docx_to_markdown(payload, file_name=file_name)
    return ParseResult(
        content=result.markdown,
        parse_engine=result.parse_engine,
        parse_quality=result.parse_quality,
        has_tables=result.has_tables,
        has_figures=result.has_figures,
        page_count=None,
        char_count=result.char_count,
    )


def _contains_markdown_table(text: str) -> bool:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("|") and index + 1 < len(lines):
            if "---" in lines[index + 1]:
                return True
    return False


def _parse_pdf(payload: bytes, file_name: str = "") -> ParseResult:
    result = convert_pdf_to_markdown(payload, file_name=file_name or "document.pdf")
    return ParseResult(
        content=result.markdown,
        parse_engine=result.parse_engine,
        parse_quality=result.parse_quality,
        has_tables=result.has_tables,
        has_figures=result.has_figures,
        page_count=result.page_count,
        char_count=result.char_count,
        figure_assets=list(result.figure_assets),
    )
