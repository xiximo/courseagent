from pydantic import BaseModel, Field

from app.schemas.qa import CitationDto


class BasicInfoDto(BaseModel):
    standardNo: str = ""
    name: str = ""
    scope: str = ""
    publishDate: str = ""
    effectiveDate: str = ""
    partCode: str = ""
    partName: str = ""
    draftType: str = ""


class ComparisonItemDto(BaseModel):
    sourceType: str
    sourceLabel: str
    standardNo: str
    standardName: str = ""
    matchedClause: str = ""
    diff: str
    note: str = ""
    inferenceSource: str = "none"  # knowledge_base | llm | none
    citations: list[CitationDto] = Field(default_factory=list)


class ElementItemDto(BaseModel):
    category: str
    name: str
    content: str
    position: str = ""
    clauseNo: str = ""
    requirement: str = ""
    unit: str = ""
    comparisons: list[ComparisonItemDto] = Field(default_factory=list)


class TestMethodComparisonDto(BaseModel):
    draftMethod: str
    draftContent: str = ""
    comparisons: list[ComparisonItemDto] = Field(default_factory=list)


class ToolTraceStepDto(BaseModel):
    id: str
    toolName: str
    inputSummary: str
    outputSummary: str
    durationMs: int
    status: str
    citationIds: list[str] = Field(default_factory=list)
    timestamp: str


class DraftAnalysisResultDto(BaseModel):
    taskId: str
    summary: str
    basicInfo: BasicInfoDto
    elements: list[ElementItemDto] = Field(default_factory=list)
    testMethodComparisons: list[TestMethodComparisonDto] = Field(default_factory=list)
    referenceChecks: list[dict] = Field(default_factory=list)
    issues: list[dict] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    citations: list[CitationDto] = Field(default_factory=list)
    thinkingSteps: list[ToolTraceStepDto] = Field(default_factory=list)
    analyzedAt: str


class AnalyzeDraftBody(BaseModel):
    text: str | None = None
    fileName: str | None = None
