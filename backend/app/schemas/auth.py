from typing import Literal

from pydantic import BaseModel, Field

AccountStatus = Literal["enabled", "disabled", "locked", "terminated"]


class AuthUserProfile(BaseModel):
    id: str
    username: str
    fullName: str
    employeeNo: str | None = None
    deptId: str | None = None
    status: AccountStatus = "enabled"
    roleCodes: list[str] = Field(default_factory=list)
    lastLoginAt: str | None = None


class LoginBody(BaseModel):
    username: str
    password: str


class ChangePasswordBody(BaseModel):
    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=6, max_length=128)


class ChangePasswordResultDto(BaseModel):
    changed: bool = True


class LoginResponse(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    expiresInSeconds: int
    user: AuthUserProfile
