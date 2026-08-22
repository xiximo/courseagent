from typing import Literal

from pydantic import BaseModel, Field

AccountStatusDto = Literal["enabled", "disabled", "locked", "terminated"]


class UserPersonaProfileDto(BaseModel):
    persona: str = ""
    personaLabel: str = ""
    summary: str = ""
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    sampleQuestions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class UserAccountDto(BaseModel):
    id: str
    username: str
    fullName: str
    status: AccountStatusDto = "enabled"
    roleCodes: list[str] = Field(default_factory=list)
    profile: UserPersonaProfileDto = Field(default_factory=UserPersonaProfileDto)
    lastLoginAt: str | None = None
    createdAt: str | None = None
    isSeed: bool = False


class CreateUserBody(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    fullName: str = Field(min_length=1, max_length=128)
    status: AccountStatusDto = "enabled"
    roleCodes: list[str] = Field(default_factory=lambda: ["end_user"])
    profile: UserPersonaProfileDto = Field(default_factory=UserPersonaProfileDto)


class UpdateUserBody(BaseModel):
    fullName: str | None = Field(default=None, min_length=1, max_length=128)
    status: AccountStatusDto | None = None
    roleCodes: list[str] | None = None
    profile: UserPersonaProfileDto | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)


class DeleteUserResultDto(BaseModel):
    message: str = "用户已删除"


class ResetUserPasswordResultDto(BaseModel):
    message: str = "密码已重置"
    password: str
