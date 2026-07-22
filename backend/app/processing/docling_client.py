"""Docling HTTP Worker 客户端。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class DoclingWorkerFigure:
    file_name: str
    content_base64: str
    page_no: int | None = None
    captions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DoclingWorkerResult:
    markdown: str
    parse_engine: str
    parse_quality: str
    has_tables: bool
    has_figures: bool
    page_count: int | None
    char_count: int
    warnings: list[str] = field(default_factory=list)
    figures: list[DoclingWorkerFigure] = field(default_factory=list)
    elapsed_sec: float = 0.0


class DoclingWorkerError(RuntimeError):
    pass


def is_docling_worker_configured() -> bool:
    settings = get_settings()
    return bool(settings.docling_worker_enabled and settings.docling_worker_url)


def convert_pdf_via_worker(
    payload: bytes,
    *,
    file_name: str = "document.pdf",
    ocr: bool | None = None,
) -> DoclingWorkerResult:
    settings = get_settings()
    if not settings.docling_worker_enabled or not settings.docling_worker_url:
        raise DoclingWorkerError("Docling worker 未启用或未配置 URL")

    base_url = settings.docling_worker_url.rstrip("/")
    use_ocr = settings.docling_worker_ocr if ocr is None else ocr
    headers: dict[str, str] = {}
    if settings.docling_worker_token:
        headers["X-Worker-Token"] = settings.docling_worker_token

    files = {"file": (file_name, payload, "application/pdf")}
    data = {
        "ocr": "true" if use_ocr else "false",
        "describe_figures": "true" if settings.docling_worker_describe_figures else "false",
        "figure_vlm_caption": "false",
    }
    if settings.docling_worker_device:
        data["device"] = settings.docling_worker_device

    try:
        with httpx.Client(
            timeout=settings.docling_worker_timeout_seconds,
            trust_env=False,
        ) as client:
            response = client.post(
                f"{base_url}/v1/convert/pdf",
                files=files,
                data=data,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise DoclingWorkerError(
            f"Docling worker 超时（>{settings.docling_worker_timeout_seconds}s）"
        ) from exc
    except httpx.HTTPError as exc:
        raise DoclingWorkerError(f"Docling worker 连接失败: {exc}") from exc

    if response.status_code >= 400:
        detail = _extract_error_detail(response)
        raise DoclingWorkerError(f"Docling worker 返回错误 ({response.status_code}): {detail}")

    body: dict[str, Any] = response.json()
    markdown = str(body.get("markdown", "")).strip()
    if not markdown:
        raise DoclingWorkerError("Docling worker 返回空内容")

    figures = [
        DoclingWorkerFigure(
            file_name=str(item.get("file_name") or item.get("image_file") or f"fig-{index:03d}.png"),
            content_base64=str(item.get("content_base64") or ""),
            page_no=item.get("page_no"),
            captions=[str(caption) for caption in item.get("captions", [])],
        )
        for index, item in enumerate(body.get("figures", []), start=1)
        if item.get("content_base64")
    ]

    return DoclingWorkerResult(
        markdown=markdown,
        parse_engine=str(body.get("parse_engine", "docling")),
        parse_quality=str(body.get("parse_quality", "medium")),
        has_tables=bool(body.get("has_tables", False)),
        has_figures=bool(body.get("has_figures", False)),
        page_count=body.get("page_count"),
        char_count=int(body.get("char_count", len(markdown))),
        warnings=[str(item) for item in body.get("warnings", [])],
        figures=figures,
        elapsed_sec=float(body.get("elapsed_sec", 0.0)),
    )


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500]
    detail = payload.get("detail", response.text)
    if isinstance(detail, list):
        return "; ".join(str(item) for item in detail)
    return str(detail)
