"""Review report schema unit tests."""

from __future__ import annotations

import json

from app.schemas.review_report import (
    REVIEW_REPORT_DISCLAIMER,
    REVIEW_REPORT_TITLE,
    ImprovementRowDto,
    MissingFeatureRowDto,
    ReviewReportBasicInfoDto,
    ReviewReportDto,
    SummaryPointDto,
)


def test_review_report_defaults() -> None:
    report = ReviewReportDto(taskId="task-1")
    assert report.title == REVIEW_REPORT_TITLE
    assert report.disclaimer == REVIEW_REPORT_DISCLAIMER
    assert report.basicInfo.standardName == ""
    assert report.missingFeatures == []
    assert report.improvements == []
    assert report.summaryPoints == []


def test_review_report_roundtrip_from_template_sample() -> None:
    payload = {
        "taskId": "task-glass-lifter",
        "sourceTaskId": "analysis-glass-lifter",
        "title": REVIEW_REPORT_TITLE,
        "basicInfo": {
            "standardName": "汽车产品玻璃升降器技术条件",
            "standardNo": "无（未提供）",
            "partName": "玻璃升降器",
            "reviewDate": "2025-04-05",
        },
        "missingFeatures": [
            {
                "description": "手动玻璃升降器的“旋转圈数”特性要求及试验方法",
                "relatedStandards": (
                    "QC/T 626-2019《汽车玻璃升降器》第4.6.2 a）条和第5.6.2 a）条"
                ),
                "citationIds": ["chunk-1"],
            }
        ],
        "improvements": [
            {
                "featureElement": "手柄扭矩",
                "suggestedContent": "量化手柄扭矩限值，建议≤ 1.8N·m",
                "suggestedMethod": "参考QC/T 626-2019中5.6.2 b）的方法",
                "referenceStandards": "QC/T 626-2019《汽车玻璃升降器》第4.6.2条",
                "citationIds": ["chunk-2"],
            }
        ],
        "summaryPoints": [
            {
                "order": 1,
                "title": "量化缺失问题突出",
                "content": "共17项要求未量化，建议逐一补充具体数值。",
            }
        ],
        "finalConclusion": (
            "企标整体水平处于行业中间偏上，但存在量化不足等问题，建议按上述意见修订。"
        ),
        "disclaimer": REVIEW_REPORT_DISCLAIMER,
        "citations": [],
        "generatedAt": "2025-04-05T10:00:00+00:00",
    }

    report = ReviewReportDto.model_validate(payload)
    dumped = json.loads(report.model_dump_json())
    restored = ReviewReportDto.model_validate(dumped)

    assert restored.taskId == "task-glass-lifter"
    assert restored.basicInfo.partName == "玻璃升降器"
    assert len(restored.missingFeatures) == 1
    assert restored.missingFeatures[0].description.startswith("手动玻璃升降器")
    assert restored.improvements[0].featureElement == "手柄扭矩"
    assert restored.summaryPoints[0].order == 1
    assert restored.summaryPoints[0].title == "量化缺失问题突出"


def test_nested_row_models() -> None:
    missing = MissingFeatureRowDto(
        description="功能安全的试验方法或验证流程",
        relatedStandards="GB/T 34590、ISO 26262",
    )
    improvement = ImprovementRowDto(
        featureElement="耐久性（电动）",
        suggestedContent="提升电动升降器耐久性至前门≥60,000次",
        suggestedMethod="按QC/T 626-2019中5.11.1方法",
        referenceStandards="吉利、一汽、东风耐久性试验规范",
    )
    summary = SummaryPointDto(order=2, title="耐久性要求偏低", content="建议提升至≥60,000次")

    assert missing.relatedStandards.startswith("GB/T")
    assert improvement.featureElement == "耐久性（电动）"
    assert summary.order == 2
