from pydantic import BaseModel, Field


class OrchestrationConfigDto(BaseModel):
    maxIterations: int = Field(ge=1, le=20, default=5)
    turnTimeoutSeconds: int = Field(ge=5, le=120, default=10)
    parallelTools: bool = True
    citationGateEnabled: bool = True
    noEvidenceTemplate: str = "当前知识库未找到足够依据，建议人工复核"


class UpdateOrchestrationConfigBody(BaseModel):
    maxIterations: int | None = Field(default=None, ge=1, le=20)
    turnTimeoutSeconds: int | None = Field(default=None, ge=5, le=120)
    parallelTools: bool | None = None
    citationGateEnabled: bool | None = None
    noEvidenceTemplate: str | None = None


class ModelRoutingConfigDto(BaseModel):
    defaultModel: str
    fastPathModel: str
    fastPathRules: list[str] = Field(default_factory=list)
    profileOverrides: dict[str, str] = Field(default_factory=dict)


class UpdateModelRoutingConfigBody(BaseModel):
    defaultModel: str | None = None
    fastPathModel: str | None = None
    fastPathRules: list[str] | None = None
    profileOverrides: dict[str, str] | None = None


class AgentSkillVersionDto(BaseModel):
    version: str
    changelog: str
    deployedAt: str
    active: bool


class AgentSkillDto(BaseModel):
    id: str
    name: str
    description: str
    activeVersion: str
    versions: list[AgentSkillVersionDto]


class ActivateSkillBody(BaseModel):
    version: str
