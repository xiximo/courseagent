from typing import Any, Literal

from pydantic import BaseModel, Field


CourseAgentType = Literal["basic", "workflow", "autonomous"]


class CreateCourseAgentBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    agentType: CourseAgentType = "workflow"


class CourseAgentCitationDto(BaseModel):
    document: str
    chapter: str
    attachmentId: str | None = None
    chunkId: str | None = None


class CourseAgentMessageDto(BaseModel):
    id: str
    role: str
    content: str
    createdAt: str
    citations: list[CourseAgentCitationDto] | None = None
    quickActions: list[str] | None = None


class CourseAgentTraceEventDto(BaseModel):
    id: str
    type: str
    title: str
    detail: str | None = None
    toolName: str | None = None
    status: str | None = None
    createdAt: str


class CourseAgentConstraintsDto(BaseModel):
    city: str | None = None
    date: str | None = None
    format: str | None = None
    goal: str | None = None


class CourseAgentSessionStateDto(BaseModel):
    step: str
    role: str | None = None
    constraints: CourseAgentConstraintsDto = Field(default_factory=CourseAgentConstraintsDto)
    recommendedCourses: list[str] = Field(default_factory=list)
    lockedCourse: str | None = None


class CourseAgentSessionSummaryDto(BaseModel):
    id: str
    agentId: str
    title: str
    createdAt: str
    updatedAt: str


class CourseAgentSessionDto(BaseModel):
    id: str
    agentId: str
    title: str
    messages: list[CourseAgentMessageDto] = Field(default_factory=list)
    state: CourseAgentSessionStateDto
    trace: list[CourseAgentTraceEventDto] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class CourseAgentModelConfigDto(BaseModel):
    provider: str = "doubao"
    stream: bool = False
    modelName: str = ""
    endpointId: str = ""
    apiKey: str = ""
    apiKeyConfigured: bool = False
    baseUrl: str = ""


class CourseAgentModelProfileDto(CourseAgentModelConfigDto):
    id: str
    name: str
    description: str = ""
    isActive: bool = False


class CreateCourseModelBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    provider: str | None = None
    stream: bool | None = None
    modelName: str | None = None
    endpointId: str | None = None
    apiKey: str | None = None
    baseUrl: str | None = None
    setAsActive: bool = False


class UpdateCourseModelBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    provider: str | None = None
    stream: bool | None = None
    modelName: str | None = None
    endpointId: str | None = None
    apiKey: str | None = None
    baseUrl: str | None = None
    setAsActive: bool | None = None


class DeleteCourseModelResultDto(BaseModel):
    message: str = "模型配置已删除"


class CourseAgentStateStepDto(BaseModel):
    id: str
    label: str
    description: str
    enabled: bool = True
    template: str | None = None


class CourseAgentKnowledgeBaseDto(BaseModel):
    id: str
    role: str
    name: str
    materialLabel: str
    standardId: str | None = None
    description: str = ""
    documentCount: int = 0
    chunkCount: int = 0
    lastIndexedAt: str = ""
    status: str = "ready"
    chunkMode: str = "size"
    chunkMaxChars: int = 1800
    chunkOverlapChars: int = 200


class CreateCourseKnowledgeBaseBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    chunkMode: str = "size"
    chunkMaxChars: int = 1800
    chunkOverlapChars: int = 200


class UpdateCourseKnowledgeBaseBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    chunkMode: str | None = None
    chunkMaxChars: int | None = None
    chunkOverlapChars: int | None = None


class DeleteCourseKnowledgeBaseResultDto(BaseModel):
    message: str = "知识库已删除"


class CourseMaterialDocumentDto(BaseModel):
    id: str
    fileName: str
    fileType: str = ""
    fileSize: int | None = None
    parseStatus: str = "pending"
    chunkCount: int = 0
    indexedChunkCount: int = 0
    uploadedAt: str = ""
    failureReason: str | None = None


class CourseMaterialActionResultDto(BaseModel):
    materialLabel: str
    knowledgeBase: CourseAgentKnowledgeBaseDto
    message: str = ""


class CourseAgentEmbedConfigDto(BaseModel):
    embedKey: str
    allowedOrigins: list[str] = Field(default_factory=list)
    theme: str = "light"
    position: str = "bottom-right"


class CourseAgentConversationConfigDto(BaseModel):
    welcomeMessage: str = ""
    systemPrompt: str = ""
    menuButtons: list[str] = Field(default_factory=list)
    resetMessage: str = ""
    emptyInputMessage: str = ""
    tooLongMessage: str = ""
    outOfScopeMessage: str = ""


class CourseAgentReactToolDto(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    kind: str = "kb"
    knowledgeBaseIds: list[str] = Field(default_factory=list)
    enabled: bool = True


class CourseAgentReactConfigDto(BaseModel):
    soul: str = ""
    prohibitionRules: str = ""
    maxToolRounds: int = 4
    tools: list[CourseAgentReactToolDto] = Field(default_factory=list)


class CourseAgentScheduleDto(BaseModel):
    enabled: bool = False
    intervalHours: float = 2
    runMode: Literal["chat", "scheduled"] = "chat"
    visibleInChat: bool = True
    target: Literal["all_users", "members"] = "all_users"
    onlyIfNewMessages: bool = True
    lookbackHours: float = 24
    taskPrompt: str = ""
    lastRunAt: str | None = None
    lastRunNote: str | None = None


class CourseAgentConfigDto(BaseModel):
    agentId: str
    name: str
    description: str = ""
    status: str = "draft"
    agentType: CourseAgentType = "workflow"
    isDefault: bool = False
    temperature: float = 0.3
    boundKnowledgeBaseIds: list[str] = Field(default_factory=list)
    boundModelIds: list[str] = Field(default_factory=list)
    model: CourseAgentModelConfigDto = Field(default_factory=CourseAgentModelConfigDto)
    activeModelId: str | None = None
    models: list[CourseAgentModelProfileDto] = Field(default_factory=list)
    stateMachine: list[CourseAgentStateStepDto] = Field(default_factory=list)
    workflowGraph: dict[str, Any] | None = None
    knowledgeBases: list[CourseAgentKnowledgeBaseDto] = Field(default_factory=list)
    embed: CourseAgentEmbedConfigDto
    conversation: CourseAgentConversationConfigDto
    reactConfig: CourseAgentReactConfigDto | None = None
    schedule: CourseAgentScheduleDto | None = None
    updatedAt: str


class CourseAgentSummaryDto(BaseModel):
    agentId: str
    name: str
    description: str = ""
    status: str
    agentType: CourseAgentType = "workflow"
    isDefault: bool = False
    visibleInChat: bool = True
    runMode: str = "chat"
    scheduleEnabled: bool = False
    tenantId: str | None = None
    updatedAt: str


class DeleteCourseAgentSessionResultDto(BaseModel):
    message: str = "会话已删除"


class DeleteCourseAgentResultDto(BaseModel):
    message: str = "Agent 已删除"


class CourseAgentPatchBody(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    isDefault: bool | None = None
    temperature: float | None = None
    boundKnowledgeBaseIds: list[str] | None = None
    boundModelIds: list[str] | None = None
    model: CourseAgentModelConfigDto | None = None
    stateMachine: list[CourseAgentStateStepDto] | None = None
    workflowGraph: dict[str, Any] | None = None
    knowledgeBases: list[CourseAgentKnowledgeBaseDto] | None = None
    embed: CourseAgentEmbedConfigDto | None = None
    conversation: CourseAgentConversationConfigDto | None = None
    reactConfig: CourseAgentReactConfigDto | None = None
    schedule: CourseAgentScheduleDto | None = None


class SendCourseAgentMessageBody(BaseModel):
    content: str = Field(default="")


class PublicAgentConfigDto(BaseModel):
    agentId: str
    name: str
    welcomeMessage: str
    menuButtons: list[str] = Field(default_factory=list)
    theme: str = "light"


class CourseAgentLeadSummaryDto(BaseModel):
    id: str
    agentId: str
    agentName: str
    sessionId: str
    consultationIndex: int
    status: str
    clientIp: str | None = None
    role: str | None = None
    profile: dict[str, Any] = Field(default_factory=dict)
    title: str = "客户咨询"
    messageCount: int = 0
    startedAt: str
    endedAt: str | None = None


class CourseAgentLeadDetailDto(CourseAgentLeadSummaryDto):
    userAgent: str | None = None
    origin: str | None = None
    messages: list[CourseAgentMessageDto] = Field(default_factory=list)


class DeleteCourseAgentLeadResultDto(BaseModel):
    message: str = "线索已删除"


class AdminSessionRecordDto(BaseModel):
    id: str
    agentId: str
    agentName: str
    title: str
    messageCount: int = 0
    createdAt: str
    updatedAt: str


class AdminUserSessionGroupDto(BaseModel):
    userId: str | None = None
    username: str
    fullName: str
    personaLabel: str | None = None
    sessionCount: int = 0
    lastActiveAt: str | None = None
    sessions: list[AdminSessionRecordDto] = Field(default_factory=list)


class AdminSessionDetailDto(CourseAgentSessionDto):
    agentName: str = ""
    userId: str | None = None
    username: str = "guest"
    fullName: str = "游客"
    personaLabel: str | None = None
