from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from html import unescape
from io import BytesIO
from typing import Any, Iterator

from app.processing.docx_compat import apply_python_docx_compat
from app.processing.docx_payload import (
    friendly_docx_error,
    is_repairable_docx_error,
    prepare_docx_payload,
    repair_docx_archive,
)

# 中文/英文 Word 标题样式 → Markdown 标题映射（mammoth style_map）
DOCX_STYLE_MAP = """
p[style-name='Heading 1'] => h1:fresh
p[style-name='Heading 2'] => h2:fresh
p[style-name='Heading 3'] => h3:fresh
p[style-name='Heading 4'] => h4:fresh
p[style-name='Heading 5'] => h5:fresh
p[style-name='Heading 6'] => h6:fresh
p[style-name='标题 1'] => h1:fresh
p[style-name='标题 2'] => h2:fresh
p[style-name='标题 3'] => h3:fresh
p[style-name='标题 4'] => h4:fresh
p[style-name='标题 5'] => h5:fresh
p[style-name='标题 6'] => h6:fresh
p[style-name='标题1'] => h1:fresh
p[style-name='标题2'] => h2:fresh
p[style-name='标题3'] => h3:fresh
p[style-name='标题4'] => h4:fresh
p[style-name='标题5'] => h5:fresh
p[style-name='标题6'] => h6:fresh
p[style-name='TOC Heading'] => h2:fresh
"""

HEADING_LEVEL_PATTERN = re.compile(r"^#{1,6}\s+")
CHAPTER_PATTERN = re.compile(r"^第[一二三四五六七八九十百千零\d]+章")
SECTION_NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)+\s+")
HTML_TABLE_PATTERN = re.compile(r"<table[\s\S]*?</table>", re.IGNORECASE)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocxStructureBlock:
    kind: str
    text: str
    style_name: str | None = None
    heading_level: int | None = None
    list_level: int | None = None
    is_ordered_list: bool = False


@dataclass
class DocxStructure:
    blocks: list[DocxStructureBlock] = field(default_factory=list)
    table_markdowns: list[str] = field(default_factory=list)
    heading_count: int = 0
    paragraph_count: int = 0
    has_tables: bool = False
    has_figures: bool = False
    style_names: list[str] = field(default_factory=list)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "paragraphCount": self.paragraph_count,
            "headingCount": self.heading_count,
            "tableCount": len(self.table_markdowns),
            "hasTables": self.has_tables,
            "hasFigures": self.has_figures,
            "styleNames": self.style_names[:20],
            "blockCount": len(self.blocks),
        }


@dataclass(frozen=True)
class DocxConvertResult:
    markdown: str
    metadata: dict[str, Any]
    parse_engine: str
    parse_quality: str
    has_tables: bool
    has_figures: bool
    char_count: int
    warnings: list[str]


def convert_docx_to_markdown(
    payload: bytes,
    file_name: str = "",
) -> DocxConvertResult:
    """DOCX → Markdown：mammoth 负责正文/标题，python-docx 负责结构与表格补强。"""
    apply_python_docx_compat()
    prepared = _prepare_with_retry(payload, file_name)

    structure = _analyze_structure_with_python_docx(prepared)
    mammoth_markdown, mammoth_warnings = _convert_with_mammoth(prepared)
    markdown = _merge_markdown_output(mammoth_markdown, structure)
    warnings = list(mammoth_warnings)

    if not markdown.strip():
        markdown = _build_markdown_from_structure(structure)
        if not mammoth_markdown.strip() and markdown.strip():
            warnings.append("已使用 python-docx 结构转换作为正文")

    if not markdown.strip():
        raise ValueError("DOCX 未抽取到有效文本")

    has_md_tables = "|" in markdown and "---" in markdown
    has_tables = structure.has_tables or has_md_tables
    quality = _assess_quality(markdown, structure, warnings)
    parse_engine = (
        "python-docx+mammoth" if mammoth_markdown.strip() else "python-docx"
    )

    return DocxConvertResult(
        markdown=markdown.strip(),
        metadata=structure.to_metadata(),
        parse_engine=parse_engine,
        parse_quality=quality,
        has_tables=has_tables,
        has_figures=structure.has_figures,
        char_count=len(markdown.strip()),
        warnings=warnings,
    )


def _prepare_with_retry(payload: bytes, file_name: str) -> bytes:
    try:
        return prepare_docx_payload(payload, file_name)
    except ValueError:
        raise
    except Exception as exc:
        if not is_repairable_docx_error(exc):
            raise friendly_docx_error(exc, file_name) from exc
        try:
            repaired = repair_docx_archive(payload)
            return prepare_docx_payload(repaired, file_name)
        except Exception as retry_exc:
            raise friendly_docx_error(retry_exc, file_name) from retry_exc


def _convert_with_mammoth(payload: bytes) -> tuple[str, list[str]]:
    try:
        import mammoth
    except ImportError as exc:
        raise ValueError("未安装 mammoth，无法将 DOCX 转换为 Markdown") from exc

    try:
        result = mammoth.convert_to_markdown(
            BytesIO(payload),
            style_map=DOCX_STYLE_MAP,
        )
        warnings = [str(message) for message in result.messages]
        return (result.value or "").strip(), warnings
    except Exception as exc:
        logger.warning(
            "mammoth DOCX convert failed, fallback to python-docx: %s",
            exc,
            exc_info=True,
        )
        return "", [
            f"mammoth 解析失败（{type(exc).__name__}），已回退 python-docx 纯文本抽取"
        ]


def _analyze_structure_with_python_docx(payload: bytes) -> DocxStructure:
    try:
        from docx import Document
        from docx.document import Document as DocumentType
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:
        raise ValueError("未安装 python-docx，无法解析 DOCX 结构") from exc

    document = Document(BytesIO(payload))
    structure = DocxStructure()
    seen_styles: set[str] = set()

    for block in _iter_block_items(document, DocumentType, Paragraph, Table, qn):
        if isinstance(block, Table):
            table_md = _table_to_markdown(block)
            if table_md:
                structure.table_markdowns.append(table_md)
                structure.blocks.append(
                    DocxStructureBlock(kind="table", text=table_md)
                )
            continue

        paragraph = block
        text = paragraph.text.strip()
        style_name = paragraph.style.name if paragraph.style else None
        if style_name and style_name not in seen_styles:
            seen_styles.add(style_name)
            structure.style_names.append(style_name)

        if not text:
            continue

        structure.paragraph_count += 1
        heading_level = _resolve_heading_level(style_name, text)
        if heading_level:
            structure.heading_count += 1

        list_level, is_ordered = _resolve_list_info(paragraph)
        structure.blocks.append(
            DocxStructureBlock(
                kind="heading" if heading_level else "paragraph",
                text=text,
                style_name=style_name,
                heading_level=heading_level,
                list_level=list_level,
                is_ordered_list=is_ordered,
            )
        )

        if _paragraph_has_image(paragraph):
            structure.has_figures = True

    structure.has_tables = bool(structure.table_markdowns)
    return structure


def _iter_block_items(
    parent,
    document_type,
    paragraph_cls,
    table_cls,
    qn,
) -> Iterator:
    if isinstance(parent, document_type):
        parent_elm = parent.element.body
    else:
        raise ValueError("仅支持 Document 根节点遍历")

    for child in parent_elm.iterchildren():
        if child.tag == qn("w:p"):
            yield paragraph_cls(child, parent)
        elif child.tag == qn("w:tbl"):
            yield table_cls(child, parent)


def _resolve_heading_level(style_name: str | None, text: str) -> int | None:
    normalized = (style_name or "").strip().lower()
    if normalized:
        for key, level in (
            ("heading 1", 1),
            ("heading 2", 2),
            ("heading 3", 3),
            ("heading 4", 4),
            ("heading 5", 5),
            ("heading 6", 6),
            ("标题 1", 1),
            ("标题 2", 2),
            ("标题 3", 3),
            ("标题 4", 4),
            ("标题 5", 5),
            ("标题 6", 6),
            ("标题1", 1),
            ("标题2", 2),
            ("标题3", 3),
            ("标题4", 4),
            ("标题5", 5),
            ("标题6", 6),
        ):
            if key in normalized:
                return level

    if CHAPTER_PATTERN.match(text):
        return 1
    if SECTION_NUMBER_PATTERN.match(text):
        return 3
    return None


def _resolve_list_info(paragraph) -> tuple[int | None, bool]:
    p_pr = paragraph._p.pPr  # noqa: SLF001
    if p_pr is None or p_pr.numPr is None:
        return None, False

    num_pr = p_pr.numPr
    ilvl = num_pr.ilvl
    level = int(ilvl.val) + 1 if ilvl is not None else 1
    return level, True


def _paragraph_has_image(paragraph) -> bool:
    drawings = paragraph._p.xpath(".//w:drawing")  # noqa: SLF001
    return bool(drawings)


def _table_to_markdown(table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""

    header = rows[0]
    body = rows[1:] if len(rows) > 1 else []
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[: len(header)]) + " |")
    return "\n".join(lines)


def _merge_markdown_output(mammoth_markdown: str, structure: DocxStructure) -> str:
    content = mammoth_markdown.strip()
    if not content:
        return _build_markdown_from_structure(structure)

    had_html_tables = bool(HTML_TABLE_PATTERN.search(content))
    content = _replace_html_tables(content, structure.table_markdowns)
    content = _normalize_markdown_headings(content)

    # mammoth 常将表格压成纯文本；此时用 python-docx 按文档顺序重建，避免重复
    if structure.has_tables and not had_html_tables and not _contains_markdown_table(
        content
    ):
        return _build_markdown_from_structure(structure)

    metadata_comment = (
        f"<!-- docx-meta:{json.dumps(structure.to_metadata(), ensure_ascii=False)} -->"
    )
    return f"{metadata_comment}\n\n{content}".strip()


def _replace_html_tables(content: str, table_markdowns: list[str]) -> str:
    if not table_markdowns:
        return _strip_residual_html(content)

    table_index = 0

    def replacer(_match: re.Match[str]) -> str:
        nonlocal table_index
        if table_index < len(table_markdowns):
            replacement = table_markdowns[table_index]
            table_index += 1
            return f"\n\n{replacement}\n\n"
        return ""

    replaced = HTML_TABLE_PATTERN.sub(replacer, content)
    return _strip_residual_html(replaced)


def _strip_residual_html(content: str) -> str:
    cleaned = HTML_TAG_PATTERN.sub("", content)
    return unescape(cleaned)


def _normalize_markdown_headings(content: str) -> str:
    lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if HEADING_LEVEL_PATTERN.match(stripped):
            lines.append(stripped)
            continue
        if CHAPTER_PATTERN.match(stripped):
            lines.append(f"# {stripped}")
            continue
        if SECTION_NUMBER_PATTERN.match(stripped):
            lines.append(f"### {stripped}")
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _contains_markdown_table(content: str) -> bool:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("|") and index + 1 < len(lines):
            if "---" in lines[index + 1]:
                return True
    return False


def _build_markdown_from_structure(structure: DocxStructure) -> str:
    parts: list[str] = []
    for block in structure.blocks:
        if block.kind == "table":
            parts.append(block.text)
            continue

        prefix = "#" * block.heading_level if block.heading_level else ""
        if block.list_level:
            indent = "  " * (block.list_level - 1)
            marker = f"{indent}1. " if block.is_ordered_list else f"{indent}- "
            parts.append(f"{marker}{block.text}")
        elif prefix:
            parts.append(f"{prefix} {block.text}")
        else:
            parts.append(block.text)

    metadata_comment = (
        f"<!-- docx-meta:{json.dumps(structure.to_metadata(), ensure_ascii=False)} -->"
    )
    body = "\n\n".join(part for part in parts if part.strip())
    if not body:
        return ""
    return f"{metadata_comment}\n\n{body}"


def _assess_quality(
    markdown: str,
    structure: DocxStructure,
    warnings: list[str],
) -> str:
    if not markdown.strip():
        return "low"
    if warnings and structure.heading_count == 0 and not structure.has_tables:
        return "low"
    if structure.heading_count >= 2 or structure.has_tables:
        return "high"
    if structure.paragraph_count >= 3:
        return "medium"
    return "medium"
