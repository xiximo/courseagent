from pydantic import BaseModel, Field


class RegisterOrgBody(BaseModel):
    orgName: str = Field(min_length=2, max_length=128)
    contactName: str = Field(min_length=2, max_length=128)
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class TenantSummaryDto(BaseModel):
    id: str
    name: str
    slug: str
    ownerUsername: str = ""
    planCode: str = "free"
    userCount: int = 0
    createdAt: str = ""


class UpdateTenantPlanBody(BaseModel):
    planCode: str = Field(pattern="^(free|pro)$")


class DeleteTenantResultDto(BaseModel):
    message: str = "机构已删除"


class RegisterMemberBody(BaseModel):
    slug: str = Field(min_length=2, max_length=64)
    fullName: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class CreateOrgMemberBody(BaseModel):
    fullName: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class PublicTenantDto(BaseModel):
    name: str
    slug: str


class OrgMemberDto(BaseModel):
    id: str
    username: str
    fullName: str
    status: str
    roleCodes: list[str] = Field(default_factory=list)
    lastLoginAt: str | None = None
    createdAt: str | None = None


class OrgWorkspaceDto(BaseModel):
    tenantId: str
    tenantName: str
    slug: str
    planCode: str = "free"
    userCount: int = 0
    joinPath: str = ""
