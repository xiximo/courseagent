from pydantic import BaseModel


class LoginAuditDto(BaseModel):
    id: str
    username: str
    fullName: str
    ipAddress: str
    loggedInAt: str
