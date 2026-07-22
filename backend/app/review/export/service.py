"""评审报告导出工具。"""

from __future__ import annotations

import re
from typing import Literal

from app.review.export.ppt_renderer import render_review_report_pptx
from app.review.export.word_renderer import render_review_report_docx
from app.schemas.review_report import ReviewReportDto

ExportFormat = Literal["docx", "pptx"]

_MEDIA_TYPES: dict[ExportFormat, str] = {
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    "pptx": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ),
}


def export_review_report(report: ReviewReportDto, export_format: ExportFormat) -> tuple[bytes, str, str]:
    """返回 (文件内容, media_type, 文件名)。"""
    if export_format == "docx":
        content = render_review_report_docx(report)
    else:
        content = render_review_report_pptx(report)

    filename = build_export_filename(report, export_format)
    return content, _MEDIA_TYPES[export_format], filename


def build_export_filename(report: ReviewReportDto, export_format: ExportFormat) -> str:
    name = report.basicInfo.standardName.strip() or "评审报告"
    safe_name = re.sub(r'[<>:"/\\|?*\s]+', "_", name).strip("_") or "评审报告"
    review_date = report.basicInfo.reviewDate.strip() or "export"
    safe_date = re.sub(r'[<>:"/\\|?*\s]+', "_", review_date).strip("_") or "export"
    return f"AI智审官_{safe_name}_{safe_date}.{export_format}"
