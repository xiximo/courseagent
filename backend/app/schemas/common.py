from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    code: str
    message: str | None = None
    data: T | None = None


def success(data: T, code: str = "OK", message: str | None = None) -> ApiResponse[T]:
    return ApiResponse(ok=True, code=code, message=message, data=data)
