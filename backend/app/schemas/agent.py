from typing import Literal

from pydantic import BaseModel, Field


class AgentOverviewToolUsageDto(BaseModel):
    toolId: str
    toolName: str
    calls: int
    avgLatencyMs: int
    errorRate: float


class AgentOverviewProfileHealthDto(BaseModel):
    profileId: str
    name: str
    enabled: bool
    sessionsToday: int
    entryPoints: list[str] = Field(default_factory=list)


class AgentOverviewTrendPointDto(BaseModel):
    label: str
    value: int


class AgentOverviewKnowledgeStatsDto(BaseModel):
    batchNo: str
    standardCount: int
    attachmentCount: int
    indexedCount: int
    lastSyncAt: str
    syncStatus: Literal["healthy", "stale", "syncing"]


class AgentOverviewDto(BaseModel):
    activeSessions: int
    toolCallsToday: int
    avgLatencyMs: int
    citationGateBlockRate: float
    modelVersion: str
    knowledgeBaseBatch: str
    updatedAt: str
    sessionsToday: int | None = None
    qaAnswersToday: int | None = None
    reviewTasksToday: int | None = None
    errorRateToday: float | None = None
    enabledProfiles: int | None = None
    enabledTools: int | None = None
    activeSkills: int | None = None
    toolUsageTop: list[AgentOverviewToolUsageDto] = Field(default_factory=list)
    profileHealth: list[AgentOverviewProfileHealthDto] = Field(default_factory=list)
    knowledgeStats: AgentOverviewKnowledgeStatsDto | None = None
    toolCallsTrend: list[AgentOverviewTrendPointDto] = Field(default_factory=list)
    latencyTrend: list[AgentOverviewTrendPointDto] = Field(default_factory=list)
