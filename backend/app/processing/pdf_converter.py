from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

CHAPTER_PATTERN = re.compile(r"^第[一二三四五六七八九十百千零\d]+章")
SECTION_NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)+\s+")
TABLE_CAPTION_PATTERN = re.compile(r"^表\s*(\d+)[：:\s]?(.*)$")
FIGURE_CAPTION_PATTERN = re.compile(r"^图\s*(\d+)[：:\s]?(.*)$")
HEADING_LEVEL_PATTERN = re.compile(r"^#{1,6}\s+")

# 平均每页低于该字符数且含图片时，疑似扫描件
SCAN_CHARS_PER_PAGE_THRESHOLD = 40


@dataclass
class PdfPageContent:
    page_number: int
    text: str
    table_markdowns: list[str] = field(default_factory=list)
    image_count: int = 0


@dataclass
class PdfProbeResult:
    page_count: int
    pages_with_text: int
    total_chars: int
    total_images: int
    has_text_layer: bool
    likely_scanned: bool


@dataclass(frozen=True)
class PdfConvertResult:
    markdown: str
    metadata: dict[str, Any]
    parse_engine: str
    parse_quality: str
    has_tables: bool
    has_figures: bool
    page_count: int
    char_count: int
    warnings: list[str]
    figure_assets: list[dict[str, Any]] = field(default_factory=list)


def convert_pdf_to_markdown(payload: bytes, *, file_name: str = "document.pdf") -> PdfConvertResult:
    """PDF → Markdown：默认 PyMuPDF + pdfplumber；扫描件可回退 Docling worker。"""
    validate_pdf_payload(payload)
    warnings: list[str] = []

    probe = _probe_with_pymupdf(payload)
    if _should_use_docling_worker(probe):
        return _convert_via_docling_worker(payload, probe, file_name=file_name)

    if not probe.has_text_layer:
        raise ValueError(
            "PDF 无文字层，疑似扫描件，需 OCR 通道（请启用 Docling worker 或二期 OCR）"
        )
    if probe.likely_scanned:
        warnings.append("文本密度偏低且含图片，可能为扫描件，建议人工复核")

    pages = _extract_pages_with_pymupdf(payload)
    table_map = _extract_tables_with_pdfplumber(payload, warnings)
    for page in pages:
        page.table_markdowns = table_map.get(page.page_number, [])

    markdown = _build_markdown_output(pages, probe, warnings)
    if not markdown.strip():
        raise ValueError("PDF 未抽取到有效文本")

    has_tables = any(page.table_markdowns for page in pages) or bool(
        TABLE_CAPTION_PATTERN.search(markdown)
    )
    has_figures = probe.total_images > 0 or bool(
        FIGURE_CAPTION_PATTERN.search(markdown)
    )
    quality = _assess_pdf_quality(probe, pages, has_tables, warnings)
    engine = "pymupdf+pdfplumber" if has_tables else "pymupdf"

    metadata = {
        "pageCount": probe.page_count,
        "pagesWithText": probe.pages_with_text,
        "totalImages": probe.total_images,
        "tableCount": sum(len(p.table_markdowns) for p in pages),
        "hasTables": has_tables,
        "hasFigures": has_figures,
        "likelyScanned": probe.likely_scanned,
    }

    return PdfConvertResult(
        markdown=markdown.strip(),
        metadata=metadata,
        parse_engine=engine,
        parse_quality=quality,
        has_tables=has_tables,
        has_figures=has_figures,
        page_count=probe.page_count,
        char_count=len(markdown.strip()),
        warnings=warnings,
    )


def validate_pdf_payload(payload: bytes) -> None:
    if not payload:
        raise ValueError("PDF 内容为空")
    if not payload[:5].startswith(b"%PDF"):
        preview = payload[:16].hex(" ")
        raise ValueError(f"不是有效的 PDF 文件（文件头: {preview}）")


def _probe_with_pymupdf(payload: bytes) -> PdfProbeResult:
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("未安装 pymupdf，无法解析 PDF") from exc

    document = fitz.open(stream=payload, filetype="pdf")
    page_count = document.page_count
    pages_with_text = 0
    total_chars = 0
    total_images = 0

    for page in document:
        text = page.get_text("text").strip()
        if text:
            pages_with_text += 1
            total_chars += len(text)
        total_images += len(page.get_images())

    document.close()

    avg_chars = total_chars / page_count if page_count else 0
    has_text_layer = pages_with_text > 0
    likely_scanned = (
        has_text_layer
        and avg_chars < SCAN_CHARS_PER_PAGE_THRESHOLD
        and total_images > 0
    )

    return PdfProbeResult(
        page_count=page_count,
        pages_with_text=pages_with_text,
        total_chars=total_chars,
        total_images=total_images,
        has_text_layer=has_text_layer,
        likely_scanned=likely_scanned,
    )


def _extract_pages_with_pymupdf(payload: bytes) -> list[PdfPageContent]:
    import fitz

    document = fitz.open(stream=payload, filetype="pdf")
    pages: list[PdfPageContent] = []

    for page in document:
        text = page.get_text("text", sort=True).strip()
        pages.append(
            PdfPageContent(
                page_number=page.number + 1,
                text=text,
                image_count=len(page.get_images()),
            )
        )

    document.close()
    return pages


def _extract_tables_with_pdfplumber(
    payload: bytes,
    warnings: list[str],
) -> dict[int, list[str]]:
    try:
        import pdfplumber
    except ImportError as exc:
        warnings.append("未安装 pdfplumber，表格将仅以正文形式保留")
        return {}

    table_map: dict[int, list[str]] = {}
    try:
        with pdfplumber.open(BytesIO(payload)) as pdf:
            for index, page in enumerate(pdf.pages):
                page_number = index + 1
                tables = page.extract_tables() or []
                markdowns: list[str] = []
                for table in tables:
                    table_md = _rows_to_markdown_table(table)
                    if table_md:
                        markdowns.append(table_md)
                if markdowns:
                    table_map[page_number] = markdowns
    except Exception as exc:
        warnings.append(f"pdfplumber 表格抽取失败: {exc}")

    return table_map


def _rows_to_markdown_table(rows: list[list[Any]]) -> str:
    normalized_rows: list[list[str]] = []
    for row in rows:
        cells = [
            str(cell).strip().replace("\n", " ") if cell is not None else ""
            for cell in row
        ]
        if any(cells):
            normalized_rows.append(cells)

    if not normalized_rows:
        return ""

    header = normalized_rows[0]
    body = normalized_rows[1:] if len(normalized_rows) > 1 else []
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[: len(header)]) + " |")
    return "\n".join(lines)


def _build_markdown_output(
    pages: list[PdfPageContent],
    probe: PdfProbeResult,
    warnings: list[str],
) -> str:
    parts: list[str] = [
        f"<!-- pdf-meta:{json.dumps({'pageCount': probe.page_count, 'warnings': warnings}, ensure_ascii=False)} -->"
    ]

    for page in pages:
        parts.append(f"<!-- page:{page.page_number} -->")
        if page.text:
            parts.append(_normalize_pdf_text(page.text))

        for table_md in page.table_markdowns:
            parts.append(f"<!-- table:page-{page.page_number} -->")
            parts.append(table_md)

        if page.image_count > 0:
            parts.append(
                f"<!-- figures:page-{page.page_number} count={page.image_count} -->"
            )

    return "\n\n".join(part for part in parts if part.strip())


def _normalize_pdf_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if HEADING_LEVEL_PATTERN.match(line):
            lines.append(line)
            continue
        table_match = TABLE_CAPTION_PATTERN.match(line)
        if table_match:
            caption = f"表 {table_match.group(1)}"
            if table_match.group(2):
                caption += f" {table_match.group(2).strip()}"
            lines.append(f"### {caption}")
            continue
        figure_match = FIGURE_CAPTION_PATTERN.match(line)
        if figure_match:
            caption = f"图 {figure_match.group(1)}"
            if figure_match.group(2):
                caption += f" {figure_match.group(2).strip()}"
            lines.append(f"### {caption}")
            continue
        if CHAPTER_PATTERN.match(line):
            lines.append(f"# {line}")
            continue
        if SECTION_NUMBER_PATTERN.match(line):
            lines.append(f"### {line}")
            continue
        lines.append(line)

    return "\n".join(lines)


def _assess_pdf_quality(
    probe: PdfProbeResult,
    pages: list[PdfPageContent],
    has_tables: bool,
    warnings: list[str],
) -> str:
    if probe.likely_scanned:
        return "low"

    structured_lines = 0
    for page in pages:
        for line in page.text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if (
                CHAPTER_PATTERN.match(stripped)
                or SECTION_NUMBER_PATTERN.match(stripped)
                or TABLE_CAPTION_PATTERN.match(stripped)
            ):
                structured_lines += 1

    if structured_lines >= 2 and not warnings:
        return "high"
    if has_tables or structured_lines >= 1:
        return "medium"
    if probe.pages_with_text >= max(1, probe.page_count // 2):
        return "medium"
    return "low"


def _should_use_docling_worker(probe: PdfProbeResult) -> bool:
    from app.processing.docling_client import is_docling_worker_configured

    if not is_docling_worker_configured():
        return False

    from app.config import get_settings

    settings = get_settings()
    if not probe.has_text_layer and settings.docling_fallback_on_no_text_layer:
        return True
    if probe.likely_scanned and settings.docling_fallback_on_likely_scanned:
        return True
    return False


def _convert_via_docling_worker(
    payload: bytes,
    probe: PdfProbeResult,
    *,
    file_name: str,
) -> PdfConvertResult:
    from app.processing.docling_client import DoclingWorkerError, convert_pdf_via_worker

    try:
        worker_result = convert_pdf_via_worker(payload, file_name=file_name)
    except DoclingWorkerError as exc:
        raise ValueError(str(exc)) from exc

    warnings = list(worker_result.warnings)
    if not probe.has_text_layer:
        warnings.append("PDF 无文字层，已通过 Docling worker 解析")
    elif probe.likely_scanned:
        warnings.append("文本密度偏低，已通过 Docling worker 解析")

    metadata = {
        "pageCount": worker_result.page_count or probe.page_count,
        "pagesWithText": probe.pages_with_text,
        "totalImages": probe.total_images,
        "tableCount": None,
        "hasTables": worker_result.has_tables,
        "hasFigures": worker_result.has_figures,
        "likelyScanned": probe.likely_scanned,
        "workerElapsedSec": worker_result.elapsed_sec,
    }

    figure_assets = [
        {
            "file_name": figure.file_name,
            "content_base64": figure.content_base64,
            "page_no": figure.page_no,
            "captions": figure.captions,
        }
        for figure in worker_result.figures
        if figure.content_base64
    ]

    return PdfConvertResult(
        markdown=worker_result.markdown,
        metadata=metadata,
        parse_engine=worker_result.parse_engine,
        parse_quality=worker_result.parse_quality,
        has_tables=worker_result.has_tables,
        has_figures=worker_result.has_figures or bool(figure_assets),
        page_count=worker_result.page_count or probe.page_count,
        char_count=worker_result.char_count,
        warnings=warnings,
        figure_assets=figure_assets,
    )
