from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO

# OLE Compound Document (.doc 老格式)
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_MAGIC = b"PK"

# Word 损坏关系：Target="NULL" 或内部书签链接
BROKEN_RELATIONSHIP_PATTERN = re.compile(
    r"<Relationship\b[^>]*\bTarget=\"(?:\.\./)?NULL\"[^>]*/>\s*",
    re.IGNORECASE,
)
BROKEN_BOOKMARK_RELATIONSHIP_PATTERN = re.compile(
    r"<Relationship\b[^>]*\bTarget=\"#[^\"]+\"[^>]*/>\s*",
    re.IGNORECASE,
)


def prepare_docx_payload(payload: bytes, file_name: str = "") -> bytes:
    """下载/解析前统一规范化 DOCX 字节流。"""
    if not payload:
        raise ValueError("附件内容为空，请在同步页重新下载该附件")

    normalized = unwrap_docx_payload(payload, file_name)
    validate_docx_payload(normalized, file_name)
    return repair_docx_archive(normalized)


def unwrap_docx_payload(payload: bytes, file_name: str = "") -> bytes:
    """若 SPRS 返回 zip 压缩包或误存为外层 zip，则解出内部 docx。"""
    if payload[:2] != ZIP_MAGIC:
        return payload

    if _is_docx_archive(payload):
        return payload

    extracted = _extract_docx_from_zip(payload, file_name)
    if extracted:
        return extracted

    return payload


def validate_docx_payload(payload: bytes, file_name: str = "") -> None:
    if payload[:2] == ZIP_MAGIC:
        if not _is_docx_archive(payload):
            raise ValueError(
                "附件为 ZIP 压缩包但不含有效 DOCX 结构，"
                "请确认 SPRS 附件类型或在同步页重新下载"
            )
        return

    if payload[:8] == OLE_MAGIC:
        raise ValueError(
            "附件实际为 DOC 老格式（非 DOCX），"
            "需先通过 LibreOffice 转换为 DOCX 后再解析"
        )

    stripped = payload.lstrip()
    if stripped.startswith((b"{", b"[")):
        try:
            parsed = json.loads(stripped.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            message = parsed.get("message") or parsed.get("msg") or "SPRS 返回错误"
            raise ValueError(f"附件下载内容为 JSON 错误响应：{message}，请重新同步下载")
        raise ValueError("附件内容为 JSON 而非 DOCX，请在同步页重新下载")

    lowered = stripped[:32].lower()
    if lowered.startswith((b"<!doctype", b"<html", b"<head")):
        raise ValueError("附件内容为 HTML 页面而非 DOCX，请检查 SPRS 网关或重新同步")

    preview = payload[:16].hex(" ")
    label = file_name or "附件"
    raise ValueError(
        f"{label} 不是有效的 DOCX 文件（文件头: {preview}），"
        "请在同步页对该标准重新执行附件下载"
    )


def repair_docx_archive(payload: bytes) -> bytes:
    """修复 Word 文档中 Target=NULL 等损坏关系，避免 python-docx / mammoth 报错。"""
    if payload[:2] != ZIP_MAGIC or not _is_docx_archive(payload):
        return payload

    input_buf = BytesIO(payload)
    output_buf = BytesIO()
    changed = False

    with zipfile.ZipFile(input_buf, "r") as zin:
        with zipfile.ZipFile(output_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith(".rels"):
                    text = data.decode("utf-8", errors="replace")
                    cleaned = BROKEN_RELATIONSHIP_PATTERN.sub("", text)
                    cleaned = BROKEN_BOOKMARK_RELATIONSHIP_PATTERN.sub("", cleaned)
                    if cleaned != text:
                        changed = True
                        data = cleaned.encode("utf-8")
                zout.writestr(item, data)

    return output_buf.getvalue() if changed else payload


def is_repairable_docx_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    markers = (
        "null",
        "no item named",
        "relationship",
        "not found in the archive",
        "bad zip file",
    )
    return any(marker in message for marker in markers)


def friendly_docx_error(exc: BaseException, file_name: str = "") -> ValueError:
    message = str(exc)
    label = file_name or "DOCX 附件"

    if "not a zip file" in message.lower() or "bad zip file" in message.lower():
        return ValueError(
            f"{label} 不是有效的 DOCX/ZIP 文件，可能下载时内容已损坏，"
            "请在同步页重新下载后再试"
        )
    if "null" in message.lower():
        return ValueError(
            f"{label} 含有损坏的 Word 内部链接（NULL 关系），"
            "已尝试自动修复但仍失败，请用 Word 重新保存后再同步"
        )
    return ValueError(f"DOCX 解析失败: {message}")


def _is_docx_archive(payload: bytes) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(payload), "r") as zf:
            return "[Content_Types].xml" in zf.namelist()
    except zipfile.BadZipFile:
        return False


def _extract_docx_from_zip(payload: bytes, file_name: str) -> bytes | None:
    try:
        with zipfile.ZipFile(BytesIO(payload), "r") as zf:
            docx_entries = [
                name
                for name in zf.namelist()
                if name.lower().endswith(".docx") and not name.endswith("/")
            ]
            if docx_entries:
                preferred = _pick_docx_entry(docx_entries, file_name)
                inner = zf.read(preferred)
                if inner[:2] == ZIP_MAGIC and _is_docx_archive(inner):
                    return inner

            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                inner = zf.read(name)
                if inner[:2] == ZIP_MAGIC and _is_docx_archive(inner):
                    return inner
    except zipfile.BadZipFile:
        return None
    return None


def _pick_docx_entry(entries: list[str], file_name: str) -> str:
    if not file_name:
        return entries[0]

    target = file_name.lower().replace("\\", "/").split("/")[-1]
    for entry in entries:
        if entry.lower().replace("\\", "/").split("/")[-1] == target:
            return entry
    for entry in entries:
        if target in entry.lower():
            return entry
    return entries[0]
