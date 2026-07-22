from pydantic import BaseModel, Field


class LlmConfigDto(BaseModel):
    enabled: bool = True
    provider: str = "doubao"
    modelName: str
    endpointId: str
    apiKeyMasked: str
    baseUrl: str
    timeoutSeconds: int = Field(ge=10, le=600)
    qaTopK: int = Field(ge=1, le=30)
    configured: bool = False


class UpdateLlmConfigBody(BaseModel):
    enabled: bool | None = None
    modelName: str | None = None
    endpointId: str | None = None
    apiKey: str | None = None
    baseUrl: str | None = None
    timeoutSeconds: int | None = Field(default=None, ge=10, le=600)
    qaTopK: int | None = Field(default=None, ge=1, le=30)
