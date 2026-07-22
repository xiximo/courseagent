"""抽取图片资产：对象存储 + Markdown 链接改写。"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.storage.base import ObjectStorage

FIGURE_OBJECT_PREFIX = "extracted"
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


@dataclass(frozen=True)
class FigureAssetInput:
    file_name: str
    content_base64: str
    page_no: int | None = None
    captions: list[str] | None = None


@dataclass(frozen=True)
class FigureAssetRecord:
    file_name: str
    storage_key: str
    page_no: int | None
    captions: list[str]
    preview_url: str


def build_extracted_assets_prefix(attachment_id: UUID) -> str:
    return f"{FIGURE_OBJECT_PREFIX}/{attachment_id}/figures"


def build_asset_preview_path(attachment_id: UUID, file_name: str) -> str:
    safe_name = file_name.replace("\\", "_").replace("/", "_").strip() or "figure.png"
    return f"/api/v1/qibiao/processing/attachments/{attachment_id}/extracted-assets/{safe_name}"


def persist_figure_assets(
    storage: ObjectStorage,
    attachment_id: UUID,
    markdown: str,
    figures: list[FigureAssetInput],
) -> tuple[str, list[FigureAssetRecord]]:
    if not figures:
        return markdown, []

    prefix = build_extracted_assets_prefix(attachment_id)
    storage.remove_prefix(prefix)

    records: list[FigureAssetRecord] = []
    path_map: dict[str, str] = {}

    for index, figure in enumerate(figures, start=1):
        file_name = figure.file_name.strip() or f"fig-{index:03d}.png"
        if not file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            file_name = f"{file_name}.png"

        try:
            payload = base64.b64decode(figure.content_base64)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"图片 {file_name} 的 base64 数据无效") from exc
        if not payload:
            continue

        storage_key = f"{prefix}/{file_name}"
        content_type = _guess_image_content_type(file_name)
        storage.put_bytes(storage_key, payload, content_type=content_type)
        preview_url = build_asset_preview_path(attachment_id, file_name)
        records.append(
            FigureAssetRecord(
                file_name=file_name,
                storage_key=storage_key,
                page_no=figure.page_no,
                captions=list(figure.captions or []),
                preview_url=preview_url,
            )
        )
        path_map[file_name] = preview_url
        path_map[f"figures/{file_name}"] = preview_url

    rewritten = rewrite_markdown_image_links(markdown, path_map)
    return rewritten, records


def _image_target_file_name(target: str) -> str:
    cleaned = target.strip().strip('"').strip("'")
    if cleaned.startswith("file://"):
        cleaned = cleaned[7:]
    return Path(cleaned.replace("\\", "/")).name


def rewrite_markdown_image_links(markdown: str, path_map: dict[str, str]) -> str:
    if not path_map:
        return markdown

    def replace(match: re.Match[str]) -> str:
        alt = match.group(1)
        target = match.group(2).strip()
        if target.startswith("/api/"):
            return match.group(0)

        mapped = path_map.get(target)
        if mapped is None:
            mapped = path_map.get(f"figures/{_image_target_file_name(target)}")
        if mapped is None:
            mapped = path_map.get(_image_target_file_name(target))
        if mapped is None:
            return match.group(0)
        return f"![{alt}]({mapped})"

    return MARKDOWN_IMAGE_PATTERN.sub(replace, markdown)


def remove_figure_assets(storage: ObjectStorage, attachment_id: UUID) -> int:
    return storage.remove_prefix(build_extracted_assets_prefix(attachment_id))


def get_figure_asset_bytes(
    storage: ObjectStorage,
    attachment_id: UUID,
    file_name: str,
) -> tuple[bytes, str]:
    safe_name = file_name.replace("\\", "_").replace("/", "_").strip()
    if not safe_name or ".." in safe_name:
        raise ValueError("图片文件名无效")

    storage_key = f"{build_extracted_assets_prefix(attachment_id)}/{safe_name}"
    if not storage.exists(storage_key):
        raise ValueError("图片不存在")
    payload = storage.get_bytes(storage_key)
    return payload, _guess_image_content_type(safe_name)


def list_figure_assets(
    storage: ObjectStorage,
    attachment_id: UUID,
) -> list[dict[str, Any]]:
    prefix = build_extracted_assets_prefix(attachment_id)
    assets: list[dict[str, Any]] = []
    for object_name in storage.list_keys(prefix):
        file_name = object_name.rsplit("/", 1)[-1]
        if not file_name or file_name == "manifest.json":
            continue
        assets.append(
            {
                "fileName": file_name,
                "previewUrl": build_asset_preview_path(attachment_id, file_name),
                "storageKey": object_name,
            }
        )
    assets.sort(key=lambda item: item["fileName"])
    return assets


def figure_records_to_manifest(records: list[FigureAssetRecord]) -> list[dict[str, Any]]:
    return [
        {
            "fileName": record.file_name,
            "pageNo": record.page_no,
            "captions": record.captions,
            "previewUrl": record.preview_url,
            "storageKey": record.storage_key,
        }
        for record in records
    ]


def _guess_image_content_type(file_name: str) -> str:
    lower = file_name.lower()
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/png"
