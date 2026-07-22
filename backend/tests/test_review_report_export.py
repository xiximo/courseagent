"""Review report export unit tests."""

from __future__ import annotations

from zipfile import ZipFile
from io import BytesIO

from app.review.export.service import build_export_filename, export_review_report
from app.schemas.review_report import (
    ImprovementRowDto,
    MissingFeatureRowDto,
    ReviewReportBasicInfoDto,
    ReviewReportDto,
    SummaryPointDto,
)


def _sample_report() -> ReviewReportDto:
    return ReviewReportDto(
        taskId="report-1",
        sourceTaskId="analysis-1",
        basicInfo=ReviewReportBasicInfoDto(
            standardName="汽车用密封条技术条件",
            standardNo="Q/TX 001-2026",
            partName="密封条",
            reviewDate="2026-07-10",
        ),
        missingFeatures=[
            MissingFeatureRowDto(
                description="缺少实施日期",
                relatedStandards="企业标准编写规范",
            )
        ],
        improvements=[
            ImprovementRowDto(
                featureElement="邵氏硬度",
                suggestedContent="建议复核指标范围",
                suggestedMethod="按 GB/T 531 试验",
                referenceStandards="QC/T 6789-2019",
            )
        ],
        summaryPoints=[
            SummaryPointDto(order=1, title="基础信息", content="建议补充实施日期")
        ],
        finalConclusion="建议修订后再次评审。",
        generatedAt="2026-07-10T00:00:00+00:00",
    )


def test_build_export_filename() -> None:
    filename = build_export_filename(_sample_report(), "docx")
    assert filename.endswith(".docx")
    assert filename.startswith("AI智审官_")
    assert "2026-07-10" in filename


def test_export_docx_produces_valid_zip() -> None:
    content, media_type, filename = export_review_report(_sample_report(), "docx")
    assert media_type.endswith("wordprocessingml.document")
    assert filename.endswith(".docx")
    assert content[:2] == b"PK"
    with ZipFile(BytesIO(content)) as archive:
        names = archive.namelist()
    assert "word/document.xml" in names


def test_export_pptx_produces_valid_zip() -> None:
    content, media_type, filename = export_review_report(_sample_report(), "pptx")
    assert media_type.endswith("presentationml.presentation")
    assert filename.endswith(".pptx")
    assert content[:2] == b"PK"
    with ZipFile(BytesIO(content)) as archive:
        names = archive.namelist()
    assert "ppt/presentation.xml" in names
