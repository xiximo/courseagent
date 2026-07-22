from pydantic import BaseModel, Field


class CitationDto(BaseModel):
    standardNo: str = ""
    standardName: str = ""
    attachment: str | None = None
    attachmentId: str | None = None
    chunkId: str | None = None
    excerpt: str = ""
    position: str | None = None
    standardId: str | None = None


class QaAnswerDto(BaseModel):
    conclusion: str
    basis: list[str] = Field(default_factory=list)
    citations: list[CitationDto] = Field(default_factory=list)
    scope: str | None = None
    riskNotice: str | None = None
    disclaimer: str
    answeredAt: str
    knowledgeBaseUpdatedAt: str


class ChatMessageDto(BaseModel):
    id: str
    role: str
    content: str
    answer: QaAnswerDto | None = None
    createdAt: str


class QaSessionDto(BaseModel):
    id: str
    title: str
    standardId: str | None = None
    messages: list[ChatMessageDto] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class CreateQaSessionBody(BaseModel):
    standardId: str | None = None


class SendQaMessageBody(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
