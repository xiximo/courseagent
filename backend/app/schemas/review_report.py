"""AI智审官评审报告数据模型，对齐《AI智审官模板.md》章节结构。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.qa import CitationDto
from app.schemas.review import DraftAnalysisResultDto

REVIEW_REPORT_TITLE = "AI智审官——企业标准专业性评审报告"
REVIEW_REPORT_DISCLAIMER = "建议仅供审核参考，最终结论以人工审核为准"


class ReviewReportBasicInfoDto(BaseModel):
    """报告「1. 基本信息」区块。"""

    standardName: str = ""
    standardNo: str = ""
    partName: str = ""
    reviewDate: str = ""


class MissingFeatureRowDto(BaseModel):
    """报告「缺失特性结论」表格行。"""

    description: str = Field(description="缺失特性说明")
    relatedStandards: str = Field(
        default="",
        description="涉及标准，可含标准号、名称与条款位置",
    )
    citationIds: list[str] = Field(
        default_factory=list,
        description="关联 citations 中的 chunkId 或标准标识，用于追溯依据",
    )


class ImprovementRowDto(BaseModel):
    """报告「需提升结论」表格行。"""

    featureElement: str = Field(default="", description="特性要素")
    suggestedContent: str = Field(default="", description="建议内容")
    suggestedMethod: str = Field(default="", description="建议方法")
    referenceStandards: str = Field(
        default="",
        description="参考标准，可含标准号、名称与条款位置",
    )
    citationIds: list[str] = Field(default_factory=list)


class SummaryPointDto(BaseModel):
    """报告「评审总结建议」分条。"""

    order: int = Field(ge=1, description="条目序号，从 1 开始")
    title: str = Field(default="", description="小标题，如「量化缺失问题突出」")
    content: str = Field(default="", description="具体说明与建议")


class ReviewReportDto(BaseModel):
    """AI智审官完整评审报告，供页面预览与 Word/PPT 导出共用。"""

    taskId: str = Field(description="报告任务 ID，可与分析 taskId 相同或独立生成")
    sourceTaskId: str = Field(
        default="",
        description="来源草案分析 taskId（DraftAnalysisResult.taskId）",
    )
    title: str = REVIEW_REPORT_TITLE
    basicInfo: ReviewReportBasicInfoDto = Field(default_factory=ReviewReportBasicInfoDto)
    missingFeatures: list[MissingFeatureRowDto] = Field(default_factory=list)
    improvements: list[ImprovementRowDto] = Field(default_factory=list)
    summaryPoints: list[SummaryPointDto] = Field(default_factory=list)
    finalConclusion: str = Field(default="", description="最终结论段落")
    disclaimer: str = REVIEW_REPORT_DISCLAIMER
    citations: list[CitationDto] = Field(default_factory=list)
    generatedAt: str = ""


class GenerateReportBody(BaseModel):
    """基于已有分析结果合成评审报告。"""

    analysis: DraftAnalysisResultDto
    draftExcerpt: str = ""
    parseNote: str = ""


class ExportReportBody(BaseModel):
    """导出评审报告。"""

    report: ReviewReportDto
