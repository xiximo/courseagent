"""Report synthesis unit tests."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from app.db.models.llm_config import LlmConfigRecord
from app.review.report_synthesis import ReportSynthesisService
from app.schemas.review import (
    BasicInfoDto,
    ComparisonItemDto,
    DraftAnalysisResultDto,
    TestMethodComparisonDto,
)


def _llm_config() -> LlmConfigRecord:
    return LlmConfigRecord(
        id=1,
        enabled=False,
        provider="doubao",
        model_name="test",
        endpoint_id="",
        api_key="",
        base_url="https://example.com",
        timeout_seconds=60,
        qa_top_k=5,
    )


def _sample_analysis() -> DraftAnalysisResultDto:
    return DraftAnalysisResultDto(
        taskId="analysis-1",
        summary="草案整体尚可，但量化不足。",
        basicInfo=BasicInfoDto(
            standardNo="",
            name="汽车产品玻璃升降器技术条件",
            partName="玻璃升降器",
        ),
        issues=[
            {
                "type": "missing",
                "description": "缺少旋转圈数要求",
                "suggestion": "QC/T 626-2019 第4.6.2条",
            },
            {
                "type": "insufficient",
                "description": "手柄扭矩未量化",
                "suggestion": "建议补充≤1.8N·m",
            },
        ],
        suggestions=["建议补充量化指标", "建议对标先进主机厂耐久性要求"],
        testMethodComparisons=[
            TestMethodComparisonDto(
                draftMethod="耐久性试验",
                draftContent="前门55000次",
                comparisons=[
                    ComparisonItemDto(
                        sourceType="oem",
                        sourceLabel="其他车企",
                        standardNo="—",
                        diff="missing",
                        note="先进主机厂要求更高",
                        inferenceSource="llm",
                    )
                ],
            )
        ],
        analyzedAt="2025-04-05T00:00:00+00:00",
    )


def test_synthesize_with_rules_maps_sections() -> None:
    service = ReportSynthesisService(MagicMock(), _llm_config())
    report = service.synthesize(analysis=_sample_analysis())

    assert report.sourceTaskId == "analysis-1"
    assert report.basicInfo.standardName == "汽车产品玻璃升降器技术条件"
    assert report.basicInfo.partName == "玻璃升降器"
    assert any("旋转圈数" in row.description for row in report.missingFeatures)
    assert any(row.featureElement == "手柄扭矩未量化" for row in report.improvements)
    assert len(report.summaryPoints) >= 1
    assert report.finalConclusion
    assert report.disclaimer


def test_synthesize_with_llm_uses_post_process() -> None:
    config = _llm_config()
    config.enabled = True
    config.api_key = "key"
    config.endpoint_id = "ep"

    llm_json = """
    {
      "basicInfo": {
        "standardName": "汽车产品玻璃升降器技术条件",
        "standardNo": "无（未提供）",
        "partName": "玻璃升降器",
        "reviewDate": "2025-04-05"
      },
      "missingFeatures": [
        {
          "description": "缺少旋转圈数要求",
          "relatedStandards": "QC/T 626-2019",
          "citationIds": []
        }
      ],
      "improvements": [
        {
          "featureElement": "手柄扭矩",
          "suggestedContent": "建议≤1.8N·m",
          "suggestedMethod": "参考QC/T 626试验方法",
          "referenceStandards": "QC/T 626-2019",
          "citationIds": []
        }
      ],
      "summaryPoints": [
        {"order": 1, "title": "量化不足", "content": "建议补充量化指标"}
      ],
      "finalConclusion": "建议修订后发布。"
    }
    """

    service = ReportSynthesisService(MagicMock(), config)
    with patch(
        "app.review.report_synthesis.chat_completion",
        return_value=llm_json,
    ):
        report = service.synthesize(analysis=_sample_analysis())

    assert report.basicInfo.standardNo == "无（未提供）"
    assert report.missingFeatures[0].description == "缺少旋转圈数要求"
    assert report.improvements[0].featureElement == "手柄扭矩"
    assert report.summaryPoints[0].title == "量化不足"
    assert report.finalConclusion == "建议修订后发布。"
