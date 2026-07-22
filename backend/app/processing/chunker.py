from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

MAX_CLAUSE_CHARS = 1800
FIGURE_CONTEXT_LINES = 6
FALLBACK_PAGE_CHARS = 2400
FALLBACK_PARAGRAPH_CHARS = 1800

CHAPTER_PATTERN = re.compile(r"^第[一二三四五六七八九十百千零\d]+章[：:\s]?(.*)$")
SECTION_PATTERN = re.compile(r"^第[一二三四五六七八九十百千零\d]+节[：:\s]?(.*)$")
CLAUSE_NUMBER_PATTERN = re.compile(r"^(\d+(?:\.\d+)+)\s+(.+)$")
APPENDIX_CLAUSE_PATTERN = re.compile(r"^([A-Za-z](?:\.\d+)+)\s+(.+)$")
APPENDIX_PATTERN = re.compile(r"^附录\s*([A-Za-z0-9]+)[：:\s]?(.*)$")
TABLE_CAPTION_PATTERN = re.compile(r"^表\s*(\d+)[：:\s]?(.*)$")
FIGURE_CAPTION_PATTERN = re.compile(r"^图\s*(\d+)[：:\s]?(.*)$")
TABLE_BLOCK_PATTERN = re.compile(r"^\|.+\|$")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
METADATA_COMMENT_PATTERN = re.compile(r"^<!--\s*docx-meta:[\s\S]*?-->\s*$", re.MULTILINE)
PAGE_COMMENT_PATTERN = re.compile(r"^<!--\s*page:(\d+)\s*-->\s*$")
PDF_META_COMMENT_PATTERN = re.compile(
    r"^<!--\s*pdf-meta:[\s\S]*?-->\s*$", re.MULTILINE
)
PDF_FIGURE_COMMENT_PATTERN = re.compile(
    r"^<!--\s*figures:page-\d+[\s\S]*?-->\s*$", re.MULTILINE
)
PDF_TABLE_COMMENT_PATTERN = re.compile(
    r"^<!--\s*table:page-\d+\s*-->\s*$", re.MULTILINE
)


@dataclass(frozen=True)
class ChunkDraft:
    chunk_index: int
    content: str
    position_label: str | None
    chunk_type: str
    token_count: int
    doc_role: str = "body"
    clause_level: str | None = None
    parent_label: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    table_caption: str | None = None
    figure_caption: str | None = None
    content_json: dict[str, Any] | None = None


@dataclass
class _ChunkContext:
    doc_role: str
    chapter_label: str | None = None
    section_label: str | None = None
    appendix_label: str | None = None
    in_appendix: bool = False
    current_page: int | None = None
    page_start: int | None = None
    saw_structure: bool = False


@dataclass
class _ClauseBuffer:
    lines: list[str] = field(default_factory=list)
    position_label: str | None = None
    clause_level: str | None = None
    chunk_type: str = "clause"
    page_start: int | None = None
    page_end: int | None = None

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()

    @property
    def char_count(self) -> int:
        return len(self.text)


def chunk_attachment_text(
    text: str,
    *,
    doc_role: str = "body",
    parse_quality: str | None = None,
) -> list[ChunkDraft]:
    normalized = _normalize_source_text(text)
    if not normalized:
        return []

    lines = normalized.split("\n")
    ctx = _ChunkContext(doc_role=doc_role)
    chunks: list[ChunkDraft] = []
    clause_buffer = _ClauseBuffer()
    chunk_index = 0

    def emit(draft: ChunkDraft) -> None:
        nonlocal chunk_index
        chunks.append(
            ChunkDraft(
                chunk_index=chunk_index,
                content=draft.content,
                position_label=draft.position_label,
                chunk_type=draft.chunk_type,
                token_count=draft.token_count,
                doc_role=doc_role,
                clause_level=draft.clause_level,
                parent_label=draft.parent_label or _resolve_parent_label(ctx),
                page_start=draft.page_start,
                page_end=draft.page_end,
                table_caption=draft.table_caption,
                figure_caption=draft.figure_caption,
                content_json=draft.content_json,
            )
        )
        chunk_index += 1

    def flush_clause() -> None:
        nonlocal clause_buffer
        body = clause_buffer.text
        if not body:
            clause_buffer = _ClauseBuffer()
            return

        if clause_buffer.char_count > MAX_CLAUSE_CHARS and clause_buffer.chunk_type == "clause":
            _flush_long_clause(clause_buffer, ctx, emit)
            clause_buffer = _ClauseBuffer()
            return

        emit(
            ChunkDraft(
                chunk_index=0,
                content=body,
                position_label=clause_buffer.position_label,
                chunk_type=clause_buffer.chunk_type,
                token_count=_estimate_tokens(body),
                clause_level=clause_buffer.clause_level,
                parent_label=_resolve_parent_label(ctx),
                page_start=clause_buffer.page_start,
                page_end=clause_buffer.page_end or ctx.current_page,
            )
        )
        clause_buffer = _ClauseBuffer()

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()

        page_match = PAGE_COMMENT_PATTERN.match(line)
        if page_match:
            ctx.current_page = int(page_match.group(1))
            if clause_buffer.lines and clause_buffer.page_start is None:
                clause_buffer.page_start = ctx.current_page
            index += 1
            continue

        if not line:
            if clause_buffer.lines:
                clause_buffer.lines.append("")
            index += 1
            continue

        if TABLE_BLOCK_PATTERN.match(line) or line.startswith("| ---"):
            pending_caption = _find_recent_table_caption(clause_buffer, chunks)
            section_label = _section_context_for_table(ctx, clause_buffer, chunks)
            flush_clause()
            table_lines = [raw_line.rstrip()]
            index += 1
            while index < len(lines):
                candidate = lines[index].strip()
                if TABLE_BLOCK_PATTERN.match(candidate) or candidate.startswith("| ---"):
                    table_lines.append(lines[index].rstrip())
                    index += 1
                    continue
                break
            table_md = "\n".join(table_lines).strip()
            caption = pending_caption or _find_recent_table_caption(clause_buffer, chunks)
            table_content = _prepend_table_context(section_label, caption, table_md)
            emit(
                ChunkDraft(
                    chunk_index=0,
                    content=table_content,
                    position_label=caption or section_label,
                    chunk_type="table",
                    token_count=_estimate_tokens(table_content),
                    clause_level="clause",
                    parent_label=_resolve_parent_label(ctx),
                    page_start=ctx.current_page,
                    page_end=ctx.current_page,
                    table_caption=caption,
                    content_json=_markdown_table_to_json(table_md),
                )
            )
            ctx.saw_structure = True
            continue

        structure = _parse_structure_line(line)
        if structure is not None:
            flush_clause()
            _apply_structure(ctx, structure)

            if structure.kind == "figure":
                figure_lines, index = _collect_figure_block(lines, index, line)
                caption = structure.label
                content = "\n".join(figure_lines).strip()
                emit(
                    ChunkDraft(
                        chunk_index=0,
                        content=content,
                        position_label=caption,
                        chunk_type="figure",
                        token_count=_estimate_tokens(content),
                        clause_level="clause",
                        parent_label=_resolve_parent_label(ctx),
                        page_start=ctx.current_page,
                        page_end=ctx.current_page,
                        figure_caption=caption,
                    )
                )
                ctx.saw_structure = True
                continue

            if structure.kind == "table_caption":
                clause_buffer = _ClauseBuffer(
                    lines=[line],
                    position_label=structure.label,
                    clause_level=structure.clause_level,
                    chunk_type="clause",
                    page_start=ctx.current_page,
                    page_end=ctx.current_page,
                )
                ctx.saw_structure = True
                index += 1
                continue

            clause_buffer = _ClauseBuffer(
                lines=[line],
                position_label=structure.label,
                clause_level=structure.clause_level,
                chunk_type=structure.chunk_type,
                page_start=ctx.current_page,
                page_end=ctx.current_page,
            )
            ctx.saw_structure = True
            index += 1
            continue

        if clause_buffer.char_count >= MAX_CLAUSE_CHARS and clause_buffer.lines:
            flush_clause()

        if not clause_buffer.lines:
            clause_buffer = _ClauseBuffer(
                page_start=ctx.current_page,
                page_end=ctx.current_page,
                chunk_type="appendix" if ctx.in_appendix else "clause",
            )

        clause_buffer.lines.append(line)
        clause_buffer.page_end = ctx.current_page
        index += 1

    flush_clause()

    if not chunks:
        return _fallback_chunks(normalized, doc_role=doc_role, parse_quality=parse_quality)

    if not ctx.saw_structure and parse_quality in {"medium", "low", "ocr"}:
        return _fallback_chunks(normalized, doc_role=doc_role, parse_quality=parse_quality)

    if not ctx.saw_structure and len(chunks) == 1 and chunks[0].chunk_type == "clause":
        return _fallback_chunks(normalized, doc_role=doc_role, parse_quality=parse_quality)

    return chunks


def _normalize_source_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").strip()
    normalized = METADATA_COMMENT_PATTERN.sub("", normalized)
    normalized = PDF_META_COMMENT_PATTERN.sub("", normalized)
    normalized = PDF_FIGURE_COMMENT_PATTERN.sub("", normalized)
    normalized = PDF_TABLE_COMMENT_PATTERN.sub("", normalized)
    return normalized.strip()


@dataclass(frozen=True)
class _StructureLine:
    kind: str
    label: str
    clause_level: str | None
    chunk_type: str


def _parse_structure_line(line: str) -> _StructureLine | None:
    heading = HEADING_PATTERN.match(line)
    if heading:
        title = heading.group(2).strip()
        return _classify_heading(title, raw=line)

    for pattern, kind in (
        (CHAPTER_PATTERN, "chapter"),
        (SECTION_PATTERN, "section"),
        (APPENDIX_PATTERN, "appendix"),
        (CLAUSE_NUMBER_PATTERN, "clause"),
        (APPENDIX_CLAUSE_PATTERN, "appendix_clause"),
        (TABLE_CAPTION_PATTERN, "table_caption"),
        (FIGURE_CAPTION_PATTERN, "figure"),
    ):
        match = pattern.match(line)
        if not match:
            continue
        if kind == "appendix_clause":
            label = match.group(1)
            return _StructureLine(
                kind="clause",
                label=label,
                clause_level="clause",
                chunk_type="appendix",
            )
        if kind == "appendix":
            label = f"附录{match.group(1)}"
            return _StructureLine(
                kind="appendix",
                label=label,
                clause_level="appendix",
                chunk_type="appendix",
            )
        if kind == "clause":
            number = match.group(1)
            return _StructureLine(
                kind="clause",
                label=number,
                clause_level=_clause_level_from_number(number),
                chunk_type="appendix" if number.startswith("A.") else "clause",
            )
        if kind == "table_caption":
            caption = f"表{match.group(1)}"
            if match.group(2):
                caption += f" {match.group(2).strip()}"
            return _StructureLine(
                kind="table_caption",
                label=caption,
                clause_level="clause",
                chunk_type="clause",
            )
        if kind == "figure":
            caption = f"图{match.group(1)}"
            if match.group(2):
                caption += f" {match.group(2).strip()}"
            return _StructureLine(
                kind="figure",
                label=caption,
                clause_level="clause",
                chunk_type="figure",
            )
        if kind == "chapter":
            return _StructureLine(
                kind="chapter",
                label=line[:64],
                clause_level="chapter",
                chunk_type="clause",
            )
        if kind == "section":
            return _StructureLine(
                kind="section",
                label=line[:64],
                clause_level="section",
                chunk_type="clause",
            )
    return None


def _classify_heading(title: str, *, raw: str) -> _StructureLine:
    if CHAPTER_PATTERN.match(title) or title.startswith("第") and "章" in title:
        return _StructureLine(
            kind="chapter",
            label=title[:64],
            clause_level="chapter",
            chunk_type="clause",
        )
    if SECTION_PATTERN.match(title) or title.startswith("第") and "节" in title:
        return _StructureLine(
            kind="section",
            label=title[:64],
            clause_level="section",
            chunk_type="clause",
        )
    appendix = APPENDIX_PATTERN.match(title)
    if appendix:
        return _StructureLine(
            kind="appendix",
            label=f"附录{appendix.group(1)}",
            clause_level="appendix",
            chunk_type="appendix",
        )
    table = TABLE_CAPTION_PATTERN.match(title)
    if table:
        caption = f"表{table.group(1)}"
        if table.group(2):
            caption += f" {table.group(2).strip()}"
        return _StructureLine(
            kind="table_caption",
            label=caption,
            clause_level="clause",
            chunk_type="clause",
        )
    figure = FIGURE_CAPTION_PATTERN.match(title)
    if figure:
        caption = f"图{figure.group(1)}"
        if figure.group(2):
            caption += f" {figure.group(2).strip()}"
        return _StructureLine(
            kind="figure",
            label=caption,
            clause_level="clause",
            chunk_type="figure",
        )
    clause = CLAUSE_NUMBER_PATTERN.match(title)
    if clause:
        number = clause.group(1)
        return _StructureLine(
            kind="clause",
            label=number,
            clause_level=_clause_level_from_number(number),
            chunk_type="clause",
        )
    appendix_clause = APPENDIX_CLAUSE_PATTERN.match(title)
    if appendix_clause:
        return _StructureLine(
            kind="clause",
            label=appendix_clause.group(1),
            clause_level="clause",
            chunk_type="appendix",
        )
    return _StructureLine(
        kind="heading",
        label=title[:64],
        clause_level="section",
        chunk_type="clause",
    )


def _apply_structure(ctx: _ChunkContext, structure: _StructureLine) -> None:
    if structure.kind == "chapter":
        ctx.chapter_label = structure.label
        ctx.section_label = None
        ctx.in_appendix = False
        ctx.appendix_label = None
        return
    if structure.kind == "section":
        ctx.section_label = structure.label
        ctx.in_appendix = False
        return
    if structure.kind == "appendix":
        ctx.in_appendix = True
        ctx.appendix_label = structure.label
        ctx.section_label = None
        return


def _resolve_parent_label(ctx: _ChunkContext) -> str | None:
    if ctx.in_appendix and ctx.appendix_label:
        return ctx.appendix_label
    if ctx.section_label:
        return ctx.section_label
    if ctx.chapter_label:
        return ctx.chapter_label
    return None


def _section_context_for_table(
    ctx: _ChunkContext,
    clause_buffer: _ClauseBuffer,
    chunks: list[ChunkDraft],
) -> str | None:
    if clause_buffer.position_label and not clause_buffer.position_label.startswith("表"):
        return clause_buffer.position_label
    if ctx.section_label:
        return ctx.section_label
    if ctx.chapter_label:
        return ctx.chapter_label
    if ctx.appendix_label:
        return ctx.appendix_label
    for item in reversed(chunks[-3:]):
        if item.chunk_type != "clause" or not item.position_label:
            continue
        if item.position_label.startswith("表"):
            continue
        return item.position_label
    return None


def _prepend_table_context(
    section_label: str | None,
    caption: str | None,
    table_md: str,
) -> str:
    parts: list[str] = []
    if section_label:
        heading = section_label.strip()
        if not heading.startswith("#"):
            heading = f"# {heading}"
        parts.append(heading)
    if caption and caption != section_label:
        parts.append(caption)
    parts.append(table_md)
    return "\n\n".join(parts)


def _clause_level_from_number(number: str) -> str:
    parts = number.split(".")
    if len(parts) <= 1:
        return "section"
    if len(parts) == 2:
        return "section"
    return "clause"


def _collect_figure_block(
    lines: list[str],
    start_index: int,
    heading_line: str,
) -> tuple[list[str], int]:
    collected = [heading_line.strip()]
    index = start_index + 1
    context_lines = 0
    while index < len(lines) and context_lines < FIGURE_CONTEXT_LINES:
        candidate = lines[index].strip()
        if not candidate:
            if collected and collected[-1] != "":
                collected.append("")
            index += 1
            continue
        if PAGE_COMMENT_PATTERN.match(candidate):
            break
        if _parse_structure_line(candidate) is not None:
            break
        if TABLE_BLOCK_PATTERN.match(candidate):
            break
        collected.append(lines[index].rstrip())
        if candidate and not candidate.startswith("<!--"):
            context_lines += 1
        index += 1
    return collected, index


def _flush_long_clause(
    buffer: _ClauseBuffer,
    ctx: _ChunkContext,
    emit,
) -> None:
    paragraphs: list[str] = []
    current: list[str] = []
    for line in buffer.lines:
        if not line.strip():
            if current:
                paragraphs.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append("\n".join(current).strip())

    if not paragraphs:
        return

    if len(paragraphs) == 1 and len(paragraphs[0]) > MAX_CLAUSE_CHARS:
        _emit_fixed_size_parts(paragraphs[0], buffer=buffer, ctx=ctx, emit=emit)
        return

    rolling: list[str] = []
    rolling_chars = 0
    for paragraph in paragraphs:
        if rolling_chars + len(paragraph) > MAX_CLAUSE_CHARS and rolling:
            content = "\n\n".join(rolling).strip()
            emit(
                ChunkDraft(
                    chunk_index=0,
                    content=content,
                    position_label=buffer.position_label,
                    chunk_type=buffer.chunk_type,
                    token_count=_estimate_tokens(content),
                    clause_level=buffer.clause_level,
                    parent_label=_resolve_parent_label(ctx),
                    page_start=buffer.page_start,
                    page_end=buffer.page_end or ctx.current_page,
                )
            )
            rolling = []
            rolling_chars = 0
        rolling.append(paragraph)
        rolling_chars += len(paragraph)

    if rolling:
        content = "\n\n".join(rolling).strip()
        emit(
            ChunkDraft(
                chunk_index=0,
                content=content,
                position_label=buffer.position_label,
                chunk_type=buffer.chunk_type,
                token_count=_estimate_tokens(content),
                clause_level=buffer.clause_level,
                parent_label=_resolve_parent_label(ctx),
                page_start=buffer.page_start,
                page_end=buffer.page_end,
            )
        )


def _emit_fixed_size_parts(
    text: str,
    *,
    buffer: _ClauseBuffer,
    ctx: _ChunkContext,
    emit,
) -> None:
    start = 0
    while start < len(text):
        end = min(start + MAX_CLAUSE_CHARS, len(text))
        part = text[start:end].strip()
        if part:
            emit(
                ChunkDraft(
                    chunk_index=0,
                    content=part,
                    position_label=buffer.position_label,
                    chunk_type=buffer.chunk_type,
                    token_count=_estimate_tokens(part),
                    clause_level=buffer.clause_level,
                    parent_label=_resolve_parent_label(ctx),
                    page_start=buffer.page_start,
                    page_end=buffer.page_end or ctx.current_page,
                )
            )
        start = end


def _find_recent_table_caption(
    clause_buffer: _ClauseBuffer,
    chunks: list[ChunkDraft],
) -> str | None:
    if clause_buffer.position_label and clause_buffer.position_label.startswith("表"):
        return clause_buffer.position_label
    for item in reversed(chunks[-3:]):
        if item.table_caption:
            return item.table_caption
        if item.position_label and item.position_label.startswith("表"):
            return item.position_label
    return None


def _markdown_table_to_json(table_md: str) -> dict[str, Any] | None:
    rows: list[list[str]] = []
    for line in table_md.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if set(stripped.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells:
            rows.append(cells)
    if not rows:
        return None
    headers = rows[0]
    body = rows[1:] if len(rows) > 1 else []
    return {"headers": headers, "rows": body}


def _fallback_chunks(
    text: str,
    *,
    doc_role: str,
    parse_quality: str | None,
) -> list[ChunkDraft]:
    page_blocks = _split_by_page_markers(text)
    if len(page_blocks) > 1:
        return _emit_page_fallback(page_blocks, doc_role=doc_role)

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return [
            ChunkDraft(
                chunk_index=0,
                content=text[:8000],
                position_label=None,
                chunk_type="preamble" if doc_role == "body" else "clause",
                token_count=_estimate_tokens(text),
                doc_role=doc_role,
                clause_level=None,
            )
        ]

    chunks: list[ChunkDraft] = []
    buffer: list[str] = []
    buffer_chars = 0
    chunk_index = 0
    limit = FALLBACK_PARAGRAPH_CHARS if parse_quality in {"medium", "low", "ocr"} else MAX_CLAUSE_CHARS

    def flush() -> None:
        nonlocal chunk_index, buffer, buffer_chars
        body = "\n\n".join(buffer).strip()
        if not body:
            buffer = []
            buffer_chars = 0
            return
        chunks.append(
            ChunkDraft(
                chunk_index=chunk_index,
                content=body,
                position_label=None,
                chunk_type="preamble" if not chunks and doc_role == "body" else "clause",
                token_count=_estimate_tokens(body),
                doc_role=doc_role,
            )
        )
        chunk_index += 1
        buffer = []
        buffer_chars = 0

    for paragraph in paragraphs:
        if buffer_chars + len(paragraph) > limit and buffer:
            flush()
        buffer.append(paragraph)
        buffer_chars += len(paragraph)
    flush()
    return chunks


def _split_by_page_markers(text: str) -> list[tuple[int | None, str]]:
    blocks: list[tuple[int | None, str]] = []
    current_page: int | None = None
    current_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        page_match = PAGE_COMMENT_PATTERN.match(line)
        if page_match:
            if current_lines:
                blocks.append((current_page, "\n".join(current_lines).strip()))
                current_lines = []
            current_page = int(page_match.group(1))
            continue
        current_lines.append(raw_line)
    if current_lines:
        blocks.append((current_page, "\n".join(current_lines).strip()))
    return [item for item in blocks if item[1]]


def _emit_page_fallback(
    page_blocks: list[tuple[int | None, str]],
    *,
    doc_role: str,
) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    chunk_index = 0
    for page_no, body in page_blocks:
        if not body:
            continue
        if len(body) <= FALLBACK_PAGE_CHARS:
            chunks.append(
                ChunkDraft(
                    chunk_index=chunk_index,
                    content=body,
                    position_label=f"page-{page_no}" if page_no else None,
                    chunk_type="clause",
                    token_count=_estimate_tokens(body),
                    doc_role=doc_role,
                    page_start=page_no,
                    page_end=page_no,
                )
            )
            chunk_index += 1
            continue

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
        rolling: list[str] = []
        rolling_chars = 0
        for paragraph in paragraphs:
            if rolling_chars + len(paragraph) > FALLBACK_PAGE_CHARS and rolling:
                content = "\n\n".join(rolling).strip()
                chunks.append(
                    ChunkDraft(
                        chunk_index=chunk_index,
                        content=content,
                        position_label=f"page-{page_no}" if page_no else None,
                        chunk_type="clause",
                        token_count=_estimate_tokens(content),
                        doc_role=doc_role,
                        page_start=page_no,
                        page_end=page_no,
                    )
                )
                chunk_index += 1
                rolling = []
                rolling_chars = 0
            rolling.append(paragraph)
            rolling_chars += len(paragraph)
        if rolling:
            content = "\n\n".join(rolling).strip()
            chunks.append(
                ChunkDraft(
                    chunk_index=chunk_index,
                    content=content,
                    position_label=f"page-{page_no}" if page_no else None,
                    chunk_type="clause",
                    token_count=_estimate_tokens(content),
                    doc_role=doc_role,
                    page_start=page_no,
                    page_end=page_no,
                )
            )
            chunk_index += 1
    return chunks


def _estimate_tokens(text: str) -> int:
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    other = len(text) - chinese
    return chinese + max(1, other // 4)
